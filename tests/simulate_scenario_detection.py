"""
Validación de la decisión de escenario de publish_today_picks().

No envía mensajes. Mockea los datos en memoria y verifica que la
combinación de (estado, value pick, featured pick) selecciona el
escenario correcto.

Casos:
  1) value pick existe → ESCENARIO 1 (VALUE BET)
  2) sin value pick, featured existe → ESCENARIO 2 (FEATURED)
  3) sin value pick, sin featured → ESCENARIO 3 (NO-PICK)
  4) JSON ausente → ESTADO D (EXECUTION_FAILURE)
  5) odds ausentes y JSON vacío → ESTADO C (ODDS_FAILURE)
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.telegram_bot import (
    detect_state,
    STATE_SUCCESS, STATE_NO_VALUE, STATE_ODDS_FAILURE, STATE_EXECUTION_FAILURE,
)

TODAY = "2026-04-24"

cases = [
    {
        "name": "1) Value pick presente",
        "data": {"date": TODAY, "pick_gratuito": {"matchup": "X"}, "picks_suscripcion": []},
        "odds_ok": True,
        "expected_state": STATE_SUCCESS,
        "scenario": "1 (VALUE BET) — usa format_value_bet()",
    },
    {
        "name": "2) Sin value pick, JSON actual, odds OK (motor selectivo)",
        "data": {"date": TODAY, "pick_gratuito": None, "pick_dia": None, "picks_suscripcion": []},
        "odds_ok": True,
        "expected_state": STATE_NO_VALUE,
        "scenario": "2 (FEATURED) si existe, o 3 (NO-PICK) si no",
    },
    {
        "name": "3) Sin value pick, sin odds usables",
        "data": {"date": TODAY, "pick_gratuito": None, "picks_suscripcion": []},
        "odds_ok": False,
        "expected_state": STATE_ODDS_FAILURE,
        "scenario": "Estado C (ODDS_FAILURE)",
    },
    {
        "name": "4) JSON ausente",
        "data": None,
        "odds_ok": True,
        "expected_state": STATE_EXECUTION_FAILURE,
        "scenario": "Estado D (EXECUTION_FAILURE)",
    },
    {
        "name": "5) JSON con fecha vieja (motor no corrió hoy)",
        "data": {"date": "2026-04-20", "pick_gratuito": {"matchup": "X"}},
        "odds_ok": True,
        "expected_state": STATE_EXECUTION_FAILURE,
        "scenario": "Estado D (EXECUTION_FAILURE)",
    },
]

print("\n" + "═" * 60)
print("  VALIDACIÓN DE DETECCIÓN DE ESCENARIOS")
print("═" * 60)

all_ok = True
for case in cases:
    with patch("bot.telegram_bot._odds_json_is_usable", return_value=case["odds_ok"]):
        actual = detect_state(case["data"], TODAY)
    status = "✓" if actual == case["expected_state"] else "✗"
    if actual != case["expected_state"]:
        all_ok = False
    print(f"\n  {status} {case['name']}")
    print(f"      esperado: {case['expected_state']}")
    print(f"      obtenido: {actual}")
    print(f"      escenario: {case['scenario']}")

print("\n" + "═" * 60)
print(f"  {'✅ TODOS LOS CASOS PASARON' if all_ok else '❌ HAY FALLOS'}")
print("═" * 60 + "\n")

sys.exit(0 if all_ok else 1)
