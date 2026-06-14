import json
from datetime import datetime, timezone

import scripts.pipeline_health as health


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_selection_picks_do_not_require_club_daily_file(tmp_path, monkeypatch):
    daily = tmp_path / "static" / "predictions" / "daily_picks.json"
    api_dir = tmp_path / "static" / "api_football" / "data"
    wc_stats = tmp_path / "static" / "worldcup_stats.json"
    wc_fixtures = tmp_path / "static" / "worldcup_fixtures.json"

    _write_json(daily, {
        "date": "2026-06-14",
        "pick_gratuito": {
            "matchup": "Germany vs Curaçao",
            "league": "Mundial 2026",
            "market": "Over 2.5 goles",
            "tipo": "pick_gratuito",
        },
        "picks_suscripcion": [],
    })
    _write_json(wc_stats, {"Germany": {}, "Curaçao": {}})
    _write_json(wc_fixtures, [{
        "date": datetime(2026, 6, 14, 17, tzinfo=timezone.utc).isoformat(),
        "home": "Germany",
        "away": "Curaçao",
    }])

    monkeypatch.setattr(health, "DAILY_PATH", daily)
    monkeypatch.setattr(health, "API_FOOTBALL_DIR", api_dir)
    monkeypatch.setattr(health, "WORLD_CUP_STATS_PATH", wc_stats)
    monkeypatch.setattr(health, "WORLD_CUP_FIXTURES_PATH", wc_fixtures)

    errors, warnings = health.check_api_football("2026-06-14")
    assert errors == []
    assert "no club picks require" in " ".join(warnings)

    errors, warnings = health.check_selection_backing("2026-06-14")
    assert errors == []
    assert "Mundial 2026 backing OK" in " ".join(warnings)


def test_club_picks_still_require_api_football_daily_file(tmp_path, monkeypatch):
    daily = tmp_path / "static" / "predictions" / "daily_picks.json"
    api_dir = tmp_path / "static" / "api_football" / "data"
    _write_json(daily, {
        "date": "2026-06-14",
        "pick_gratuito": {
            "matchup": "Team A vs Team B",
            "league": "Premier League",
            "market": "Over 2.5 goles",
            "tipo": "pick_gratuito",
        },
        "picks_suscripcion": [],
    })

    monkeypatch.setattr(health, "DAILY_PATH", daily)
    monkeypatch.setattr(health, "API_FOOTBALL_DIR", api_dir)

    errors, _ = health.check_api_football("2026-06-14")
    assert len(errors) == 1
    assert "club pick" in errors[0]
