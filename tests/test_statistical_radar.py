"""Tests del radar estadístico (selector de mercado por probabilidad).

Verifican el contrato:
  - DNB/DC de selección con probabilidad alta aparecen en el radar.
  - DNB/DC de clubes siguen bloqueados (no se evalúan).
  - Señales bajo umbral se descartan (no hay pick).
  - No hay campos de EV/cuotas/Betplay en ningún lado.
"""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "statistical_radar", ROOT / "scripts" / "statistical_radar.py"
)
radar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(radar)

gp = radar.gp
SEL = gp.WORLD_CUP_LEAGUE
CLUB = "Premier League"


def _probs(win_home, draw, lose, over_1_5):
    """Construye el dict que devolvería get_probabilities (valores 0–1)."""
    wl = win_home + lose
    return {
        "win_home": win_home, "draw": draw, "win_away": lose,
        "dnb_home": win_home / wl if wl else 0.0,
        "dnb_away": lose / wl if wl else 0.0,
        "dc_home": win_home + draw, "dc_away": lose + draw,
        "over_1_5": over_1_5, "over_2_5": 0.0,
        "favorite": "home" if win_home >= lose else "away",
        "nba": False,
    }


def _patch(monkeypatch, probs):
    monkeypatch.setattr(gp, "get_probabilities",
                        lambda *a, **k: probs)


def _forbidden_keys(obj):
    """Recolecta keys que huelan a EV/cuotas/Betplay en toda la estructura."""
    bad = []
    banned = ("ev", "cuota", "odds", "betplay", "bk_")
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(b in kl for b in banned):
                bad.append(k)
            bad += _forbidden_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            bad += _forbidden_keys(v)
    return bad


def test_dnb_seleccion_high_prob_appears_in_radar(monkeypatch):
    # win 60% (<62 no pasa), DNB 75% (≥72 pasa). Recomendado = DNB.
    _patch(monkeypatch, _probs(0.60, 0.20, 0.20, 0.50))
    r = radar.evaluate_match_radar(SEL, "Canada", "Bosnia", {}, {})
    dnb = next(m for m in r["markets"] if m["market"].startswith("DNB"))
    assert dnb["passed"] is True
    assert dnb["tier"] == "radar_only"
    assert r["recommended"]["market"].startswith("DNB")


def test_dc_seleccion_high_prob_appears_in_radar(monkeypatch):
    # DC = win+draw = 0.85 (≥80 pasa).
    _patch(monkeypatch, _probs(0.55, 0.30, 0.15, 0.50))
    r = radar.evaluate_match_radar(SEL, "USA", "Paraguay", {}, {})
    dc = next(m for m in r["markets"] if m["market"] == "Doble oportunidad")
    assert dc["passed"] is True
    assert dc["tier"] == "radar_only"


def test_dnb_dc_blocked_for_clubs(monkeypatch):
    # Mismas probas altas, pero liga de CLUBES: DNB/DC ni se evalúan.
    _patch(monkeypatch, _probs(0.60, 0.20, 0.20, 0.50))
    r = radar.evaluate_match_radar(CLUB, "Arsenal", "Chelsea", {}, {})
    names = [m["market"] for m in r["markets"]]
    assert not any(n.startswith("DNB") for n in names)
    assert "Doble oportunidad" not in names
    # Solo mercados permitidos para clubes
    assert names == ["Victoria directa", "Over 1.5 goles"]


def test_under_threshold_is_discarded(monkeypatch):
    # Partido parejo: nada supera umbral → sin señal.
    _patch(monkeypatch, _probs(0.40, 0.30, 0.30, 0.45))
    r = radar.evaluate_match_radar(SEL, "Canada", "Bosnia", {}, {})
    assert r["status"] == "no_signal"
    assert r["recommended"] is None
    assert len(r["discarded"]) == len(r["markets"])


def test_no_ev_odds_betplay_fields(monkeypatch):
    _patch(monkeypatch, _probs(0.60, 0.20, 0.20, 0.80))
    r = radar.evaluate_match_radar(SEL, "Canada", "Bosnia", {}, {})
    assert _forbidden_keys(r) == []


def test_win_market_is_official_eligible(monkeypatch):
    # Victoria directa fuerte: oficial-elegible (aunque el radar no publica).
    _patch(monkeypatch, _probs(0.70, 0.15, 0.15, 0.60))
    r = radar.evaluate_match_radar(SEL, "Brasil", "Bolivia", {}, {})
    win = next(m for m in r["markets"] if m["market"] == "Victoria directa")
    assert win["passed"] is True
    assert win["tier"] == "official_eligible"
    assert r["recommended"]["market"] == "Victoria directa"
