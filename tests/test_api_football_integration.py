"""Guard API-Football en la capa de confianza (picks oficiales de fútbol).

La capa de confianza es el camino de publicación estadística cuando no hay
EV/cuotas. Un pick de fútbol sin respaldo API-Football NO debe salir de ella.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers import generate_predictions as gp


def _internal_team(games, wins, gf, ga, api=False):
    return {
        "position": {
            "posicion": 4,
            "partidos": games,
            "ganados": wins,
            "empatados": 1,
            "perdidos": games - wins - 1,
            "goles_favor": gf,
            "goles_contra": ga,
            "diferencia": gf - ga,
        },
        "api_football_source": api,
    }


def _evaluated_pick(api=False):
    hd = _internal_team(10, 7, 22, 9, api=api)
    ad = _internal_team(10, 2, 9, 22, api=api)
    raw = (
        0.0, "Liga Colombiana", "Home FC", hd, "Away FC", ad, False,
        "Home FC", 70.0, None, "estadistico", 70.0, "Home FC",
        None, 1.0, {}, [], {},
    )
    return {
        "raw": raw,
        "league": "Liga Colombiana",
        "home": "Home FC",
        "away": "Away FC",
        "nba": False,
        "confidence_factor": 1.0,
        "api_football_backed": api,
    }


def test_confidence_ladder_requires_api_football_for_football_picks(monkeypatch):
    monkeypatch.setattr(gp, "CONF_MAX_PROB", 99.0)

    assert gp.REQUIRE_API_FOOTBALL_FOR_FOOTBALL_PICKS is True
    # Sin respaldo API-Football: la capa de confianza no publica.
    assert gp._select_confidence_picks([_evaluated_pick(api=False)]) == []

    # Con respaldo: sí publica una señal estadística.
    picks = gp._select_confidence_picks([_evaluated_pick(api=True)])
    assert len(picks) == 1
    assert picks[0][2][15]["reason"] == "confianza"
