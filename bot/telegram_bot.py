"""
Bot de Telegram — PREDIKTOR
Lee el JSON diario y publica picks en el canal público.
No calcula, no decide, no inventa: solo lee y publica.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from telegram import Update, Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.config import (
    BOT_TOKEN, CHANNEL_ID, DAILY_PICKS_PATH, PUBLISH_LOG_PATH,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("prediktor_bot")

# ── Hora Colombia (UTC-5) ──
_COL_TZ = timezone(timedelta(hours=-5))


# ══════════════════════════════════════════════════════════════
#  LECTURA DEL JSON DIARIO
# ══════════════════════════════════════════════════════════════

def load_daily_picks() -> dict | None:
    """Lee el JSON diario. Retorna None si no existe o está corrupto."""
    if not DAILY_PICKS_PATH.exists():
        log.warning("JSON diario no encontrado: %s", DAILY_PICKS_PATH)
        return None
    try:
        data = json.loads(DAILY_PICKS_PATH.read_text(encoding="utf-8"))
        log.info("JSON diario cargado: fecha=%s", data.get("date"))
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.error("Error al leer JSON diario: %s", e)
        return None


# ══════════════════════════════════════════════════════════════
#  FORMATEO DE MENSAJES
# ══════════════════════════════════════════════════════════════

def format_pick_gratuito(pick: dict, date_str: str) -> str:
    """Formatea el pick gratuito para publicación en canal público."""
    league = pick.get("league", "—")
    matchup = pick.get("matchup", "—")
    market = pick.get("market", "—")
    odds = pick.get("bk_odds")
    prob = pick.get("prob_adjusted")

    odds_str = f" @{odds}" if odds else ""
    prob_str = f"{prob:.0f}%" if prob else "—"

    return (
        f"✅ <b>PICK GRATUITO DEL DÍA</b>\n"
        f"📅 {date_str}\n"
        f"\n"
        f"🏆 Liga: {league}\n"
        f"⚽ Partido: {matchup}\n"
        f"🎯 Mercado: <b>{market}{odds_str}</b>\n"
        f"📊 Probabilidad estimada: <b>{prob_str}</b>\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 Síguenos para picks diarios gratuitos"
    )


def format_teaser_premium(pick_dia: dict, date_str: str) -> str:
    """Formatea el teaser del Pick del Día (sin revelar mercado completo)."""
    league = pick_dia.get("league", "—")
    matchup = pick_dia.get("matchup", "—")

    return (
        f"🔥 <b>PICK DEL DÍA — PREMIUM</b>\n"
        f"📅 {date_str}\n"
        f"\n"
        f"🏆 Liga: {league}\n"
        f"⚽ Partido: {matchup}\n"
        f"📈 Confianza: <b>ALTA</b>\n"
        f"\n"
        f"🔒 Mercado y cuota disponibles para miembros premium\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 Desbloquea con suscripción"
    )


def format_no_picks(date_str: str) -> str:
    """Mensaje cuando no hay picks para el día."""
    return (
        f"📅 <b>PREDIKTOR — {date_str}</b>\n"
        f"\n"
        f"Hoy el motor no encontró picks con valor suficiente.\n"
        f"No forzamos apuestas — a veces el mejor pick es no apostar.\n"
        f"\n"
        f"🔔 Mañana volvemos con nuevas oportunidades"
    )


# ══════════════════════════════════════════════════════════════
#  CONTROL DE DUPLICADOS
# ══════════════════════════════════════════════════════════════

def _load_publish_log() -> dict:
    if PUBLISH_LOG_PATH.exists():
        try:
            return json.loads(PUBLISH_LOG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_publish_log(data: dict):
    PUBLISH_LOG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _already_published(date_str: str) -> bool:
    """Retorna True si ya se publicó para esta fecha."""
    publish_log = _load_publish_log()
    return publish_log.get("last_published") == date_str


def _mark_published(date_str: str):
    """Marca la fecha como publicada."""
    publish_log = _load_publish_log()
    publish_log["last_published"] = date_str
    publish_log["timestamp"] = datetime.now(_COL_TZ).isoformat()
    _save_publish_log(publish_log)


# ══════════════════════════════════════════════════════════════
#  PUBLICACIÓN AUTOMÁTICA (entry point para cron / GitHub Actions)
# ══════════════════════════════════════════════════════════════

async def publish_today_picks():
    """
    Lee el JSON diario y publica en el canal público.
    Puede llamarse desde cron, GitHub Actions, o el comando /publish.
    No reenvía si ya se publicó hoy.

    Regla clave: el pick_gratuito SIEMPRE se publica si existe,
    aunque no haya picks de suscripción ni pick_dia premium.

    En python-telegram-bot v20+ el Bot DEBE inicializarse antes de
    enviar mensajes. Usamos 'async with Bot(...) as bot:' que maneja
    initialize() y shutdown() automáticamente.
    """
    log.info("=== BOT PREDIKTOR — publish_today_picks() ===")

    if not BOT_TOKEN:
        log.error("❌ TELEGRAM_BOT_TOKEN no configurado — abortando")
        return False
    if not CHANNEL_ID:
        log.error("❌ TELEGRAM_CHANNEL_ID no configurado — abortando")
        return False

    log.info("✓ Credenciales detectadas (canal: %s)", CHANNEL_ID)

    data = load_daily_picks()
    if data is None:
        log.error("❌ No se pudo cargar el JSON diario — abortando")
        return False

    date_str = data.get("date", "—")
    pick_gratuito = data.get("pick_gratuito")
    pick_dia = data.get("pick_dia")
    picks_sub = data.get("picks_suscripcion", [])

    log.info("✓ JSON cargado: fecha=%s | gratuito=%s | premium=%s | suscripcion=%d",
             date_str,
             "SI" if pick_gratuito else "NO",
             "SI" if pick_dia else "NO",
             len(picks_sub))

    # Evitar duplicados
    if _already_published(date_str):
        log.info("⏭  Picks del %s ya publicados — sin reenviar", date_str)
        return True

    # async with inicializa la sesión HTTP y la cierra al salir.
    # Sin esto, Bot(token) NO conecta y send_message() falla silenciosamente.
    messages_sent = 0
    try:
        async with Bot(token=BOT_TOKEN) as bot:
            # 1. PICK GRATUITO — prioridad absoluta.
            #    Se publica SIEMPRE que exista, sin depender de otros picks.
            if pick_gratuito:
                msg = format_pick_gratuito(pick_gratuito, date_str)
                await bot.send_message(
                    chat_id=CHANNEL_ID, text=msg, parse_mode=ParseMode.HTML,
                )
                log.info("✅ Pick gratuito publicado: %s", pick_gratuito.get("matchup"))
                messages_sent += 1
            else:
                log.warning("⚠  pick_gratuito es null en daily_picks.json")

            # 2. Teaser del Pick del Día (solo si hay premium)
            if pick_dia:
                msg = format_teaser_premium(pick_dia, date_str)
                await bot.send_message(
                    chat_id=CHANNEL_ID, text=msg, parse_mode=ParseMode.HTML,
                )
                log.info("🔥 Teaser premium publicado: %s", pick_dia.get("matchup"))
                messages_sent += 1

            # 3. Sin picks — fallback honesto
            if messages_sent == 0:
                msg = format_no_picks(date_str)
                await bot.send_message(
                    chat_id=CHANNEL_ID, text=msg, parse_mode=ParseMode.HTML,
                )
                log.info("📅 Mensaje 'sin picks' publicado")

    except TelegramError as e:
        log.error("❌ Error de Telegram: %s", e)
        return False
    except Exception as e:
        log.error("❌ Error inesperado: %s", e)
        return False

    _mark_published(date_str)
    log.info("✅ Publicación completada para %s (%d mensajes enviados)", date_str, messages_sent)
    return True


# ══════════════════════════════════════════════════════════════
#  COMANDOS DEL BOT (interacción por DM)
# ══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start — Bienvenida y explicación de niveles."""
    await update.message.reply_text(
        "👋 <b>Bienvenido a PREDIKTOR</b>\n"
        "\n"
        "Somos un motor de predicciones deportivas basado en estadísticas reales, "
        "probabilidades y valor esperado (EV).\n"
        "\n"
        "<b>Nuestros niveles:</b>\n"
        "\n"
        "✅ <b>Pick Gratuito</b> — 1 pick diario publicado en este canal\n"
        "📊 <b>Suscripción</b> — 2 a 4 picks diarios con análisis detallado\n"
        "🔥 <b>Pick del Día (Premium)</b> — El pick con mayor valor del día\n"
        "\n"
        "<b>Comandos:</b>\n"
        "/pick — Ver el pick gratuito de hoy\n"
        "/premium — Ver teaser del Pick del Día\n"
        "/status — Estado del motor\n"
        "\n"
        "🔔 No forzamos picks — si no hay valor, no publicamos.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/pick — Muestra el pick gratuito del día."""
    data = load_daily_picks()
    if data is None:
        await update.message.reply_text("⚠️ No hay datos disponibles hoy.")
        return

    date_str = data.get("date", "—")
    pick = data.get("pick_gratuito")

    if pick:
        await update.message.reply_text(
            format_pick_gratuito(pick, date_str),
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            format_no_picks(date_str),
            parse_mode=ParseMode.HTML,
        )


async def cmd_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/premium — Muestra teaser del Pick del Día."""
    data = load_daily_picks()
    if data is None:
        await update.message.reply_text("⚠️ No hay datos disponibles hoy.")
        return

    date_str = data.get("date", "—")
    pick_dia = data.get("pick_dia")

    if pick_dia:
        await update.message.reply_text(
            format_teaser_premium(pick_dia, date_str),
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"📅 <b>{date_str}</b>\n\n"
            "Hoy no hay Pick del Día — ningún pick cumplió los umbrales premium.\n"
            "Esto es normal: el motor es conservador por diseño.",
            parse_mode=ParseMode.HTML,
        )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status — Estado del motor y última publicación."""
    data = load_daily_picks()
    publish_log = _load_publish_log()

    if data is None:
        await update.message.reply_text(
            "⚠️ <b>Estado:</b> JSON diario no encontrado\n"
            "El motor no ha generado picks todavía.",
            parse_mode=ParseMode.HTML,
        )
        return

    date_str = data.get("date", "—")
    has_dia = "✅" if data.get("pick_dia") else "❌"
    has_gratis = "✅" if data.get("pick_gratuito") else "❌"
    n_suscripcion = len(data.get("picks_suscripcion", []))
    last_pub = publish_log.get("last_published", "nunca")

    await update.message.reply_text(
        f"📊 <b>Estado PREDIKTOR</b>\n"
        f"\n"
        f"📅 Fecha JSON: <b>{date_str}</b>\n"
        f"🔥 Pick del Día: {has_dia}\n"
        f"✅ Pick Gratuito: {has_gratis}\n"
        f"📊 Picks Suscripción: {n_suscripcion}\n"
        f"\n"
        f"📤 Última publicación: {last_pub}",
        parse_mode=ParseMode.HTML,
    )


# ══════════════════════════════════════════════════════════════
#  ARRANQUE DEL BOT (modo polling para desarrollo)
# ══════════════════════════════════════════════════════════════

def run_bot():
    """Arranca el bot en modo polling (desarrollo / VPS)."""
    if not BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN no configurado — abortando")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("pick", cmd_pick))
    app.add_handler(CommandHandler("premium", cmd_premium))
    app.add_handler(CommandHandler("status", cmd_status))

    log.info("Bot PREDIKTOR iniciado en modo polling")
    app.run_polling()


if __name__ == "__main__":
    run_bot()
