import json, os, time, requests
from datetime import datetime, timedelta

API_KEY    = "50ae75b6ffda6c2ddfb182f715be3648"
HEADERS    = {"x-apisports-key": API_KEY}
BASE       = "https://v3.football.api-sports.io"
LEAGUE_ID  = 128  # Copa de la Liga Profesional Argentina
SEASON     = 2026
OUTPUT     = "static/argentina_stats.json"

def get_fixtures():
    r = requests.get(f"{BASE}/fixtures", headers=HEADERS,
        params={"league": LEAGUE_ID, "season": SEASON, "status": "FT"}, timeout=15)
    return r.json().get("response", [])

def get_stats(fixture_id):
    time.sleep(0.3)
    r = requests.get(f"{BASE}/fixtures/statistics", headers=HEADERS,
        params={"fixture": fixture_id}, timeout=15)
    return r.json().get("response", [])

print("📡 Obteniendo fixtures Argentina...")
fixtures = get_fixtures()
print(f"   ✅ {len(fixtures)} partidos terminados")

team_data = {}
for f in fixtures:
    fid  = f["fixture"]["id"]
    home = f["teams"]["home"]["name"]
    away = f["teams"]["away"]["name"]
    print(f"   ⚽ {home} vs {away}")
    stats = get_stats(fid)
    hc = ac = 0
    for team_stats in stats:
        na