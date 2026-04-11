"""
Configuración del bot de Telegram — PREDIKTOR
Variables de entorno requeridas:
  TELEGRAM_BOT_TOKEN   — token del bot (BotFather)
  TELEGRAM_CHANNEL_ID  — ID o @alias del canal público
"""
import os
from pathlib import Path

# ── Token del bot (obligatorio) ──
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# ── Canal público donde se publican los picks gratuitos ──
# Puede ser @alias o ID numérico negativo (-100...)
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")

# ── Ruta al JSON diario generado por el motor ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DAILY_PICKS_PATH = PROJECT_ROOT / "static" / "predictions" / "daily_picks.json"

# ── Log de publicaciones (evita duplicados) ──
PUBLISH_LOG_PATH = PROJECT_ROOT / "bot" / "publish_log.json"
