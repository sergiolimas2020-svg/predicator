"""
Tests del Filtro 1 (forma reciente del favorito) en generate_predictions.py.

NO depende de odds.json, API-Football ni red. Mockea estructuras mínimas.
"""
from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers import generate_predictions as gp


# ─────────────────────────────────────── helpers para construir fixtures

def _fixture(date_iso, league_id, home_id, away_id, home_winner, away_winner,
             status="FT"):
    return {
        "fixture": {"date": date_iso, "status": {"short": status}},
        "league":  {"id": league_id},
        "teams": {
            "home": {"id": home_id, "winner": home_winner},
            "away": {"id": away_id, "winner": away_winner},
        },
    }


def _ep(home="Arsenal", away="Chelsea", league="Premier League",
        nba=False, label="Arsenal", base_pick="Arsenal",
        bk_odds=1.85, ev=10.0, prob=65.0):
    """Fabrica un evaluated_pick mínimo con tupla raw consistente."""
    raw = (
        0.0,            # 0  vs
        league,         # 1  league
        home,           # 2  home
        {},             # 3  hd
        away,           # 4  away
        {},             # 5  ad
        nba,            # 6  nba flag
        label,          # 7  display_pick
        prob,           # 8  display_prob
        None,           # 9  cuota_justa
        "medio",        # 10 value_level
        prob,           # 11 base_prob
        base_pick,      # 12 base_pick
        bk_odds,        # 13 bk_odds
        1.0,            # 14 cf
        {},             # 15 best_eval
        [],             # 16 all_evals
        {},             # 17 ext_ctx
    )
    return {
        "raw":              raw,
        "league":           league,
        "home":             home,
        "away":             away,
        "nba":              nba,
        "label":            label,
        "bk_odds":          bk_odds,
        "ev_adjusted":      ev,
        "prob_adjusted":    prob,
        "value_score":      4.0,
        "confidence_factor": 1.0,
        "stats_complete":   True,
        "market_type":      "h2h",
        "reason":           "ok",
        "all_evals":        [],
    }


# ─────────────────────────────────────── _rf_favored_team

class TestFavoredTeam(unittest.TestCase):
    def test_over_returns_none(self):
        self.assertIsNone(gp._rf_favored_team("Over 2.5 goles", None))
        self.assertIsNone(gp._rf_favored_team("Over 1.5 goles", "Arsenal"))

    def test_under_returns_none(self):
        self.assertIsNone(gp._rf_favored_team("Under 2.5 goles", None))

    def test_doble_oportunidad_extracts_team(self):
        self.assertEqual(
            gp._rf_favored_team("Doble oportunidad: Arsenal", None),
            "Arsenal",
        )

    def test_dnb_extracts_team(self):
        self.assertEqual(
            gp._rf_favored_team("Apuesta sin empate: Real Madrid", None),
            "Real Madrid",
        )

    def test_uses_base_pick_when_present(self):
        self.assertEqual(gp._rf_favored_team("Arsenal", "Arsenal"), "Arsenal")

    def test_direct_team_label_is_team(self):
        self.assertEqual(gp._rf_favored_team("Boca Juniors", None), "Boca Juniors")


# ─────────────────────────────────────── _rf_count_wins_domestic

