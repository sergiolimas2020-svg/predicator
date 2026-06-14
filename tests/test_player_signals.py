from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.api_football.player_signals import extract_player_shot_signals


TEAM = 33


def _fx(fid, date_iso, status="FT"):
    return {
        "fixture": {"id": fid, "date": date_iso, "status": {"short": status}},
        "league": {"id": 39},
        "teams": {"home": {"id": TEAM}, "away": {"id": 99}},
    }


def _player(pid, name, minutes, total, on, substitute=False, pos="F"):
    return {
        "player": {"id": pid, "name": name},
        "statistics": [{
            "games": {
                "minutes": minutes,
                "position": pos,
                "substitute": substitute,
            },
            "shots": {"total": total, "on": on},
        }],
    }


def _payload(players):
    return {"response": [{"team": {"id": TEAM}, "players": players}]}


class FakeClient:
    def __init__(self, by_fixture):
        self.by_fixture = by_fixture
        self.calls = []

    def get_fixture_players(self, fixture, team=None):
        self.calls.append((fixture, team))
        return self.by_fixture.get(fixture, {"response": []})


def test_extract_player_shot_signals_averages_by_player():
    form = [_fx(1, "2026-05-10"), _fx(2, "2026-05-03"), _fx(3, "2026-04-26")]
    client = FakeClient({
        1: _payload([_player(7, "Striker A", 90, 4, 2), _player(8, "Winger B", 70, 2, 1)]),
        2: _payload([_player(7, "Striker A", 80, 2, 1), _player(8, "Winger B", 20, 1, 0)]),
        3: _payload([_player(7, "Striker A", 10, 5, 4)]),  # minutos bajos: se ignora
    })

    out = extract_player_shot_signals(client, TEAM, form, lookback=5)

    assert out["n_fixtures"] == 3
    striker = next(p for p in out["players"] if p["player_id"] == 7)
    assert striker["appearances"] == 2
    assert striker["starts"] == 2
    assert striker["minutes_avg"] == 85.0
    assert striker["shots_total_avg"] == 3.0
    assert striker["shots_on_target_avg"] == 1.5


def test_extract_player_shot_signals_handles_missing_data():
    out = extract_player_shot_signals(FakeClient({}), TEAM, [])
    assert out["players"] == []
    assert out["n_fixtures"] == 0
    assert "sin_form_data" in out["errors"]
