"""Contrato de picks oficiales — blindaje estadístico/API-Football.

Verifican que:
  - El motor está en modo estadístico puro (sin EV/cuotas inventadas).
  - Fútbol oficial requiere respaldo API-Football; NBA queda exenta.
  - DNB y Doble Oportunidad siguen bloqueados en clubes.
  - Córners, tiros a puerta y Over 2.5 pueden entrar por la escalera alternativa.
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


# ── Política de mercados oficiales ──

def test_disabled_markets_are_flagged():
    assert gp._is_disabled_official_market("Apuesta sin empate: Equipo A")   # DNB
    assert gp._is_disabled_official_market("Doble oportunidad: Equipo A")    # DC


def test_allowed_markets_not_flagged():
    assert not gp._is_disabled_official_market("Gana Equipo A")      # 1X2
    assert not gp._is_disabled_official_market("Over 1.5 goles")     # Over 1.5 vive
    assert not gp._is_disabled_official_market("Over 8.5 córners")
    assert not gp._is_disabled_official_market("Over 2.5 goles")
    assert not gp._is_disabled_official_market("Over 7.5 tiros a puerta")


def test_selection_dnb_and_double_chance_are_allowed():
    assert not gp._is_disabled_official_market(
        "Equipo A sin empate (DNB)", gp.WORLD_CUP_LEAGUE
    )
    assert not gp._is_disabled_official_market(
        "Equipo A o empate (Doble Oportunidad)", gp.WORLD_CUP_LEAGUE
    )


def test_alternative_markets_enabled_in_confidence_ladder():
    assert gp.CONF_CORNERS_ENABLED is True
    assert gp.CONF_OVER25_ENABLED is True
    assert gp.CONF_SHOTS_ENABLED is True
    assert gp.CONF_PLAYER_SHOTS_ENABLED is True


def test_player_shot_market_requires_api_player_data():
    hd = {"position": {"partidos": 10, "ganados": 5, "goles_favor": 15, "goles_contra": 10}}
    ad = {"position": {"partidos": 10, "ganados": 4, "goles_favor": 12, "goles_contra": 11}}
    matches = [("Liga Colombiana", "Home FC", "Away FC", hd, ad, False)]
    danger = {
        (gp._norm("Home FC"), gp._norm("Away FC")): {
            "home_player_shots": {
                "n_fixtures": 4,
                "players": [{
                    "player_id": 9,
                    "name": "Delantero A",
                    "position": "F",
                    "appearances": 4,
                    "starts": 4,
                    "minutes_avg": 78.0,
                    "shots_total_avg": 3.2,
                    "shots_on_target_avg": 1.1,
                }],
            },
            "away_player_shots": {"n_fixtures": 0, "players": []},
        }
    }
    picks = gp._select_player_shot_picks(matches, danger)
    assert picks
    assert "Delantero A" in picks[0][0]
    assert picks[0][2][15]["reason"] == "confianza_player_shots"


def test_player_shot_market_does_not_publish_without_player_data():
    hd = {"position": {"partidos": 10}}
    ad = {"position": {"partidos": 10}}
    matches = [("Liga Colombiana", "Home FC", "Away FC", hd, ad, False)]
    assert gp._select_player_shot_picks(matches, {}) == []


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
