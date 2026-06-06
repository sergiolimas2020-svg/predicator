"""
Tests de la agregación de córners (scrapers/corners.py) — función PURA, sin red.
Valida que los córners se separen correctamente por sede (local/visitante) y se
promedien por partido, en la estructura que espera el motor/frontend.
"""
from scrapers.corners import aggregate_corners


def test_aggregate_splits_home_and_away():
    matches = [
        # A local: 6 favor / 2 contra ; B visitante: 2 favor / 6 contra
        {"home": "A", "away": "B", "home_corners": 6, "away_corners": 2},
        # A local otra vez: 4 / 4
        {"home": "A", "away": "C", "home_corners": 4, "away_corners": 4},
        # A visitante: 3 favor / 5 contra
        {"home": "C", "away": "A", "home_corners": 5, "away_corners": 3},
    ]
    out = aggregate_corners(matches)
    a = out["A"]
    assert a["local"]["partidos"] == 2
    assert a["local"]["corners_favor"] == 5.0      # (6+4)/2
    assert a["local"]["corners_contra"] == 3.0     # (2+4)/2
    assert a["visitante"]["partidos"] == 1
    assert a["visitante"]["corners_favor"] == 3.0
    assert a["visitante"]["corners_contra"] == 5.0
    # B solo jugó de visitante
    assert out["B"]["visitante"]["corners_favor"] == 2.0
    assert out["B"]["local"]["partidos"] == 0


def test_aggregate_ignores_missing_corner_data():
    matches = [
        {"home": "A", "away": "B", "home_corners": None, "away_corners": 3},  # ignorado
        {"home": "A", "away": "B", "home_corners": 5, "away_corners": 1},
    ]
    out = aggregate_corners(matches)
    assert out["A"]["local"]["partidos"] == 1
    assert out["A"]["local"]["corners_favor"] == 5.0


def test_aggregate_structure_matches_frontend_contract():
    out = aggregate_corners([{"home": "A", "away": "B", "home_corners": 4, "away_corners": 2}])
    # El frontend lee corners.local.corners_favor / corners.visitante...
    for team in ("A", "B"):
        for side in ("local", "visitante"):
            assert set(out[team][side]) == {"partidos", "corners_favor", "corners_contra"}
