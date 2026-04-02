"""
Obtiene cuotas reales de bookmakers via The Odds API.
Guarda las mejores cuotas disponibles en static/odds.json.
"""
import json, os, requests
from pathlib import Path
from datetime import datetime, timezone

API_KEY = os.environ.get("ODDS_API_KEY", "")
BASE    = "https://api.the-odds-api.com/v4/sports"
OUT     = Path("static/odds.json")

# Ligas soportadas por la API → nombre interno
LEAGUES = {
    "soccer_argentina_primera_division": "Liga Argentina",
    "soccer_epl":                        "Premier League",
    "soccer_spain_la_liga":              "La Liga",
    "soccer_italy_serie_a":              "Serie A",
    "soccer_germany_bundesliga":         "Bundesliga",
    "soccer_france_ligue_one":           "Ligue 1",
    "soccer_brazil_campeonato":          "Brasileirao",
    "soccer_turkey_super_league":        "Super Lig",
    "soccer_uefa_champs_league":         "Champions League",
    "basketball_nba":                    "NBA",
}

def best_odds(bookmakers, outcome_name):
    """Devuelve la mejor cuota disponible para un resultado dado (line shopping)."""
    best = 1.0
    for bk in bookmakers:
        for mkt in bk.get("markets", []):
            for o in mkt.get("outcomes", []):
                if o["name"] == outcome_name and o["price"] > best:
                    best = o["price"]
    return round(best, 3) if best > 1.0 else None

def fetch_league(sport_key):
    url = f"{BASE}/{sport_key}/odds/"
    params = {
        "apiKey":      API_KEY,
        "regions":     "eu",
        "markets":     "h2h",
        "oddsFormat":  "decimal",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ERROR {sport_key}: {e}")
        return []

def main():
    if not API_KEY:
        print("ODDS_API_KEY no configurada — saltando fetch de cuotas")
        return

    all_odds = {}
    nba = False

    for sport_key, league_name in LEAGUES.items():
        print(f"  Fetching {league_name}...")
        events = fetch_league(sport_key)
        nba = sport_key == "basketball_nba"

        for e in events:
            home = e["home_team"]
            away = e["away_team"]
            date = e["commence_time"][:10]
            key  = f"{home}|{away}|{date}"

            win_home = best_odds(e["bookmakers"], home)
            win_away = best_odds(e["bookmakers"], away)
            draw     = best_odds(e["bookmakers"], "Draw") if not nba else None

            if win_home and win_away:
                all_odds[key] = {
                    "league":    league_name,
                    "home":      home,
                    "away":      away,
                    "date":      date,
                    "win_home":  win_home,
                    "win_away":  win_away,
                    "draw":      draw,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }

        print(f"    {sum(1 for v in all_odds.values() if v['league']==league_name)} partidos")

    OUT.write_text(json.dumps(all_odds, ensure_ascii=False, indent=2))
    print(f"\nCuotas guardadas: {len(all_odds)} partidos → {OUT}")

if __name__ == "__main__":
    main()
