"""
NBA SCRAPER — nba_api (oficial, gratis)
Temporada 2025-26 | Jugadores, stats, standings + corrección de traspasos
USO: .venv/bin/python scrapers/nba_scraper.py
"""

import json, os, time
from datetime import datetime

from nba_api.stats.endpoints import (
    leaguedashplayerstats,
    leaguestandingsv3,
    leaguedashteamstats,
    commonplayerinfo,
)
from nba_api.stats.static import teams as nba_teams_static

SEASON    = "2025-26"
OUTPUT    = "static/nba_stats.json"
OVER_LINE = 220.5

def safe_get(fn, retries=3, delay=1.5, **kwargs):
    for i in range(retries):
        try:
            time.sleep(delay)
            return fn(**kwargs).get_data_frames()[0]
        except Exception as e:
            print(f"   [reintento {i+1}] {e}")
    return None

print("=" * 55)
print(f"  NBA SCRAPER | nba_api | {SEASON}")
print("=" * 55)

# 1. Equipos
print("\n1. Cargando equipos NBA...")
all_teams = nba_teams_static.get_teams()
teams = {t["id"]: t for t in all_teams if t.get("is_active", True)}
print(f"   OK: {len(teams)} equipos")

# 2. Standings
print("\n2. Obteniendo standings...")
standings = {}
try:
    df_standings = safe_get(
        leaguestandingsv3.LeagueStandingsV3,
        season=SEASON,
        season_type="Regular Season",
    )
    if df_standings is not None:
        for _, row in df_standings.iterrows():
            tid = row["TeamID"]
            home_str = str(row.get("HOME", "0-0"))
            road_str = str(row.get("ROAD", "0-0"))
            standings[tid] = {
                "wins":            int(row.get("WINS", 0)),
                "losses":          int(row.get("LOSSES", 0)),
                "win_pct":         round(float(row.get("WinPCT", 0)) * 100, 1),
                "conference_rank": int(row.get("PlayoffRank", 0)),
                "home_wins":       int(home_str.split("-")[0]) if "-" in home_str else 0,
                "away_wins":       int(road_str.split("-")[0]) if "-" in road_str else 0,
            }
        print(f"   OK: {len(standings)} equipos con standings")
    else:
        print("   WARN: no se obtuvieron standings")
except Exception as e:
    print(f"   ERROR standings: {e}")

# 3. Stats de equipo
print("\n3. Obteniendo stats de equipos...")
team_stats = {}
team_over  = {}
team_under = {}
try:
    df_team = safe_get(
        leaguedashteamstats.LeagueDashTeamStats,
        season=SEASON,
        season_type_all_star="Regular Season",
    )
    if df_team is not None:
        for _, row in df_team.iterrows():
            tid = row["TEAM_ID"]
            gp  = max(int(row.get("GP", 1)), 1)          # partidos jugados (denominador)

            avg_pts    = float(row.get("PTS", 0)) / gp   # total → promedio
            plus_minus = float(row.get("PLUS_MINUS", 0)) / gp
            avg_pta    = round(avg_pts - plus_minus, 1)

            team_stats[tid] = {
                "avg_points":         round(avg_pts, 1),
                "avg_points_allowed": avg_pta,
                "avg_rebounds":       round(float(row.get("REB", 0)) / gp, 1),
                "avg_assists":        round(float(row.get("AST", 0)) / gp, 1),
                "avg_steals":         round(float(row.get("STL", 0)) / gp, 1),
                "avg_blocks":         round(float(row.get("BLK", 0)) / gp, 1),
                "avg_turnovers":      round(float(row.get("TOV", 0)) / gp, 1),
                "fg_pct":             round(float(row.get("FG_PCT", 0)) * 100, 1),
                "three_pct":          round(float(row.get("FG3_PCT", 0)) * 100, 1),
                "ft_pct":             round(float(row.get("FT_PCT", 0)) * 100, 1),
            }
            if avg_pts + avg_pta > OVER_LINE:
                team_over[tid]  = gp
                team_under[tid] = 0
            else:
                team_over[tid]  = 0
                team_under[tid] = gp
        print(f"   OK: {len(team_stats)} equipos con stats")
    else:
        print("   WARN: no se obtuvieron stats de equipos")
except Exception as e:
    print(f"   ERROR team stats: {e}")

# 4. Stats de jugadores
print("\n4. Obteniendo stats de jugadores...")
player_stats = {}
try:
    df_players = safe_get(
        leaguedashplayerstats.LeagueDashPlayerStats,
        season=SEASON,
        season_type_all_star="Regular Season",
    )
    if df_players is not None:
        for _, row in df_players.iterrows():
            gp = int(row.get("GP", 0))
            if gp < 5:
                continue
            pid = row["PLAYER_ID"]
            team_id = int(row["TEAM_ID"])
            if pid in player_stats:
                existing_gp = player_stats[pid]["games_played"]
                existing_tid = player_stats[pid]["team_id"]
                if existing_tid != 0 and team_id == 0:
                    continue
                if gp <= existing_gp and team_id == 0:
                    continue
            n = max(gp, 1)
            player_stats[pid] = {
                "name":          row["PLAYER_NAME"],
                "team_id":       team_id,
                "games_played":  gp,
                "avg_points":    round(float(row.get("PTS", 0)) / n, 1),
                "avg_rebounds":  round(float(row.get("REB", 0)) / n, 1),
                "avg_assists":   round(float(row.get("AST", 0)) / n, 1),
                "avg_threes":    round(float(row.get("FG3M", 0)) / n, 1),
                "avg_steals":    round(float(row.get("STL", 0)) / n, 1),
                "avg_blocks":    round(float(row.get("BLK", 0)) / n, 1),
                "fg_pct":        round(float(row.get("FG_PCT", 0)) * 100, 1),
                "injury_status": "Active",
                "injury_reason": "",
                "available":     True,
            }
        print(f"   OK: {len(player_stats)} jugadores")
    else:
        print("   WARN: no se obtuvieron stats de jugadores")
