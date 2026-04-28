#!/usr/bin/env python3
"""
PREDIKTOR — Notificaciones de workflow a Telegram (admin).

Usado por GitHub Actions para alertar al admin sobre éxito o fallo del
pipeline diario. NO publica al canal público (eso lo hace bot/publish.py).

Uso CLI:
    python3 scripts/notify_telegram.py success --picks 5 --date 2026-04-28
    python3 scripts/notify_telegram.py error --step "fetch_odds" --msg "401 Unauthorized"

Uso programático:
    from scripts.notify_telegram import notify_success, notify_error
    notify_success(picks_count=5, date_str="2026-04-28")
    notify_error("fetch_odds", "401 Unauthorized", logs_url="https://...")

Secrets requeridos:
    TELEGRAM_BOT_TOKEN       — bot que envía
    TELEGRAM_ADMIN_CHAT_ID   — chat de admin (NO el canal público)

Si TELEGRAM_ADMIN_CHAT_ID no está configurado, las notificaciones se
loguean a stdout pero no se envían (no rompen el workflow).
"""
import os
import sys
import json
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta


# ── Hora Colombia ──
_COL_TZ = timezone(timedelta(hours=-5))


def _send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Envía mensaje al admin chat. Retorna True si fue enviado."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")

    if not token:
        print(f"[notify_telegram] Sin TELEGRAM_BOT_TOKEN — mensaje no enviado")
        print(f"[notify_telegram] Mensaje:\n{text}")
        return False

    if not chat_id:
        print(f"[notify_telegram] Sin TELEGRAM_ADMIN_CHAT_ID — mensaje no enviado")
        print(f"[notify_telegram] Mensaje:\n{text}")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": "true",
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            if body.get("ok"):
                print(f"[notify_telegram] Mensaje enviado al admin")
                return True
            print(f"[notify_telegram] Telegram rechazó el mensaje: {body}")
            return False
    except Exception as e:
        print(f"[notify_telegram] Error al enviar: {e}")
        return False


def notify_success(picks_count: int, date_str: str = "", details: str = "") -> bool:
    """Notifica que el workflow terminó OK con N picks generados."""
    if not date_str:
        date_str = datetime.now(_COL_TZ).strftime("%Y-%m-%d")

    if picks_count == 0:
        emoji = "📅"
        subtitle = "Sin picks de valor hoy"
    elif picks_count == 1:
        emoji = "✅"
        subtitle = "1 pick publicado"
    else:
        emoji = "🎯"
        subtitle = f"{picks_count} picks publicados"

    text = (
        f"{emoji} <b>PREDIKTOR — Workflow OK</b>\n"
        f"📅 {date_str}\n"
        f"\n"
        f"{subtitle}"
    )
    if details:
        text += f"\n\n<i>{details}</i>"

    return _send_message(text)


def notify_error(step: str, error_msg: str, logs_url: str = "") -> bool:
    """Notifica que un step crítico del workflow falló."""
    date_str = datetime.now(_COL_TZ).strftime("%Y-%m-%d %H:%M")

    text = (
        f"🚨 <b>PREDIKTOR — Workflow FALLÓ</b>\n"
        f"⏰ {date_str} (Colombia)\n"
        f"\n"
        f"<b>Step:</b> <code>{step}</code>\n"
        f"<b>Error:</b>\n"
        f"<pre>{error_msg[:500]}</pre>"
    )
    if logs_url:
        text += f"\n\n<a href='{logs_url}'>Ver logs completos →</a>"

    return _send_message(text)


def notify_warning(message: str) -> bool:
    """Notifica una advertencia (no es error fatal)."""
    date_str = datetime.now(_COL_TZ).strftime("%Y-%m-%d %H:%M")

    text = (
        f"⚠️ <b>PREDIKTOR — Advertencia</b>\n"
        f"⏰ {date_str} (Colombia)\n"
        f"\n"
        f"{message}"
    )
    return _send_message(text)


# ── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Notificar al admin de PREDIKTOR vía Telegram")
    sub = parser.add_subparsers(dest="action", required=True)

    sp_success = sub.add_parser("success", help="Notificar éxito del workflow")
    sp_success.add_argument("--picks", type=int, default=0, help="Cantidad de picks generados")
    sp_success.add_argument("--date", type=str, default="", help="Fecha YYYY-MM-DD")
    sp_success.add_argument("--details", type=str, default="", help="Detalles extra")

    sp_error = sub.add_parser("error", help="Notificar fallo del workflow")
    sp_error.add_argument("--step", type=str, required=True, help="Step que falló")
    sp_error.add_argument("--msg", type=str, required=True, help="Mensaje de error")
    sp_error.add_argument("--logs-url", type=str, default="", help="URL a los logs")

    sp_warn = sub.add_parser("warning", help="Notificar advertencia")
    sp_warn.add_argument("--msg", type=str, required=True, help="Mensaje de advertencia")

    args = parser.parse_args()

    if args.action == "success":
        ok = notify_success(args.picks, args.date, args.details)
    elif args.action == "error":
        ok = notify_error(args.step, args.msg, args.logs_url)
    elif args.action == "warning":
        ok = notify_warning(args.msg)
    else:
        parser.print_help()
        return 2

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
