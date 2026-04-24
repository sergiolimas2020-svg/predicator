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
from bot.content_generator import (
    generate_daily_content, save_daily_content, format_content_for_telegram,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("prediktor_bot")

# ── Hora Colombia (UTC-5) ──
_COL_TZ = timezone(timedelta(hours=-5))

# ══════════════════════════════════════════════════════════════
#  ESTADOS POSIBLES DE PUBLICACIÓN
#  El bot SIEMPRE comunica algo al canal — nunca queda mudo.
# ══════════════════════════════════════════════════════════════
STATE_SUCCESS            = "success"           # A — hay picks del día
STATE_NO_VALUE           = "no_value"          # B — JSON OK pero sin valor
STATE_ODDS_FAILURE       = "odds_failure"      # C — no se pudo traer odds
STATE_EXECUTION_FAILURE  = "execution_failure" # D — motor falló / JSON viejo

# Path al archivo de odds (para detectar fallos de odds fetch)
_ODDS_JSON_PATH = DAILY_PICKS_PATH.parent.parent / "odds.json"


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
    """Mensaje cuando no hay picks para el día (legacy — estado B genérico)."""
    return (
        f"📅 <b>PREDIKTOR — {date_str}</b>\n"
        f"\n"
        f"Hoy el motor no encontró picks con valor suficiente.\n"
        f"No forzamos apuestas — a veces el mejor pick es no apostar.\n"
        f"\n"
        f"🔔 Mañana volvemos con nuevas oportunidades"
    )


def format_state_no_value(date_str: str) -> str:
    """Estado B: JSON OK, pero todos los picks son null (sin valor estadístico)."""
    return (
        f"📅 <b>PREDIKTOR — {date_str}</b>\n"
        f"\n"
        f"Hoy el motor no encontró picks con valor estadístico suficiente.\n"
        f"\n"
        f"Esto no es un error: significa que las cuotas del mercado están "
        f"alineadas con nuestras probabilidades, y no hay diferencial aprovechable.\n"
        f"\n"
        f"No forzamos picks sin valor real.\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 Mañana volvemos con nuevas oportunidades"
    )


def format_state_odds_failure(date_str: str) -> str:
    """Estado C: no se pudo acceder a las cuotas de los bookmakers."""
    return (
        f"⚠️ <b>PREDIKTOR — {date_str}</b>\n"
        f"\n"
        f"Hoy no pudimos acceder a las cuotas de los bookmakers.\n"
        f"\n"
        f"Por seguridad, no publicamos picks sin datos verificados de mercado. "
        f"El análisis estadístico se reanudará en cuanto la conexión con las "
        f"casas de apuestas se restablezca.\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 Volvemos a publicar en cuanto se resuelva"
    )


def format_state_execution_failure(date_str: str) -> str:
    """Estado D: inconveniente técnico (motor no corrió o JSON obsoleto)."""
    return (
        f"⚠️ <b>PREDIKTOR — {date_str}</b>\n"
        f"\n"
        f"Tenemos un inconveniente técnico en el motor de predicciones.\n"
        f"\n"
        f"Nuestro equipo ya está trabajando en resolverlo. Cuando el sistema "
        f"vuelva a generar picks, se publicará automáticamente.\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 Gracias por tu paciencia"
    )


# ══════════════════════════════════════════════════════════════
#  DETECCIÓN DE ESTADO
#  Decide qué mensaje se debe publicar basándose en los datos
#  disponibles. El bot nunca queda mudo: SIEMPRE hay un estado.
# ══════════════════════════════════════════════════════════════

def _odds_json_is_usable() -> bool:
    """Retorna True si odds.json existe y tiene al menos un partido."""
    if not _ODDS_JSON_PATH.exists():
        return False
    try:
        data = json.loads(_ODDS_JSON_PATH.read_text(encoding="utf-8"))
        return isinstance(data, dict) and len(data) > 0
    except (json.JSONDecodeError, OSError):
        return False


def detect_state(data: dict | None, today_str: str) -> str:
    """
    Clasifica la situación del día en uno de 4 estados.
    Nunca retorna None — siempre hay un estado válido.

    A) STATE_SUCCESS            → hay al menos un pick publicable
    B) STATE_NO_VALUE           → JSON actual pero sin picks (motor descartó)
    C) STATE_ODDS_FAILURE       → JSON vacío y odds.json no usable
    D) STATE_EXECUTION_FAILURE  → JSON no existe o fecha desactualizada
    """
    # D1: Sin JSON → fallo de ejecución
    if data is None:
        log.info("Estado detectado: EXECUTION_FAILURE (JSON no existe)")
        return STATE_EXECUTION_FAILURE

    # D2: JSON con fecha distinta de hoy → motor no corrió hoy
    json_date = data.get("date", "")
    if json_date != today_str:
        log.info("Estado detectado: EXECUTION_FAILURE (fecha JSON=%s, hoy=%s)",
                 json_date, today_str)
        return STATE_EXECUTION_FAILURE

    # A: JSON actual con al menos un pick publicable
    has_picks = any([
        data.get("pick_gratuito"),
        data.get("pick_dia"),
        data.get("pick_exploratorio"),
        data.get("picks_suscripcion"),
    ])
    if has_picks:
        log.info("Estado detectado: SUCCESS")
        return STATE_SUCCESS

    # B vs C: JSON vacío — ¿es por falta de valor o por fallo de odds?
    if _odds_json_is_usable():
        log.info("Estado detectado: NO_VALUE (odds disponibles, sin valor)")
        return STATE_NO_VALUE
    else:
        log.info("Estado detectado: ODDS_FAILURE (odds.json no usable)")
        return STATE_ODDS_FAILURE


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


def _already_published(date_str: str, state: str) -> bool:
    """
    Retorna True si YA se publicó el MISMO estado el MISMO día.
    Permite recuperación: si antes publicamos estado D (fallo) y luego
    el motor se arregla a estado A (éxito), se re-publica.
    """
    publish_log = _load_publish_log()
    return (
        publish_log.get("last_published") == date_str
        and publish_log.get("last_state") == state
    )


def _mark_published(date_str: str, state: str):
    """Marca la fecha+estado como publicados."""
    publish_log = _load_publish_log()
    publish_log["last_published"] = date_str
    publish_log["last_state"] = state
    publish_log["timestamp"] = datetime.now(_COL_TZ).isoformat()
    _save_publish_log(publish_log)


# ══════════════════════════════════════════════════════════════
#  PUBLICACIÓN AUTOMÁTICA (entry point para cron / GitHub Actions)
# ══════════════════════════════════════════════════════════════

async def publish_today_picks():
    """
    Lee el JSON diario, detecta el estado del sistema y publica en el canal.
    El bot SIEMPRE comunica algo al canal — nunca queda mudo.

    Estados manejados:
      A) SUCCESS           → publica pick gratuito + teaser premium
      B) NO_VALUE          → "hoy no hay valor estadístico suficiente"
      C) ODDS_FAILURE      → "no pudimos acceder a las cuotas hoy"
      D) EXECUTION_FAILURE → "inconveniente técnico en el motor"

    Control de duplicados: no reenvía si el mismo estado ya se publicó
    hoy. Pero si cambia el estado (ej: D → A cuando el motor se arregla),
    re-publica con el estado nuevo.
    """
    log.info("=== BOT PREDIKTOR — publish_today_picks() ===")

    if not BOT_TOKEN:
        log.error("❌ TELEGRAM_BOT_TOKEN no configurado — abortando")
        return False
    if not CHANNEL_ID:
        log.error("❌ TELEGRAM_CHANNEL_ID no configurado — abortando")
        return False

    log.info("✓ Credenciales detectadas (canal: %s)", CHANNEL_ID)

    # Determinar "hoy" en hora Colombia
    today_col = datetime.now(_COL_TZ).strftime("%Y-%m-%d")

    # Cargar datos y detectar estado
    data = load_daily_picks()
    state = detect_state(data, today_col)

    # Fecha para mostrar en el mensaje (la del JSON si existe, sino hoy)
    date_str = data.get("date", today_col) if data else today_col

    if data:
        pick_gratuito = data.get("pick_gratuito")
        pick_dia = data.get("pick_dia")
        picks_sub = data.get("picks_suscripcion", [])
        log.info("✓ JSON: fecha=%s | gratuito=%s | premium=%s | suscripcion=%d | estado=%s",
                 data.get("date", "?"),
                 "SI" if pick_gratuito else "NO",
                 "SI" if pick_dia else "NO",
                 len(picks_sub),
                 state)
    else:
        pick_gratuito = pick_dia = None
        picks_sub = []
        log.warning("⚠  JSON no disponible | estado=%s", state)

    # Control de duplicados por estado
    if _already_published(today_col, state):
        log.info("⏭  Estado '%s' del %s ya publicado — sin reenviar", state, today_col)
        return True

    # Publicar según estado
    messages_sent = 0
    try:
        async with Bot(token=BOT_TOKEN) as bot:

            if state == STATE_SUCCESS:
                # A) Publicar pick gratuito + teaser premium si aplica
                if pick_gratuito:
                    msg = format_pick_gratuito(pick_gratuito, date_str)
                    await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode=ParseMode.HTML)
                    log.info("✅ Pick gratuito publicado: %s", pick_gratuito.get("matchup"))
                    messages_sent += 1
                if pick_dia:
                    msg = format_teaser_premium(pick_dia, date_str)
                    await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode=ParseMode.HTML)
                    log.info("🔥 Teaser premium publicado: %s", pick_dia.get("matchup"))
                    messages_sent += 1
                # Safety net: si state==SUCCESS pero no había ni gratuito ni pick_dia
                # (solo suscripción), publicar al menos un mensaje informativo
                if messages_sent == 0:
                    msg = format_no_picks(date_str)
                    await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode=ParseMode.HTML)
                    log.info("📅 Mensaje fallback publicado (success sin gratuito/premium)")
                    messages_sent += 1

            elif state == STATE_NO_VALUE:
                # B) JSON actual pero sin picks — motor fue selectivo
                #    Usamos el content generator para publicar contenido mínimo
                #    (análisis / agenda / explicación) en vez de mensaje genérico.
                try:
                    content = generate_daily_content(today_col)
                    save_daily_content(content)  # para que la web lo lea
                    msg = format_content_for_telegram(content)
                    log.info("📝 Contenido mínimo generado: tipo=%s (%d fixtures)",
                             content.get("type"), content.get("total_fixtures", 0))
                except Exception as e:
                    # Si falla el content generator, fallback al mensaje estático
                    log.warning("Content generator falló (%s), usando fallback", e)
                    msg = format_state_no_value(date_str)

                await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode=ParseMode.HTML)
                log.info("📅 Estado B publicado (NO_VALUE + contenido mínimo)")
                messages_sent += 1

            elif state == STATE_ODDS_FAILURE:
                # C) No se pudo acceder a odds
                msg = format_state_odds_failure(today_col)
                await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode=ParseMode.HTML)
                log.info("⚠  Estado C publicado (ODDS_FAILURE)")
                messages_sent += 1

            elif state == STATE_EXECUTION_FAILURE:
                # D) Motor no corrió o JSON viejo
                msg = format_state_execution_failure(today_col)
                await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode=ParseMode.HTML)
                log.info("⚠  Estado D publicado (EXECUTION_FAILURE)")
                messages_sent += 1

    except TelegramError as e:
        log.error("❌ Error de Telegram: %s", e)
        return False
    except Exception as e:
        log.error("❌ Error inesperado: %s", e)
        return False

    # Registrar el estado publicado (para no duplicar el mismo estado)
    _mark_published(today_col, state)
    log.info("✅ Publicación completada | fecha=%s | estado=%s | mensajes=%d",
             today_col, state, messages_sent)
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