class TestCountWins(unittest.TestCase):
    HOME_LEAGUE = 39  # Premier League domestic id (no en INTL_LEAGUE_IDS)
    INTL_LEAGUE = 2   # Champions League — debe ser excluido

    def test_returns_none_if_empty(self):
        self.assertIsNone(gp._rf_count_wins_domestic([], 33))
        self.assertIsNone(gp._rf_count_wins_domestic(None, 33))

    def test_returns_none_if_insufficient_domestic(self):
        # 4 partidos domesticos + 6 de Champions → solo 4 domesticos < 5
        form = (
            [_fixture(f"2026-04-{20-i:02d}", self.HOME_LEAGUE, 33, 99, True, False)
             for i in range(4)]
            + [_fixture(f"2026-04-{10-i:02d}", self.INTL_LEAGUE, 33, 99, True, False)
               for i in range(6)]
        )
        self.assertIsNone(gp._rf_count_wins_domestic(form, 33))

    def test_counts_wins_team_is_home(self):
        form = [
            _fixture("2026-05-09", self.HOME_LEAGUE, 33, 99, True, False),   # W
            _fixture("2026-05-02", self.HOME_LEAGUE, 33, 99, False, True),   # L
            _fixture("2026-04-25", self.HOME_LEAGUE, 33, 99, True, False),   # W
            _fixture("2026-04-18", self.HOME_LEAGUE, 33, 99, None, None),    # D
            _fixture("2026-04-11", self.HOME_LEAGUE, 33, 99, True, False),   # W
        ]
        wins, n, form_str = gp._rf_count_wins_domestic(form, 33)
        self.assertEqual(wins, 3)
        self.assertEqual(n, 5)
        self.assertEqual(form_str, "WLWDW")

    def test_counts_wins_team_is_away(self):
        form = [
            _fixture("2026-05-09", self.HOME_LEAGUE, 99, 33, False, True),   # W
            _fixture("2026-05-02", self.HOME_LEAGUE, 99, 33, True, False),   # L
            _fixture("2026-04-25", self.HOME_LEAGUE, 99, 33, None, None),    # D
            _fixture("2026-04-18", self.HOME_LEAGUE, 99, 33, None, None),    # D
            _fixture("2026-04-11", self.HOME_LEAGUE, 99, 33, False, True),   # W
        ]
        wins, n, form_str = gp._rf_count_wins_domestic(form, 33)
        self.assertEqual(wins, 2)
        self.assertEqual(form_str, "WLDDW")

    def test_excludes_international(self):
        form = (
            # 5 wins en Champions League — deben EXCLUIRSE
            [_fixture(f"2026-05-{9-i:02d}", self.INTL_LEAGUE, 33, 99, True, False)
             for i in range(5)]
            # 5 partidos domesticos: 1W 4L
            + [_fixture(f"2026-04-{20-i:02d}", self.HOME_LEAGUE, 33, 99,
                        i == 0, not (i == 0))
               for i in range(5)]
        )
        wins, n, _ = gp._rf_count_wins_domestic(form, 33)
        self.assertEqual(wins, 1)  # Solo cuenta los 5 domesticos
        self.assertEqual(n, 5)

    def test_skips_non_terminated(self):
        # 4 partidos FT + 1 NS (no terminado) → solo 4 elegibles → None
        form = [
            _fixture("2026-05-09", self.HOME_LEAGUE, 33, 99, True, False, status="FT"),
            _fixture("2026-05-02", self.HOME_LEAGUE, 33, 99, True, False, status="FT"),
            _fixture("2026-04-25", self.HOME_LEAGUE, 33, 99, True, False, status="FT"),
            _fixture("2026-04-18", self.HOME_LEAGUE, 33, 99, True, False, status="FT"),
            _fixture("2026-04-11", self.HOME_LEAGUE, 33, 99, None, None, status="NS"),
        ]
        self.assertIsNone(gp._rf_count_wins_domestic(form, 33))


# ─────────────────────────────────────── _rf_apply_filter (integración)

