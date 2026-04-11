#!/usr/bin/env python3
"""
Entry point para publicación automática vía cron / GitHub Actions.
Uso:
    python -m bot.publish          # publica picks del día
    python -m bot.publish --force  # ignora control de duplicados

Requiere variables de entorno:
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHANNEL_ID
"""
import asyncio
import sys
from pathlib import Path

# Asegurar que el project root esté en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.telegram_bot import publish_today_picks, _mark_published, load_daily_picks, log
from bot.config import PUBLISH_LOG_PATH


async def main():
    force = "--force" in sys.argv

    if force:
        # Limpiar log para forzar reenvío
        data = load_daily_picks()
        if data and PUBLISH_LOG_PATH.exists():
            PUBLISH_LOG_PATH.unlink()
            log.info("--force: log de publicación eliminado")

    success = await publish_today_picks()

    if success:
        log.info("Publicación exitosa")
        sys.exit(0)
    else:
        log.error("Publicación fallida")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
