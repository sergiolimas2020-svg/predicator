"""
Tests de las funciones puras del scraper unificado (scrapers/apifootball_stats.py).
Sin red: validan el mapeo de /standings → position, y el cálculo de goles
over/under + BTS, en el formato exacto que espera el motor.
"""
from scrapers.apifootball_stats import (
    compute_positions, compute_goals, fixtures_to_team_matches,
)


def test_compute_positions_from_matches():
    # A: gana, gana, empata → 7 pts ; B: pierde, empata → 1 pt
    tm = {
        "A": [{"gf": 2, "ga": 0}, {"gf": 1, "ga": 0}, {"gf": 1, "ga": 1}],
        "B": [{"gf": 0, "ga": 2}, {"gf": 1, "ga": 1}],
    }
    pos = compute_positions(tm)
    assert pos["A"]["partidos"] == 3 and pos["A"]["ganados"] == 2
    assert pos["A"]["empatados"] == 1 and pos["A"]["perdidos"] == 0
    assert pos["A"]["goles_favor"] == 4 and pos["A"]["goles_contra"] == 1
    assert pos["A"]["puntos"] == 7 and pos["A"]["diferencia"] == 3
    # A debe ir primero (más puntos)
    assert pos["A"]["posicion"] == 1 and pos["B"]["posicion"] == 2


def test_compute_goals_percentages_and_bts():
    # 4 partidos de A: totales 1, 3, 4, 0 ; both-scored en 2 de ellos
    matches = {"A": [
        {"gf": 1, "ga": 0},   # total 1
        {"gf": 2, "ga": 1},   # total 3, BTS
        {"gf": 2, "ga": 2},   # total 4, BTS
        {"gf": 0, "ga": 0},   # total 0
    ]}
    g = compute_goals(matches)["A"]
    assert g["over_1_5"] == "50%"   # totales >1.5: {3,4} → 2/4
    assert g["over_2_5"] == "50%"   # >2.5: {3,4} → 2/4
    assert g["over_3_5"] == "25%"   # >3.5: {4} → 1/4
    assert g["bts"] == "50%"        # 2/4
    # formato string con %
    assert all(v.endswith("%") for v in g.values())


def test_compute_goals_empty():
    g = compute_goals({"X": []})["X"]
    assert g == {"over_1_5": "0%", "over_2_5": "0%", "over_3_5": "0%", "bts": "0%"}


def test_fixtures_to_team_matches_splits_both_teams():
    fixtures = [
        {"teams": {"home": {"name": "A"}, "away": {"name": "B"}}, "goals": {"home": 2, "away": 1}},
        {"teams": {"home": {"name": "B"}, "away": {"name": "A"}}, "goals": {"home": 0, "away": 3}},
        {"teams": {"home": {"name": "A"}, "away": {"name": "B"}}, "goals": {"home": None, "away": 1}},  # ignorado
    ]
    tm = fixtures_to_team_matches(fixtures)
    assert tm["A"] == [{"gf": 2, "ga": 1}, {"gf": 3, "ga": 0}]
    assert tm["B"] == [{"gf": 1, "ga": 2}, {"gf": 0, "ga": 3}]
