"""Contrato de picks oficiales — blindaje estadístico/API-Football.

Verifican que:
  - El motor está en modo estadístico puro (sin EV/cuotas inventadas).
  - Fútbol oficial requiere respaldo API-Football; NBA queda exenta.
  - Córners, Over 2.5, DNB y Doble Oportunidad NO entran a picks oficiales.
  - El Featured Pick respeta ambos guards.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers import generate_predictions as gp


# ── Modo estadístico ──

def test_statistical_only_mode_active():
    assert gp.STATISTICAL_ONLY_MODE is True


def test_confidence_fallback_is_publication_layer_for_statistical_picks():
    assert gp.CONF_PICK_ENABLED is True


# ── Guard de fuente: fútbol oficial requiere API-Football ──

def test_api_football_guard_active_in_contract():
    assert gp.REQUIRE_API_FOOTBALL_FOR_FOOTBALL_PICKS is True


def test_guard_rejects_football_pick_without_api_football():
    assert not gp._has_api_football_backing({"nba": False, "api_football_backed": False})
    assert not gp._has_api_football_backing({"nba": False})
    assert not gp._has_api_football_backing(None)


def test_guard_accepts_football_pick_with_api_football():
    assert gp._has_api_football_backing({"nba": False, "api_football_backed": True})


def test_guard_exempts_nba_picks():
    assert gp._has_api_football_backing({"nba": True, "api_football_backed": False})


# ── Mercados deshabilitados como picks oficiales ──

def test_disabled_markets_are_flagged():
    assert gp._is_disabled_official_market("Apuesta sin empate: Equipo A")   # DNB
    assert gp._is_disabled_official_market("Doble oportunidad: Equipo A")    # DC
    assert gp._is_disabled_official_market("Over 8.5 córners")
    assert gp._is_disabled_official_market("Over 2.5 goles")


def test_allowed_markets_not_flagged():
    assert not gp._is_disabled_official_market("Gana Equipo A")      # 1X2
    assert not gp._is_disabled_official_market("Over 1.5 goles")     # Over 1.5 vive


def test_corners_and_over25_disabled_in_confidence_ladder():
    assert gp.CONF_CORNERS_ENABLED is False
    assert gp.CONF_OVER25_ENABLED is False


# ── Featured Pick respeta los guards ──

def _featured_pick(api_backed, label="Gana Equipo A"):
    evaluated = [{
        "league": "Serie A",
        "home": "Equipo A", "away": "Equipo B",
        "nba": False,
        "api_football_backed": api_backed,
        "market_type": "h2h",
        "label": label,
        "prob_adjusted": 80.0,
        "confidence_factor": 1.0,
        "bk_odds": None, "ev_adjusted": None,
    }]
    return gp._build_featured_pick_output(evaluated, {}, "2026-06-11")


def test_featured_pick_excludes_football_without_api_football():
    assert _featured_pick(api_backed=False) is None


def test_featured_pick_allows_football_with_api_football():
    out = _featured_pick(api_backed=True)
    assert out is not None
    assert out["matchup"] == "Equipo A vs Equipo B"


def test_featured_pick_excludes_dnb_and_double_chance():
    assert _featured_pick(api_backed=True, label="Apuesta sin empate: Equipo A") is None
    assert _featured_pick(api_backed=True, label="Doble oportunidad: Equipo A") is None
