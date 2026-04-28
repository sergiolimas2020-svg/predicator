"""
Simulación de los 3 escenarios del bot Telegram (Bloque E).

No envía mensajes reales — solo renderiza el texto plano que se publicaría
en cada escenario para validar contenido y tono antes de producción.

Uso:
    python3 tests/simulate_scenarios.py
"""
import sys
from pathlib import Path

# Añadir raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.telegram_bot import (
    format_value_bet,
    format_featured_pick,
    format_no_pick_today,
)

DATE = "2026-04-24"

# ── Escenario 1 — VALUE BET ─────────────────────────────────────
mock_value_pick = {
    "league": "Premier League",
    "matchup": "Arsenal vs Tottenham",
    "market": "Arsenal Win",
    "bk_odds": 1.95,
    "prob_adjusted": 62.0,
    "ev_adjusted": 8.7,
}

# ── Escenario 2 — FEATURED PICK estadístico ─────────────────────
mock_featured = {
    "league": "La Liga",
    "matchup": "Real Madrid vs Getafe",
    "market": "Real Madrid Win",
    "bk_odds": 1.30,
    "prob_adjusted": 72.5,
    "confidence_label": "alta",
    "tier_origin": "statistical_only",
}

# ── Render ──────────────────────────────────────────────────────
def banner(title: str):
    print("\n" + "═" * 60)
    print(f"  {title}")
    print("═" * 60 + "\n")


banner("ESCENARIO 1 — VALUE BET DEL DÍA (motor detectó EV+)")
print(format_value_bet(mock_value_pick, DATE))

banner("ESCENARIO 2 — FEATURED PICK estadístico (sin EV+, prob ≥55%)")
print(format_featured_pick(mock_featured, DATE))

banner("ESCENARIO 3 — NO-PICK (ni value ni featured)")
print(format_no_pick_today(DATE))

print("\n" + "═" * 60)
print("  ✅ Renderizado completo. Validar tono, hashtags y CTAs.")
print("═" * 60 + "\n")
