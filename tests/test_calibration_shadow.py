"""Tests del artefacto SHADOW de calibración por mercado.

Verifican los invariantes del contrato (no la "mejora" de probabilidades):
  - Mercados deshabilitados NUNCA se proponen, ni con datos perfectos.
  - Muestra insuficiente → no se propone; se mantiene fallback sin calibrar.
  - Solo hay `proposed_calibrator` cuando el estado es "proposed".
  - El shadow no activa nada en producción (no toca calibrator.json).
"""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "calibration_shadow", ROOT / "scripts" / "calibration_shadow.py"
)
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)


def _overconfident_monotonic(n_per_band=20):
    """Datos monótonos pero sobreconfiados: prob alta→acierto medio.
    f mayor implica acierto mayor (monótono), así que A<0 es posible."""
    pairs = []
    pairs += [(0.85, 1)] * (n_per_band * 6 // 10) + [(0.85, 0)] * (n_per_band * 4 // 10)
    pairs += [(0.55, 1)] * (n_per_band * 5 // 10) + [(0.55, 0)] * (n_per_band * 5 // 10)
    return pairs


def test_active_and_disabled_markets_are_disjoint_and_complete():
    assert cs.ACTIVE_MARKETS.isdisjoint(cs.DISABLED_MARKETS)
    assert cs.DISABLED_MARKETS == {"corners", "over_2_5", "draw_no_bet", "double_chance"}


def test_disabled_market_never_proposed_even_with_perfect_data():
    # Datos "perfectos" (alta separación) en un mercado deshabilitado:
    # debe seguir fuera, sin propuesta de calibrador.
    perfect = [(0.9, 1)] * 30 + [(0.1, 0)] * 30
    for market in cs.DISABLED_MARKETS:
        res = cs._analyze_market(market, perfect)
        assert res["status"] == "disabled_market"
        assert res["proposed_calibrator"] is None


def test_insufficient_sample_keeps_uncalibrated_fallback():
    small = [(0.7, 1)] * 5 + [(0.7, 0)] * 4  # n=9 < MIN_CALIBRATION_SAMPLES
    res = cs._analyze_market("winner", small)
    assert res["status"] == "insufficient_sample"
    assert res["proposed_calibrator"] is None


def test_active_market_runs_full_gate_and_is_monotonic_when_expected():
    res = cs._analyze_market("winner", _overconfident_monotonic())
    assert res["n"] >= cs.MIN_CALIBRATION_SAMPLES
    assert res["A"] is not None
    assert res["valid_monotonic"] is True  # A < 0
    # El gate decide; solo hay calibrador propuesto si el estado es "proposed".
    if res["status"] == "proposed":
        assert res["proposed_calibrator"] == {"A": res["A"], "B": res["B"]}
    else:
        assert res["status"] in {"rejected_no_cv_improvement", "cv_unavailable"}
        assert res["proposed_calibrator"] is None


def test_proposed_calibrator_only_when_status_proposed():
    for market in cs.ACTIVE_MARKETS:
        res = cs._analyze_market(market, _overconfident_monotonic())
        if res["proposed_calibrator"] is not None:
            assert res["status"] == "proposed"


def test_shadow_does_not_enable_production_calibrator():
    # El motor solo lee static/calibrator.json; el shadow es otro archivo.
    assert cs.SHADOW_JSON.name == "calibration_shadow.json"
    assert cs.SHADOW_JSON.name != "calibrator.json"
