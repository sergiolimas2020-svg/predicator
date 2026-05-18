"""
Tests del módulo de indicadores de peligro (tiros a puerta + corners).

Mockean el cliente de API-Football — no hacen requests reales.
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.api_football.danger_signals import (
    extract_danger_signals, _stat_value, _domestic_recent,
)
from scrapers import generate_predictions as gp


DOMESTIC = 39   # liga doméstica (no en INTL_LEAGUE_IDS)
INTL = 2        # Champions League


def _fx(fid, date_iso, league_id=DOMESTIC, status="FT"):
    return {
        "fixture": {"id": fid, "date": date_iso, "status": {"short": status}},
        "league": {"id": league_id},
    }


def _stats_payload(team_id, shots, corners):
    stats = []
    if shots is not None:
        stats.append({"type": "Shots on Goal", "value": shots})
    if corners is not None:
        stats.append({"type": "Corner Kicks", "value": corners})
    return {"response": [{"team": {"id": team_id}, "statistics": stats}]}


class FakeClient:
    """Cliente mock: devuelve estadísticas pre-cargadas por fixture id."""
    def __init__(self, by_fixture):
        self._by = by_fixture
        self.calls = []

    def get_fixture_statistics(self, fixture, team=None):
        self.calls.append(fixture)
        return self._by.get(fixture, {"response": []})


class TestStatValue(unittest.TestCase):
    def test_finds_by_substring(self):
        stats = [{"type": "Shots on Goal", "value": 6},
                 {"type": "Corner Kicks", "value": 9}]
        self.assertEqual(_stat_value(stats, "shots on goal"), 6.0)
        self.assertEqual(_stat_value(stats, "corner"), 9.0)

    def test_parses_percentage(self):
        self.assertEqual(_stat_value([{"type": "Ball Possession", "value": "55%"}],
                                     "possession"), 55.0)

    def test_none_when_missing(self):
        self.assertIsNone(_stat_value([], "corner"))
        self.assertIsNone(_stat_value([{"type": "Corner Kicks", "value": None}],
                                      "corner"))


class TestDomesticRecent(unittest.TestCase):
    def test_excludes_international_and_unfinished(self):
        form = [
            _fx(1, "2026-05-09"),
            _fx(2, "2026-05-02", league_id=INTL),       # internacional → fuera
            _fx(3, "2026-04-25", status="NS"),          # no terminado → fuera
            _fx(4, "2026-04-18"),
        ]
        out = _domestic_recent(form, lookback=5)
        self.assertEqual([f["fixture"]["id"] for f in out], [1, 4])

    def test_orders_desc_and_limits(self):
        form = [_fx(i, f"2026-04-{i:02d}") for i in range(1, 11)]
        out = _domestic_recent(form, lookback=3)
        self.assertEqual([f["fixture"]["id"] for f in out], [10, 9, 8])


class TestExtractDangerSignals(unittest.TestCase):
    def test_empty_form(self):
        out = extract_danger_signals(FakeClient({}), 33, [])
        self.assertEqual(out["n_fixtures"], 0)
        self.assertIsNone(out["shots_on_target_avg"])
        self.assertIn("sin_form_data", out["errors"])

    def test_averages_shots_and_corners(self):
        form = [_fx(1, "2026-05-09"), _fx(2, "2026-05-02"), _fx(3, "2026-04-25")]
        client = FakeClient({
            1: _stats_payload(33, shots=6, corners=8),
            2: _stats_payload(33, shots=4, corners=6),
            3: _stats_payload(33, shots=5, corners=10),
        })
        out = extract_danger_signals(client, 33, form, lookback=5)
        self.assertEqual(out["n_fixtures"], 3)
        self.assertAlmostEqual(out["shots_on_target_avg"], 5.0)   # (6+4+5)/3
        self.assertAlmostEqual(out["corners_avg"], 8.0)           # (8+6+10)/3

    def test_skips_international_fixtures(self):
        form = [_fx(1, "2026-05-09"), _fx(2, "2026-05-02", league_id=INTL)]
        client = FakeClient({
            1: _stats_payload(33, shots=7, corners=5),
            2: _stats_payload(33, shots=99, corners=99),  # no debe usarse
        })
        out = extract_danger_signals(client, 33, form, lookback=5)
        self.assertEqual(out["n_fixtures"], 1)
        self.assertEqual(out["shots_on_target_avg"], 7.0)
        self.assertEqual(client.calls, [1])  # solo pidió el fixture doméstico

    def test_lookback_limit(self):
        form = [_fx(i, f"2026-04-{i:02d}") for i in range(1, 9)]
        client = FakeClient({i: _stats_payload(33, shots=i, corners=i)
                             for i in range(1, 9)})
        out = extract_danger_signals(client, 33, form, lookback=5)
        self.assertEqual(out["n_fixtures"], 5)  # solo los 5 más recientes


class TestDangerIndex(unittest.TestCase):
    def test_none_when_no_data(self):
        self.assertIsNone(gp.danger_index(None))
        self.assertIsNone(gp.danger_index({"shots_on_target_avg": None,
                                           "corners_avg": None}))

    def test_combines_shots_and_corners(self):
        idx = gp.danger_index({"shots_on_target_avg": 5.0, "corners_avg": 8.0})
        self.assertEqual(idx, 9.0)   # 5.0 + 0.5*8.0

    def test_disabled_by_default(self):
        # Preparación: no debe estar activo todavía
        self.assertFalse(gp.DANGER_SIGNALS_ENABLED)


if __name__ == "__main__":
    unittest.main()