except Exception as e:
    print(f"   ERROR player stats: {e}")

# 4b. Corregir equipo actual tras traspasos
print("\n4b. Verificando equipo actual de jugadores traspasados...")
print("    (esto puede tardar ~6 min por rate limit de NBA.com)")
traspasos = 0
valid_team_ids = set(teams.keys())
total_players = len(player_stats)

for i, (pid, pdata) in enumerate(player_stats.items(), 1):
    if i % 50 == 0:
        print(f"   ...procesando {i}/{total_players}")
    try:
        time.sleep(0.6)
        df_info = commonplayerinfo.CommonPlayerInfo(player_id=pid).get_data_frames()[0]
        current_team_id = int(df_info["TEAM_ID"].iloc[0])
        if current_team_id != pdata["team_id"] and current_team_id in valid_team_ids:
            print(f"   Traspaso: {pdata['name']}  ({pdata['team_id']} -> {current_team_id})")
            pdata["team_id"] = current_team_id
            traspasos += 1
    except Exception:
        pass

print(f"   OK: {traspasos} traspasos detectados y corregidos")

# 5. Lesionados
print("\n5. Lesionados: no disponible en nba_api free (todos Active)")
total_injured = 0

# 6. Construir JSON
print("\n6. Construyendo JSON...")
result = {}

for tid, info in teams.items():
    team_name = f"{info['city']} {info['nickname']}"
    s  = standings.get(tid, {})
    ts = team_stats.get(tid, {})

    wins    = s.get("wins", 0)
    losses  = s.get("losses", 0)
    total   = max(wins + losses, 1)
    avg_pts = ts.get("avg_points", 0.0)

    team_pl = sorted(
        [p for p in player_stats.values() if p["team_id"] == tid],
        key=lambda x: x["avg_points"], reverse=True
    )
    active  = [p for p in team_pl if p.get("available", True)][:15]
    injured = [p for p in team_pl if not p.get("available", True)]

    result[team_name] = {
        "name":               team_name,
        "team_id":            tid,
        "wins":               wins,
        "losses":             losses,
        "win_pct":            s.get("win_pct", 0.0),
        "conference":         info.get("conference", ""),
        "division":           info.get("division", ""),
        "conference_rank":    s.get("conference_rank", 0),
        "home_wins":          s.get("home_wins", 0),
        "away_wins":          s.get("away_wins", 0),
        "avg_points":         avg_pts,
        "avg_points_allowed": ts.get("avg_points_allowed", 0.0),
        "avg_rebounds":       ts.get("avg_rebounds", 0.0),
        "avg_assists":        ts.get("avg_assists", 0.0),
        "avg_threes":         0.0,
        "avg_steals":         ts.get("avg_steals", 0.0),
        "avg_blocks":         ts.get("avg_blocks", 0.0),
        "avg_turnovers":      ts.get("avg_turnovers", 0.0),
        "fg_pct":             ts.get("fg_pct", 0.0),
        "three_pct":          ts.get("three_pct", 0.0),
        "ft_pct":             ts.get("ft_pct", 0.0),
        "total_points":       int(avg_pts * total),
        "over_220":           team_over.get(tid, 0),
        "under_220":          team_under.get(tid, 0),
        "players":            active,
        "injured_players":    injured,
        "source":             "nba_api"
    }

os.makedirs("static", exist_ok=True)

# Verificar que los datos son válidos antes de sobrescribir
teams_with_data = sum(1 for t in result.values() if t.get("wins", 0) > 0 or t.get("losses", 0) > 0)
if teams_with_data == 0:
    print(f"\nADVERTENCIA: todos los equipos tienen 0 victorias/derrotas — la API no devolvió datos.")
    if os.path.exists(OUTPUT):
        print(f"  Conservando {OUTPUT} anterior para no sobreescribir con datos vacíos.")
        exit(0)

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({
        "league":        "NBA",
        "season":        SEASON,
        "updated_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_used":   "nba_api (oficial, gratis)",
        "over_line":     OVER_LINE,
        "total_injured": total_injured,
        "teams":         result
    }, f, ensure_ascii=False, indent=2)

print(f"\nCOMPLETADO:")
print(f"  {len(result)} equipos")
print(f"  {len(player_stats)} jugadores")
print(f"  {traspasos} traspasos corregidos")
print(f"  {total_injured} lesionados")
print(f"  Archivo: {OUTPUT}")
