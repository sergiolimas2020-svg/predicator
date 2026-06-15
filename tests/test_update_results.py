from scrapers.update_results import ESPN_SPORT_MAP, check_acerto, find_result


def test_selection_leagues_have_espn_result_sources():
    assert ESPN_SPORT_MAP["Mundial 2026"] == "soccer/fifa.world"
    assert ESPN_SPORT_MAP["Amistoso Selección"] == "soccer/fifa.friendly"


def test_goal_market_results_are_closed_from_score():
    result = {
        "home_score": 2,
        "away_score": 1,
        "home_name": "Germany",
        "away_name": "Curaçao",
    }

    assert check_acerto("Over 1.5 goles", result, nba=False) is True
    assert check_acerto("Over 2.5 goles", result, nba=False) is True
    assert check_acerto("Over 2.5 goles", {**result, "home_score": 1}, nba=False) is False


def test_find_result_accepts_neutral_fixture_reversed_order():
    result = {
        "home_score": 1,
        "away_score": 2,
        "home_name": "Tunisia",
        "away_name": "Sweden",
    }
    results = {("tunisia", "sweden"): result}

    assert find_result(results, "Sweden", "Tunisia") == result
