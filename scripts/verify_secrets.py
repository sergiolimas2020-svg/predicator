#!/usr/bin/env python3
"""
PREDIKTOR — Verificación de secrets antes del workflow.
Ejecuta en el step 0 del CI. Falla rápido si alguna API key crítica no funciona.

Secrets verificados:
  - ODDS_API_KEY      → obligatorio para fetch_odds.py
  - TELEGRAM_BOT_TOKEN → obligatorio para publicación en canal
  - TELEGRAM_CHANNEL_ID → obligatorio para publicación en canal

Secrets opcionales (warning si faltan, no fail):
  - RAPIDAPI_KEY      → APIs auxiliares (NBA games, props, corners)
  - TELEGRAM_ADMIN_CHAT_ID → notificaciones de error al admin

Uso:
    python3 scripts/verify_secrets.py
Exit codes:
    0 → todos los secrets críticos OK
    1 → algún secret crítico falló (workflow debe abortar)
"""
import os
import ssl
import sys
import json
import urllib.request
import urllib.error
from typing import Tuple


# ── Contexto SSL: usar certifi si está disponible (Mac/CI con bundle propio)
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()


# ── Config ────────────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

def red(s):    return f"{RED}{s}{RESET}"
def green(s):  return f"{GREEN}{s}{RESET}"
def yellow(s): return f"{YELLOW}{s}{RESET}"


# ── Validadores por secret ────────────────────────────────────

def check_odds_api(key: str) -> Tuple[bool, str]:
    """
    Verifica ODDS_API_KEY contra The Odds API.
    Usa el endpoint /v4/sports que NO consume créditos (solo metadata).
    """
    if not key:
        return False, "ODDS_API_KEY vacío o no configurado"
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PREDIKTOR-CI/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                return True, f"OK ({len(data)} deportes disponibles)"
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "401 Unauthorized — API key inválida o expirada"
        if e.code == 429:
            return False, "429 Too Many Requests — créditos agotados"
        return False, f"HTTP error {e.code}: {e.reason}"
    except Exception as e:
        return False, f"Error: {e}"


def check_telegram_bot_token(token: str) -> Tuple[bool, str]:
    """
    Verifica TELEGRAM_BOT_TOKEN contra Telegram Bot API.
    El endpoint /getMe es gratis y valida que el token funcione.
    """
    if not token:
        return False, "TELEGRAM_BOT_TOKEN vacío o no configurado"
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=10, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
            if data.get("ok"):
                username = data["result"].get("username", "?")
                return True, f"OK (bot: @{username})"
            return False, f"Telegram dice no OK: {data}"
    except urllib.error.HTTPError as e:
        if e.code in (401, 404):
            return False, f"HTTP {e.code} — token inválido"
        return False, f"HTTP error {e.code}"
    except Exception as e:
        return False, f"Error: {e}"


def check_telegram_channel(token: str, channel_id: str) -> Tuple[bool, str]:
    """
    Verifica que el bot tenga acceso al canal configurado.
    Endpoint /getChat valida que el bot pueda leer info del canal.
    """
    if not token:
        return False, "TELEGRAM_BOT_TOKEN no configurado (no se puede verificar canal)"
    if not channel_id:
        return False, "TELEGRAM_CHANNEL_ID vacío"
    url = f"https://api.telegram.org/bot{token}/getChat?chat_id={channel_id}"
    try:
        with urllib.request.urlopen(url, timeout=10, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
            if data.get("ok"):
                title = data["result"].get("title") or data["result"].get("username", "?")
                return True, f"OK (canal: {title})"
            return False, f"Telegram dice no OK: {data}"
    except urllib.error.HTTPError as e:
        if e.code == 400:
            return False, "400 Bad Request — channel_id inválido o bot no es admin"
        return False, f"HTTP error {e.code}"
    except Exception as e:
        return False, f"Error: {e}"


# ── Main ──────────────────────────────────────────────────────

def main() -> int:
    print("=" * 60)
    print("  PREDIKTOR — Verificación de secrets")
    print("=" * 60)

    odds_key = os.environ.get("ODDS_API_KEY", "")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "")
    rapid_key = os.environ.get("RAPIDAPI_KEY", "")
    admin_chat = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")

    critical_ok = True
    warnings = []

    # ── CRÍTICO: ODDS_API_KEY ──
    print("\n[1/3] ODDS_API_KEY (crítico)")
    ok, msg = check_odds_api(odds_key)
    if ok:
        print(f"  {green('✓')} {msg}")
    else:
        print(f"  {red('✗')} {msg}")
        critical_ok = False

    # ── CRÍTICO: TELEGRAM_BOT_TOKEN ──
    print("\n[2/3] TELEGRAM_BOT_TOKEN (crítico)")
    ok, msg = check_telegram_bot_token(bot_token)
    if ok:
        print(f"  {green('✓')} {msg}")
    else:
        print(f"  {red('✗')} {msg}")
        critical_ok = False

    # ── CRÍTICO: TELEGRAM_CHANNEL_ID ──
    print("\n[3/3] TELEGRAM_CHANNEL_ID (crítico)")
    ok, msg = check_telegram_channel(bot_token, channel_id)
    if ok:
        print(f"  {green('✓')} {msg}")
    else:
        print(f"  {red('✗')} {msg}")
        critical_ok = False

    # ── OPCIONALES ──
    print("\n— Opcionales —")
    if rapid_key:
        print(f"  {green('✓')} RAPIDAPI_KEY presente (no se valida — uso bajo demanda)")
    else:
        print(f"  {yellow('!')} RAPIDAPI_KEY no configurado (APIs auxiliares deshabilitadas)")
        warnings.append("RAPIDAPI_KEY")

    if admin_chat:
        print(f"  {green('✓')} TELEGRAM_ADMIN_CHAT_ID presente (notificaciones admin habilitadas)")
    else:
        print(f"  {yellow('!')} TELEGRAM_ADMIN_CHAT_ID no configurado (sin alertas a admin)")
        warnings.append("TELEGRAM_ADMIN_CHAT_ID")

    # ── Resumen ──
    print("\n" + "=" * 60)
    if critical_ok:
        if warnings:
            print(f"  {green('✓ Secrets críticos OK')} | {yellow(str(len(warnings)) + ' opcionales faltan')}")
        else:
            print(f"  {green('✓ TODOS los secrets OK')}")
        print("=" * 60)
        return 0
    else:
        print(f"  {red('✗ FALLÓ — algún secret crítico no funciona')}")
        print(f"  {red('  El workflow debe abortar para no generar daño.')}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