class TestApplyFilter(unittest.TestCase):
    def setUp(self):
        # data file path mock
        self.tmp_data = {
            (gp._norm("Arsenal"), gp._norm("Chelsea")): {
                "home": "Arsenal", "away": "Chelsea",
                "home_id": 33, "away_id": 49,
                "home_form": [
                    # Arsenal: 1W en últimos 5 → debería rechazarse
                    _fixture("2026-05-09", 39, 33, 99, False, True),  # L
                    _fixture("2026-05-02", 39, 33, 99, True, False),  # W
                    _fixture("2026-04-25", 39, 33, 99, False, True),  # L
                    _fixture("2026-04-18", 39, 33, 99, None, None),   # D
                    _fixture("2026-04-11", 39, 33, 99, False, True),  # L
                ],
                "away_form": [
                    # Chelsea: 4W → no rechazaría
                    _fixture("2026-05-09", 39, 99, 49, False, True),  # W
                    _fixture("2026-05-02", 39, 49, 99, True, False),  # W
                    _fixture("2026-04-25", 39, 49, 99, True, False),  # W
                    _fixture("2026-04-18", 39, 99, 49, False, True),  # W
                    _fixture("2026-04-11", 39, 49, 99, None, None),   # D
                ],
            }
        }

    def _patched_load(self, *_args, **_kw):
        return self.tmp_data

    def test_filter_disabled_returns_empty(self):
        with patch.object(gp, "USE_RECENT_FORM_FILTER", False):
            picks = [_ep()]
            rej = gp._rf_apply_filter(picks, "2026-05-12")
            self.assertEqual(rej, [])
            # No marca picks
            self.assertNotIn("_rf_rejected", picks[0])

    def test_no_data_means_no_filtering(self):
        # _rf_load_data devuelve {} → conservador
        with patch.object(gp, "_rf_load_data", return_value={}):
            picks = [_ep()]
            rej = gp._rf_apply_filter(picks, "2026-05-12")
            self.assertEqual(rej, [])

    def test_rejects_team_with_low_form(self):
        with patch.object(gp, "_rf_load_data", side_effect=self._patched_load):
            ep = _ep(home="Arsenal", away="Chelsea", base_pick="Arsenal",
                     label="Arsenal")
            rej = gp._rf_apply_filter([ep], "2026-05-12")
            self.assertEqual(len(rej), 1)
            self.assertTrue(ep["_rf_rejected"])
            self.assertEqual(ep["_rf_wins"], 1)
            self.assertEqual(ep["_rf_form"], "LWLDL")

    def test_publishes_team_with_good_form(self):
        with patch.object(gp, "_rf_load_data", side_effect=self._patched_load):
            ep = _ep(home="Arsenal", away="Chelsea", base_pick="Chelsea",
                     label="Chelsea")
            rej = gp._rf_apply_filter([ep], "2026-05-12")
            self.assertEqual(len(rej), 0)
            self.assertFalse(ep["_rf_rejected"])
            self.assertEqual(ep["_rf_wins"], 4)

    def test_skip_nba(self):
        with patch.object(gp, "_rf_load_data", side_effect=self._patched_load):
            ep = _ep(nba=True, league="NBA")
            rej = gp._rf_apply_filter([ep], "2026-05-12")
            self.assertEqual(len(rej), 0)
            self.assertFalse(ep["_rf_rejected"])

    def test_skip_over_under(self):
        with patch.object(gp, "_rf_load_data", side_effect=self._patched_load):
            ep = _ep(home="Arsenal", away="Chelsea",
                     label="Over 2.5 goles", base_pick="Arsenal")
            rej = gp._rf_apply_filter([ep], "2026-05-12")
            self.assertEqual(len(rej), 0)
            self.assertFalse(ep["_rf_rejected"])

    def test_skip_when_match_not_in_data(self):
        with patch.object(gp, "_rf_load_data", side_effect=self._patched_load):
            ep = _ep(home="Boca Juniors", away="River Plate",
                     base_pick="Boca Juniors", label="Boca Juniors")
            rej = gp._rf_apply_filter([ep], "2026-05-12")
            self.assertEqual(len(rej), 0)
            self.assertFalse(ep["_rf_rejected"])

    def test_doble_oportunidad_uses_team_name(self):
        with patch.object(gp, "_rf_load_data", side_effect=self._patched_load):
            ep = _ep(home="Arsenal", away="Chelsea",
                     label="Doble oportunidad: Arsenal", base_pick="Arsenal")
            rej = gp._rf_apply_filter([ep], "2026-05-12")
            # Arsenal sigue teniendo solo 1W → rechazado
            self.assertEqual(len(rej), 1)
            self.assertTrue(ep["_rf_rejected"])


if __name__ == "__main__":
    unittest.main()
