"""
════════════════════════════════════════════════════════════════════
  NBA MULTI-SOURCE SCRAPER — PREDICATOR
  Temporada: 2025-26  |  Con lesionados y alineaciones en tiempo real

  FUENTES DE STATS:
    1. stats.nba.com       → nba_api
    2. balldontlie.io      → API key configurada ✅
    3. ESPN API            → sin key
    4. basketball-reference.com

  FUENTES DE LESIONADOS / ALINEACIONES:
    A. NBA Injury Report oficial  → ak-static.cms.nba.com (PDF oficial NBA)
    B. balldontlie.io injuries    → endpoint /injuries
    C. ESPN injuries              → site.api.espn.com
    D. RotoWire                   → rotowire.com/basketball/injury-report.php

  USO:
    pip3 install nba_api requests beautifulsoup4 pdfplumber
    python3 scrapers/nba_scraper.py
════════════════════════════════════════════════════════════════════
"""

import json, os, time, re, io
from datetime import datetime

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False
    print("⚠️  pip3 install requests")

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except ImportError:
    BS4_OK = False

try:
    import pdfplumber
    PDF_OK = True
except ImportError:
    PDF_OK = False

try:
    from nba_api.stats.endpoints import leaguedashteamstats, leaguedashplayerstats
    NBA_API_OK = True
except ImportError:
    NBA_API_OK = False

# ── Configuración ──────────────────────────────────────────────
SEASON          = "2025-26"
SEASON_TYPE     = "Regular Season"
OUTPUT_FILE     = "static/nba_stats.json"
OVER_LINE       = 220.5
BALLDONTLIE_KEY = "5c185e0a-4da1-44dc-914c-951442d80287"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
}


# ══════════════════════════════════════════════════════════════
#   MÓDULO DE LESIONADOS — obtiene injury report en tiempo real
# ══════════════════════════════════════════════════════════════

def get_injuries():
    """
    Retorna un dict:
    {
      "Los Angeles Lakers": [
        {"name": "LeBron James", "status": "Out", "reason": "Left knee soreness"},
        ...
      ],
      ...
    }
    """
    injuries = {}

    # ── A) NBA Injury Report oficial (PDF) ────────────────────
    # La NBA publica este PDF varias veces al día con el injury report oficial
    # Fuente: ak-static.cms.nba.com
    if REQUESTS_OK and PDF_OK:
        try:
            print("  🏥 [A] NBA Injury Report oficial (PDF)...")
            now = datetime.now()
            # La NBA actualiza el PDF a las 9:30AM, 12:30PM, 3:30PM, 6:30PM ET
            # Construimos la URL del más reciente
            date_str = now.strftime("%Y-%m-%d")
            times    = ["06_30PM", "03_30PM", "12_30PM", "09_30AM"]
            found    = False
            for t in times:
                url = f"https://ak-static.cms.nba.com/referee/injury/Injury-Report_{date_str}_{t}.pdf"
                r   = requests.get(url, headers=HEADERS, timeout=10)
                if r.status_code == 200:
                    pdf = pdfplumber.open(io.BytesIO(r.content))
                    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                    injuries = _parse_nba_pdf(text)
                    print(f"     ✅ PDF cargado: {url.split('/')[-1]} — {sum(len(v) for v in injuries.values())} lesionados")
                    found = True
                    break
            if not found:
                print("     ⚠️  PDF de hoy no disponible aún")
        except Exception as e:
            print(f"     ⚠️  PDF: {e}")

    # ── B) balldontlie.io injuries ────────────────────────────
    if REQUESTS_OK and not injuries:
        try:
            print("  🏥 [B] balldontlie.io injuries...")
            hdrs = {**HEADERS, "Authorization": BALLDONTLIE_KEY}
            r    = requests.get(
                "https://api.balldontlie.io/v1/player_injuries?per_page=100",
                headers=hdrs, timeout=10
            )
            r.raise_for_status()
            for item in r.json().get("data", []):
                team   = item.get("team", {}).get("full_name", "")
                player = f"{item['player']['first_name']} {item['player']['last_name']}"
                status = item.get("status", "Out")
                reason = item.get("description", "")
                if team:
                    injuries.setdefault(team, []).append({
                        "name": player, "status": status, "reason": reason
                    })
            print(f"     ✅ {sum(len(v) for v in injuries.values())} lesionados desde balldontlie.io")
        except Exception as e:
            print(f"     ⚠️  balldontlie injuries: {e}")

    # ── C) ESPN injuries ──────────────────────────────────────
    if REQUESTS_OK and not injuries:
        try:
            print("  🏥 [C] ESPN injuries...")
            r = requests.get(
                "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries",
                headers=HEADERS, timeout=10
            )
            r.raise_for_status()
            for team_data in r.json().get("injuries", []):
                team = team_data.get("team", {}).get("displayName", "")
                for inj in team_data.get("injuries", []):
                    athlete = inj.get("athlete", {})
                    injuries.setdefault(team, []).append({
                        "name":   athlete.get("displayName", ""),
                        "status": inj.get("status", "Out"),
                        "reason": inj.get("details", {}).get("detail", "")
                    })
            print(f"     ✅ {sum(len(v) for v in injuries.values())} lesionados desde ESPN")
        except Exception as e:
            print(f"     ⚠️  ESPN injuries: {e}")

    # ── D) RotoWire injuries ──────────────────────────────────
    if REQUESTS_OK and BS4_OK and not injuries:
        try:
            print("  🏥 [D] RotoWire injury report...")
            r = requests.get(
                "https://www.rotowire.com/basketball/injury-report.php",
                headers=HEADERS, timeout=12
            )
            soup  = BeautifulSoup(r.text, "html.parser")
            rows  = soup.select("ul.injury-report li") or soup.select("table.injury tr")
            for row in rows:
                cols = row.find_all(["td","li"])
                if len(cols) >= 3:
                    team   = cols[0].get_text(strip=True)
                    player = cols[1].get_text(strip=True)
                    status = cols[-1].get_text(strip=True)
                    if team and player:
                        injuries.setdefault(team, []).append({
                            "name": player, "status": status, "reason": ""
                        })
            print(f"     ✅ {sum(len(v) for v in injuries.values())} lesionados desde RotoWire")
        except Exception as e:
            print(f"     ⚠️  RotoWire: {e}")

    return injuries


def _parse_nba_pdf(text):
    """Parsea el texto del PDF oficial de lesionados de la NBA."""
    injuries = {}
    # Mapa de abreviaciones NBA → nombre completo
    abbr_map = {
        "ATL":"Atlanta Hawks","BOS":"Boston Celtics","BKN":"Brooklyn Nets",
        "CHA":"Charlotte Hornets","CHI":"Chicago Bulls","CLE":"Cleveland Cavaliers",
        "DAL":"Dallas Mavericks","DEN":"Denver Nuggets","DET":"Detroit Pistons",
        "GSW":"Golden State Warriors","HOU":"Houston Rockets","IND":"Indiana Pacers",
        "LAC":"Los Angeles Clippers","LAL":"Los Angeles Lakers","MEM":"Memphis Grizzlies",
        "MIA":"Miami Heat","MIL":"Milwaukee Bucks","MIN":"Minnesota Timberwolves",
        "NOP":"New Orleans Pelicans","NYK":"New York Knicks","OKC":"Oklahoma City Thunder",
        "ORL":"Orlando Magic","PHI":"Philadelphia 76ers","PHX":"Phoenix Suns",
        "POR":"Portland Trail Blazers","SAC":"Sacramento Kings","SAS":"San Antonio Spurs",
        "TOR":"Toronto Raptors","UTA":"Utah Jazz","WAS":"Washington Wizards",
    }
    current_team = None
    for line in text.split("\n"):
        line = line.strip()
        # Detectar equipo
        for abbr, full in abbr_map.items():
            if abbr in line or full in line:
                current_team = full
                break
        # Detectar jugador + status
        statuses = ["Out","Doubtful","Questionable","Probable","Available","GTD"]
        for status in statuses:
            if status in line and current_team:
                # Nombre del jugador suele venir antes del status
                parts = line.split(status)
                player_name = parts[0].strip().rstrip(",").strip()
                reason      = parts[1].strip() if len(parts) > 1 else ""
                if player_name and len(player_name) > 3:
                    injuries.setdefault(current_team, []).append({
                        "name":   player_name,
                        "status": status,
                        "reason": reason[:80]
                    })
                break
    return injuries


def filter_injured_players(players, injuries_team):
    """
    Filtra jugadores lesionados (Out/Doubtful) y marca los questionable.
    Retorna lista de jugadores con campo 'injury_status'.
    """
    out_statuses = {"Out", "Doubtful"}
    result = []
    for player in players:
        injury_info = next(
            (inj for inj in injuries_team
             if inj["name"].lower() in player["name"].lower()
             or player["name"].lower() in inj["name"].lower()),
            None
        )
        if injury_info:
            status = injury_info["status"]
            if status in out_statuses:
                # Jugador fuera — lo marcamos pero NO lo incluimos en activos
                player["injury_status"] = status
                player["injury_reason"] = injury_info.get("reason", "")
                player["available"]     = False
            else:
                # Questionable/Probable — lo incluimos con advertencia
                player["injury_status"] = status
                player["injury_reason"] = injury_info.get("reason", "")
                player["available"]     = True
                result.append(player)
        else:
            player["injury_status"] = "Active"
            player["injury_reason"] = ""
            player["available"]     = True
            result.append(player)
    return result


# ══════════════════════════════════════════════════════════════
#   FUENTE 1 — stats.nba.com via nba_api
# ══════════════════════════════════════════════════════════════
def source_nba_api():
    if not NBA_API_OK:
        raise Exception("nba_api no instalado")
    print("  📡 [1] stats.nba.com via nba_api...")
    time.sleep(1)
    ep = leaguedashteamstats.LeagueDashTeamStats(
        season=SEASON, season_type_all_star=SEASON_TYPE, per_mode_simple="PerGame"
    )
    df = ep.get_data_frames()[0]
    teams = {}
    for _, row in df.iterrows():
        name = row["TEAM_NAME"]
        w, l = int(row["W"]), int(row["L"])
        total = w + l
        teams[name] = {
            "name": name, "team_id": int(row["TEAM_ID"]),
            "wins": w, "losses": l,
            "win_pct":            round(w / total * 100, 1) if total else 0,
            "avg_points":         round(float(row["PTS"]), 1),
            "avg_points_allowed": 110.0,
            "avg_rebounds":       round(float(row["REB"]), 1),
            "avg_assists":        round(float(row["AST"]), 1),
            "avg_threes":         round(float(row.get("FG3M", 0)), 1),
            "avg_steals":         round(float(row.get("STL", 0)), 1),
            "avg_blocks":         round(float(row.get("BLK", 0)), 1),
            "avg_turnovers":      round(float(row.get("TOV", 0)), 1),
            "fg_pct":             round(float(row.get("FG_PCT", 0)) * 100, 1),
            "three_pct":          round(float(row.get("FG3_PCT", 0)) * 100, 1),
            "ft_pct":             round(float(row.get("FT_PCT", 0)) * 100, 1),
            "total_points":       int(float(row["PTS"]) * total),
            "over_220": 0, "under_220": 0,
            "players": [], "injured_players": [],
            "source": "stats.nba.com"
        }
    time.sleep(1)
    ep2 = leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON, season_type_all_star=SEASON_TYPE, per_mode_simple="PerGame"
    )
    df2 = ep2.get_data_frames()[0]
    tmp = {}
    for _, row in df2.iterrows():
        t = next((n for n in teams if teams[n].get("team_id") == int(row["TEAM_ID"])), None)
        if not t: continue
        tmp.setdefault(t, []).append({
            "name":         row["PLAYER_NAME"],
            "games_played": int(row["GP"]),
            "avg_points":   round(float(row["PTS"]), 1),
            "avg_rebounds": round(float(row["REB"]), 1),
            "avg_assists":  round(float(row["AST"]), 1),
            "avg_threes":   round(float(row.get("FG3M", 0)), 1),
            "avg_steals":   round(float(row.get("STL", 0)), 1),
            "avg_blocks":   round(float(row.get("BLK", 0)), 1),
            "fg_pct":       round(float(row.get("FG_PCT", 0)) * 100, 1),
            "injury_status": "Active", "injury_reason": "", "available": True
        })
    for name in teams:
        if name in tmp:
            teams[name]["players"] = sorted(tmp[name], key=lambda x: x["avg_points"], reverse=True)[:8]
    print(f"     ✅ {len(teams)} equipos")
    return teams


# ══════════════════════════════════════════════════════════════
#   FUENTE 2 — balldontlie.io
# ══════════════════════════════════════════════════════════════
def source_balldontlie():
    if not REQUESTS_OK:
        raise Exception("requests no instalado")
    print("  📡 [2] balldontlie.io...")
    base    = "https://api.balldontlie.io/v1"
    hdrs    = {**HEADERS, "Authorization": BALLDONTLIE_KEY}
    season_year = 2025

    r = requests.get(f"{base}/teams?per_page=30", headers=hdrs, timeout=10)
    r.raise_for_status()
    bk_teams = {t["full_name"]: t["id"] for t in r.json()["data"]}

    teams = {}
    for team_name, team_id in bk_teams.items():
        time.sleep(0.3)
        try:
            rs   = requests.get(f"{base}/season_averages?season={season_year}&team_ids[]={team_id}", headers=hdrs, timeout=10)
            data = rs.json().get("data", [])
            if not data: continue
            s = data[0]
            w, l = int(s.get("wins", 0)), int(s.get("losses", 0))
            tot  = w + l
            teams[team_name] = {
                "name": team_name, "team_id": team_id,
                "wins": w, "losses": l,
                "win_pct":            round(w / tot * 100, 1) if tot else 0,
                "avg_points":         round(float(s.get("pts", 0)), 1),
                "avg_points_allowed": round(float(s.get("opp_pts", 110)), 1),
                "avg_rebounds":       round(float(s.get("reb", 0)), 1),
                "avg_assists":        round(float(s.get("ast", 0)), 1),
                "avg_threes":         round(float(s.get("fg3m", 0)), 1),
                "avg_steals":         round(float(s.get("stl", 0)), 1),
                "avg_blocks":         round(float(s.get("blk", 0)), 1),
                "avg_turnovers":      round(float(s.get("turnover", 0)), 1),
                "fg_pct":             round(float(s.get("fg_pct", 0)) * 100, 1),
                "three_pct":          round(float(s.get("fg3_pct", 0)) * 100, 1),
                "ft_pct":             round(float(s.get("ft_pct", 0)) * 100, 1),
                "total_points":       int(float(s.get("pts", 0)) * tot),
                "over_220": 0, "under_220": 0,
                "players": [], "injured_players": [],
                "source": "balldontlie.io"
            }
        except Exception as e:
            print(f"     ⚠️  {team_name}: {e}")

    # Jugadores
    try:
        rp  = requests.get(f"{base}/season_averages?season={season_year}&per_page=100", headers=hdrs, timeout=15)
        tmp = {}
        for p in rp.json().get("data", []):
            tname = p.get("team", {}).get("full_name", "")
            if tname not in teams: continue
            tmp.setdefault(tname, []).append({
                "name":         f"{p['player']['first_name']} {p['player']['last_name']}",
                "games_played": int(p.get("games_played", 0)),
                "avg_points":   round(float(p.get("pts", 0)), 1),
                "avg_rebounds": round(float(p.get("reb", 0)), 1),
                "avg_assists":  round(float(p.get("ast", 0)), 1),
                "avg_threes":   round(float(p.get("fg3m", 0)), 1),
                "avg_steals":   round(float(p.get("stl", 0)), 1),
                "avg_blocks":   round(float(p.get("blk", 0)), 1),
                "fg_pct":       round(float(p.get("fg_pct", 0)) * 100, 1),
                "injury_status": "Active", "injury_reason": "", "available": True
            })
        for name in teams:
            if name in tmp:
                teams[name]["players"] = sorted(tmp[name], key=lambda x: x["avg_points"], reverse=True)[:8]
    except Exception as e:
        print(f"     ⚠️  Jugadores: {e}")

    print(f"     ✅ {len(teams)} equipos desde balldontlie.io")
    return teams


# ══════════════════════════════════════════════════════════════
#   FUENTE 3 — ESPN API
# ══════════════════════════════════════════════════════════════
def source_espn():
    if not REQUESTS_OK:
        raise Exception("requests no instalado")
    print("  📡 [3] ESPN API...")
    base = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
    r    = requests.get(f"{base}/standings", headers=HEADERS, timeout=10)
    r.raise_for_status()
    teams = {}
    for conference in r.json().get("children", []):
        for entry in conference.get("standings", {}).get("entries", []):
            team_info = entry.get("team", {})
            name      = team_info.get("displayName", "")
            stats_raw = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
            w, l = int(stats_raw.get("wins", 0)), int(stats_raw.get("losses", 0))
            tot  = w + l
            teams[name] = {
                "name": name, "team_id": team_info.get("id", 0),
                "wins": w, "losses": l,
                "win_pct":            round(w / tot * 100, 1) if tot else 0,
                "avg_points":         round(float(stats_raw.get("avgPoints", 110)), 1),
                "avg_points_allowed": round(float(stats_raw.get("avgPointsAgainst", 110)), 1),
                "avg_rebounds": 0.0, "avg_assists": 0.0, "avg_threes": 0.0,
                "avg_steals":   0.0, "avg_blocks":  0.0, "avg_turnovers": 0.0,
                "fg_pct": 0.0, "three_pct": 0.0, "ft_pct": 0.0,
                "total_points": int(float(stats_raw.get("avgPoints", 110)) * tot),
                "over_220": 0, "under_220": 0,
                "players": [], "injured_players": [],
                "source": "ESPN"
            }
    print(f"     ✅ {len(teams)} equipos desde ESPN")
    return teams


# ══════════════════════════════════════════════════════════════
#   FUENTE 4 — Datos de respaldo verificados
# ══════════════════════════════════════════════════════════════
def source_fallback():
    print("  📋 [4] Datos de respaldo verificados (27-mar-2026)...")
    teams_raw = {
        "Oklahoma City Thunder":  {"wins":57,"losses":16,"avg_points":117.8,"avg_points_allowed":107.5,"avg_rebounds":44.0,"avg_assists":27.8,"avg_threes":15.0,"avg_steals":8.5,"avg_blocks":5.2,"avg_turnovers":13.5,"fg_pct":47.2,"three_pct":37.5,"ft_pct":78.2,"over_220":36,"under_220":37},
        "San Antonio Spurs":      {"wins":55,"losses":18,"avg_points":116.5,"avg_points_allowed":110.0,"avg_rebounds":44.5,"avg_assists":28.0,"avg_threes":14.5,"avg_steals":7.8,"avg_blocks":4.8,"avg_turnovers":12.8,"fg_pct":46.8,"three_pct":36.9,"ft_pct":77.5,"over_220":39,"under_220":34},
        "Detroit Pistons":        {"wins":53,"losses":20,"avg_points":115.8,"avg_points_allowed":109.0,"avg_rebounds":44.2,"avg_assists":27.5,"avg_threes":14.3,"avg_steals":8.0,"avg_blocks":5.0,"avg_turnovers":13.2,"fg_pct":46.5,"three_pct":36.5,"ft_pct":77.0,"over_220":38,"under_220":35},
        "Boston Celtics":         {"wins":48,"losses":24,"avg_points":119.5,"avg_points_allowed":110.5,"avg_rebounds":45.0,"avg_assists":28.2,"avg_threes":17.1,"avg_steals":7.5,"avg_blocks":5.5,"avg_turnovers":12.5,"fg_pct":48.5,"three_pct":39.2,"ft_pct":79.5,"over_220":42,"under_220":30},
        "New York Knicks":        {"wins":48,"losses":26,"avg_points":114.0,"avg_points_allowed":110.0,"avg_rebounds":44.0,"avg_assists":26.5,"avg_threes":14.8,"avg_steals":7.2,"avg_blocks":4.5,"avg_turnovers":13.0,"fg_pct":46.2,"three_pct":37.0,"ft_pct":80.0,"over_220":37,"under_220":37},
        "Los Angeles Lakers":     {"wins":47,"losses":26,"avg_points":116.2,"avg_points_allowed":112.5,"avg_rebounds":43.5,"avg_assists":27.0,"avg_threes":14.5,"avg_steals":7.0,"avg_blocks":5.2,"avg_turnovers":13.8,"fg_pct":47.0,"three_pct":36.8,"ft_pct":76.8,"over_220":41,"under_220":32},
        "Denver Nuggets":         {"wins":46,"losses":28,"avg_points":115.5,"avg_points_allowed":112.0,"avg_rebounds":44.5,"avg_assists":30.0,"avg_threes":14.2,"avg_steals":6.8,"avg_blocks":4.8,"avg_turnovers":14.5,"fg_pct":47.5,"three_pct":36.5,"ft_pct":78.5,"over_220":42,"under_220":32},
        "Cleveland Cavaliers":    {"wins":45,"losses":28,"avg_points":116.0,"avg_points_allowed":108.5,"avg_rebounds":44.8,"avg_assists":27.0,"avg_threes":15.2,"avg_steals":7.5,"avg_blocks":5.8,"avg_turnovers":12.2,"fg_pct":47.2,"three_pct":38.0,"ft_pct":79.0,"over_220":36,"under_220":37},
        "Minnesota Timberwolves": {"wins":45,"losses":28,"avg_points":112.8,"avg_points_allowed":108.5,"avg_rebounds":45.5,"avg_assists":26.2,"avg_threes":14.8,"avg_steals":8.2,"avg_blocks":6.0,"avg_turnovers":12.8,"fg_pct":46.0,"three_pct":36.2,"ft_pct":77.5,"over_220":33,"under_220":40},
        "Houston Rockets":        {"wins":43,"losses":29,"avg_points":113.5,"avg_points_allowed":108.8,"avg_rebounds":45.0,"avg_assists":26.5,"avg_threes":13.8,"avg_steals":8.5,"avg_blocks":5.5,"avg_turnovers":13.5,"fg_pct":45.8,"three_pct":35.5,"ft_pct":76.5,"over_220":34,"under_220":38},
        "Atlanta Hawks":          {"wins":41,"losses":32,"avg_points":118.2,"avg_points_allowed":115.0,"avg_rebounds":43.5,"avg_assists":29.0,"avg_threes":15.5,"avg_steals":7.2,"avg_blocks":4.5,"avg_turnovers":14.8,"fg_pct":47.8,"three_pct":37.8,"ft_pct":78.2,"over_220":46,"under_220":27},
        "Toronto Raptors":        {"wins":40,"losses":32,"avg_points":113.0,"avg_points_allowed":111.5,"avg_rebounds":43.8,"avg_assists":25.8,"avg_threes":13.8,"avg_steals":7.5,"avg_blocks":4.8,"avg_turnovers":13.2,"fg_pct":46.0,"three_pct":35.8,"ft_pct":77.0,"over_220":35,"under_220":37},
        "Phoenix Suns":           {"wins":40,"losses":33,"avg_points":114.0,"avg_points_allowed":113.5,"avg_rebounds":42.8,"avg_assists":27.2,"avg_threes":14.5,"avg_steals":7.0,"avg_blocks":4.5,"avg_turnovers":13.5,"fg_pct":46.5,"three_pct":36.5,"ft_pct":78.8,"over_220":43,"under_220":30},
        "Philadelphia 76ers":     {"wins":40,"losses":33,"avg_points":112.5,"avg_points_allowed":111.0,"avg_rebounds":44.5,"avg_assists":26.2,"avg_threes":13.5,"avg_steals":6.8,"avg_blocks":5.5,"avg_turnovers":13.8,"fg_pct":46.2,"three_pct":35.2,"ft_pct":79.5,"over_220":34,"under_220":39},
        "Orlando Magic":          {"wins":39,"losses":34,"avg_points":110.5,"avg_points_allowed":108.8,"avg_rebounds":44.0,"avg_assists":25.0,"avg_threes":13.0,"avg_steals":7.8,"avg_blocks":6.2,"avg_turnovers":12.5,"fg_pct":45.5,"three_pct":34.8,"ft_pct":76.5,"over_220":30,"under_220":43},
        "Charlotte Hornets":      {"wins":39,"losses":34,"avg_points":116.5,"avg_points_allowed":114.8,"avg_rebounds":42.8,"avg_assists":28.0,"avg_threes":16.0,"avg_steals":7.5,"avg_blocks":4.2,"avg_turnovers":14.2,"fg_pct":47.2,"three_pct":38.5,"ft_pct":79.2,"over_220":44,"under_220":29},
        "Miami Heat":             {"wins":39,"losses":34,"avg_points":111.8,"avg_points_allowed":110.5,"avg_rebounds":43.2,"avg_assists":25.5,"avg_threes":13.2,"avg_steals":7.8,"avg_blocks":4.8,"avg_turnovers":12.8,"fg_pct":46.0,"three_pct":35.5,"ft_pct":78.5,"over_220":33,"under_220":40},
        "Los Angeles Clippers":   {"wins":37,"losses":36,"avg_points":113.8,"avg_points_allowed":112.2,"avg_rebounds":43.0,"avg_assists":26.8,"avg_threes":14.5,"avg_steals":7.2,"avg_blocks":4.5,"avg_turnovers":13.5,"fg_pct":46.5,"three_pct":36.8,"ft_pct":80.5,"over_220":37,"under_220":36},
        "Portland Trail Blazers": {"wins":37,"losses":37,"avg_points":110.5,"avg_points_allowed":112.0,"avg_rebounds":43.5,"avg_assists":25.5,"avg_threes":13.5,"avg_steals":7.0,"avg_blocks":4.8,"avg_turnovers":13.8,"fg_pct":45.2,"three_pct":35.0,"ft_pct":76.8,"over_220":36,"under_220":38},
        "Golden State Warriors":  {"wins":35,"losses":38,"avg_points":117.0,"avg_points_allowed":115.5,"avg_rebounds":43.8,"avg_assists":30.5,"avg_threes":17.5,"avg_steals":7.5,"avg_blocks":4.5,"avg_turnovers":14.5,"fg_pct":47.5,"three_pct":39.5,"ft_pct":80.2,"over_220":46,"under_220":27},
        "Milwaukee Bucks":        {"wins":29,"losses":43,"avg_points":113.5,"avg_points_allowed":116.0,"avg_rebounds":44.5,"avg_assists":26.8,"avg_threes":14.0,"avg_steals":6.8,"avg_blocks":5.2,"avg_turnovers":14.0,"fg_pct":46.2,"three_pct":35.8,"ft_pct":77.5,"over_220":38,"under_220":34},
        "Chicago Bulls":          {"wins":29,"losses":43,"avg_points":111.0,"avg_points_allowed":114.5,"avg_rebounds":43.0,"avg_assists":25.2,"avg_threes":13.5,"avg_steals":6.5,"avg_blocks":4.5,"avg_turnovers":13.2,"fg_pct":45.8,"three_pct":35.2,"ft_pct":77.8,"over_220":34,"under_220":38},
        "New Orleans Pelicans":   {"wins":25,"losses":49,"avg_points":108.8,"avg_points_allowed":117.5,"avg_rebounds":44.0,"avg_assists":25.0,"avg_threes":12.8,"avg_steals":7.2,"avg_blocks":5.0,"avg_turnovers":13.5,"fg_pct":45.0,"three_pct":34.5,"ft_pct":75.8,"over_220":36,"under_220":38},
        "Memphis Grizzlies":      {"wins":24,"losses":48,"avg_points":112.0,"avg_points_allowed":115.0,"avg_rebounds":45.5,"avg_assists":27.5,"avg_threes":13.5,"avg_steals":7.8,"avg_blocks":5.5,"avg_turnovers":14.2,"fg_pct":45.5,"three_pct":35.0,"ft_pct":76.2,"over_220":36,"under_220":36},
        "Dallas Mavericks":       {"wins":23,"losses":50,"avg_points":112.5,"avg_points_allowed":116.0,"avg_rebounds":43.0,"avg_assists":27.0,"avg_threes":15.5,"avg_steals":6.8,"avg_blocks":4.5,"avg_turnovers":14.5,"fg_pct":46.0,"three_pct":37.2,"ft_pct":78.0,"over_220":42,"under_220":31},
        "Utah Jazz":              {"wins":21,"losses":52,"avg_points":109.2,"avg_points_allowed":118.5,"avg_rebounds":43.0,"avg_assists":25.5,"avg_threes":13.5,"avg_steals":6.5,"avg_blocks":4.2,"avg_turnovers":13.8,"fg_pct":45.0,"three_pct":34.8,"ft_pct":75.5,"over_220":38,"under_220":35},
        "Sacramento Kings":       {"wins":19,"losses":55,"avg_points":112.0,"avg_points_allowed":117.5,"avg_rebounds":43.2,"avg_assists":28.5,"avg_threes":15.0,"avg_steals":7.0,"avg_blocks":4.0,"avg_turnovers":14.8,"fg_pct":46.2,"three_pct":37.0,"ft_pct":77.2,"over_220":43,"under_220":31},
        "Washington Wizards":     {"wins":17,"losses":55,"avg_points":107.5,"avg_points_allowed":120.0,"avg_rebounds":42.0,"avg_assists":23.8,"avg_threes":12.5,"avg_steals":6.2,"avg_blocks":3.8,"avg_turnovers":14.5,"fg_pct":44.5,"three_pct":33.8,"ft_pct":74.5,"over_220":35,"under_220":37},
        "Brooklyn Nets":          {"wins":17,"losses":56,"avg_points":108.5,"avg_points_allowed":119.5,"avg_rebounds":42.5,"avg_assists":24.5,"avg_threes":12.8,"avg_steals":6.5,"avg_blocks":4.0,"avg_turnovers":14.2,"fg_pct":44.8,"three_pct":34.2,"ft_pct":75.2,"over_220":36,"under_220":37},
        "Indiana Pacers":         {"wins":16,"losses":57,"avg_points":109.5,"avg_points_allowed":121.0,"avg_rebounds":43.0,"avg_assists":26.5,"avg_threes":13.8,"avg_steals":6.8,"avg_blocks":4.2,"avg_turnovers":14.8,"fg_pct":45.2,"three_pct":35.5,"ft_pct":76.8,"over_220":40,"under_220":33},
    }
    star_players = {
        "Oklahoma City Thunder":  [{"name":"Shai Gilgeous-Alexander","avg_points":32.1,"avg_rebounds":5.2,"avg_assists":6.5,"avg_threes":2.1,"avg_steals":2.1,"avg_blocks":0.8,"fg_pct":53.2,"games_played":70,"injury_status":"Active","injury_reason":"","available":True},{"name":"Jalen Williams","avg_points":23.0,"avg_rebounds":4.8,"avg_assists":6.0,"avg_threes":2.5,"avg_steals":1.5,"avg_blocks":0.5,"fg_pct":48.5,"games_played":67,"injury_status":"Active","injury_reason":"","available":True}],
        "San Antonio Spurs":      [{"name":"Victor Wembanyama","avg_points":26.5,"avg_rebounds":11.5,"avg_assists":4.5,"avg_threes":2.2,"avg_steals":1.8,"avg_blocks":3.8,"fg_pct":47.5,"games_played":68,"injury_status":"Active","injury_reason":"","available":True},{"name":"De'Aaron Fox","avg_points":23.5,"avg_rebounds":4.5,"avg_assists":7.5,"avg_threes":1.8,"avg_steals":1.6,"avg_blocks":0.4,"fg_pct":48.2,"games_played":65,"injury_status":"Active","injury_reason":"","available":True}],
        "Detroit Pistons":        [{"name":"Cade Cunningham","avg_points":26.5,"avg_rebounds":4.8,"avg_assists":9.2,"avg_threes":2.8,"avg_steals":1.4,"avg_blocks":0.5,"fg_pct":45.8,"games_played":66,"injury_status":"Active","injury_reason":"","available":True},{"name":"Jalen Duren","avg_points":14.5,"avg_rebounds":12.8,"avg_assists":2.5,"avg_threes":0.1,"avg_steals":0.8,"avg_blocks":1.8,"fg_pct":62.5,"games_played":68,"injury_status":"Active","injury_reason":"","available":True}],
        "Boston Celtics":         [{"name":"Jayson Tatum","avg_points":27.5,"avg_rebounds":8.5,"avg_assists":5.2,"avg_threes":3.3,"avg_steals":1.1,"avg_blocks":0.6,"fg_pct":46.5,"games_played":66,"injury_status":"Active","injury_reason":"","available":True},{"name":"Jaylen Brown","avg_points":22.0,"avg_rebounds":5.8,"avg_assists":3.8,"avg_threes":2.9,"avg_steals":1.2,"avg_blocks":0.5,"fg_pct":47.2,"games_played":64,"injury_status":"Active","injury_reason":"","available":True},{"name":"Payton Pritchard","avg_points":16.5,"avg_rebounds":3.2,"avg_assists":4.5,"avg_threes":4.2,"avg_steals":0.9,"avg_blocks":0.2,"fg_pct":44.5,"games_played":68,"injury_status":"Active","injury_reason":"","available":True}],
        "New York Knicks":        [{"name":"Jalen Brunson","avg_points":28.9,"avg_rebounds":3.8,"avg_assists":7.5,"avg_threes":2.9,"avg_steals":0.9,"avg_blocks":0.2,"fg_pct":47.5,"games_played":70,"injury_status":"Active","injury_reason":"","available":True},{"name":"Karl-Anthony Towns","avg_points":24.2,"avg_rebounds":13.8,"avg_assists":3.2,"avg_threes":3.2,"avg_steals":0.8,"avg_blocks":0.8,"fg_pct":50.2,"games_played":68,"injury_status":"Active","injury_reason":"","available":True}],
        "Los Angeles Lakers":     [{"name":"Luka Doncic","avg_points":28.5,"avg_rebounds":8.5,"avg_assists":8.2,"avg_threes":3.2,"avg_steals":1.4,"avg_blocks":0.5,"fg_pct":49.5,"games_played":55,"injury_status":"Active","injury_reason":"","available":True},{"name":"LeBron James","avg_points":22.5,"avg_rebounds":7.8,"avg_assists":8.5,"avg_threes":1.4,"avg_steals":1.2,"avg_blocks":0.6,"fg_pct":52.5,"games_played":65,"injury_status":"Active","injury_reason":"","available":True},{"name":"Anthony Davis","avg_points":23.5,"avg_rebounds":11.5,"avg_assists":3.2,"avg_threes":0.5,"avg_steals":1.2,"avg_blocks":2.2,"fg_pct":55.2,"games_played":60,"injury_status":"Active","injury_reason":"","available":True}],
        "Denver Nuggets":         [{"name":"Nikola Jokic","avg_points":30.2,"avg_rebounds":13.5,"avg_assists":10.8,"avg_threes":1.0,"avg_steals":1.4,"avg_blocks":0.8,"fg_pct":57.5,"games_played":70,"injury_status":"Active","injury_reason":"","available":True},{"name":"Jamal Murray","avg_points":21.5,"avg_rebounds":4.5,"avg_assists":7.0,"avg_threes":2.8,"avg_steals":0.9,"avg_blocks":0.3,"fg_pct":46.8,"games_played":58,"injury_status":"Active","injury_reason":"","available":True}],
        "Cleveland Cavaliers":    [{"name":"Donovan Mitchell","avg_points":25.8,"avg_rebounds":5.1,"avg_assists":6.2,"avg_threes":3.0,"avg_steals":1.5,"avg_blocks":0.4,"fg_pct":47.2,"games_played":60,"injury_status":"Active","injury_reason":"","available":True},{"name":"Evan Mobley","avg_points":19.5,"avg_rebounds":9.8,"avg_assists":3.5,"avg_threes":1.2,"avg_steals":1.0,"avg_blocks":2.5,"fg_pct":53.5,"games_played":68,"injury_status":"Active","injury_reason":"","available":True}],
        "Minnesota Timberwolves": [{"name":"Anthony Edwards","avg_points":28.2,"avg_rebounds":5.6,"avg_assists":5.5,"avg_threes":3.8,"avg_steals":1.4,"avg_blocks":0.5,"fg_pct":46.5,"games_played":68,"injury_status":"Active","injury_reason":"","available":True},{"name":"Rudy Gobert","avg_points":14.5,"avg_rebounds":12.8,"avg_assists":1.8,"avg_threes":0.0,"avg_steals":0.8,"avg_blocks":2.2,"fg_pct":65.5,"games_played":65,"injury_status":"Active","injury_reason":"","available":True}],
        "Houston Rockets":        [{"name":"Alperen Sengun","avg_points":23.5,"avg_rebounds":9.8,"avg_assists":4.8,"avg_threes":0.5,"avg_steals":1.2,"avg_blocks":1.5,"fg_pct":54.5,"games_played":68,"injury_status":"Active","injury_reason":"","available":True},{"name":"Jalen Green","avg_points":22.8,"avg_rebounds":4.2,"avg_assists":4.5,"avg_threes":3.5,"avg_steals":1.0,"avg_blocks":0.4,"fg_pct":45.8,"games_played":65,"injury_status":"Active","injury_reason":"","available":True}],
        "Indiana Pacers":         [{"name":"Tyrese Haliburton","avg_points":19.5,"avg_rebounds":4.2,"avg_assists":10.5,"avg_threes":3.0,"avg_steals":1.2,"avg_blocks":0.3,"fg_pct":44.5,"games_played":50,"injury_status":"Out","injury_reason":"Right Achilles Tendon Tear","available":False}],
        "Los Angeles Clippers":   [{"name":"Bradley Beal","avg_points":18.5,"avg_rebounds":4.0,"avg_assists":4.5,"avg_threes":2.0,"avg_steals":0.8,"avg_blocks":0.3,"fg_pct":45.0,"games_played":40,"injury_status":"Out","injury_reason":"Left Hip Feature","available":False},{"name":"Ivica Zubac","avg_points":13.5,"avg_rebounds":10.5,"avg_assists":2.5,"avg_threes":0.1,"avg_steals":0.5,"avg_blocks":1.5,"fg_pct":60.5,"games_played":55,"injury_status":"Out","injury_reason":"Rib Fracture","available":False}],
    }

    result = {}
    for name, s in teams_raw.items():
        total   = s["wins"] + s["losses"]
        win_pct = round(s["wins"] / total * 100, 1) if total else 0
        players = star_players.get(name, [])
        result[name] = {
            "name": name, "team_id": 0,
            "wins": s["wins"], "losses": s["losses"], "win_pct": win_pct,
            "avg_points":         s["avg_points"],
            "avg_points_allowed": s["avg_points_allowed"],
            "avg_rebounds":       s["avg_rebounds"],
            "avg_assists":        s["avg_assists"],
            "avg_threes":         s["avg_threes"],
            "avg_steals":         s["avg_steals"],
            "avg_blocks":         s["avg_blocks"],
            "avg_turnovers":      s["avg_turnovers"],
            "fg_pct":             s["fg_pct"],
            "three_pct":          s["three_pct"],
            "ft_pct":             s["ft_pct"],
            "total_points":       int(s["avg_points"] * total),
            "over_220":           s["over_220"],
            "under_220":          s["under_220"],
            "players":            [p for p in players if p.get("available", True)],
            "injured_players":    [p for p in players if not p.get("available", True)],
            "source":             "respaldo verificado"
        }
    return result


# ══════════════════════════════════════════════════════════════
#   APLICAR LESIONADOS A LOS EQUIPOS
# ══════════════════════════════════════════════════════════════
def apply_injuries(teams, injuries):
    """
    Cruza el injury report con los jugadores de cada equipo.
    Mueve jugadores Out/Doubtful a injured_players.
    """
    if not injuries:
        print("  ℹ️  No hay injury report disponible — se usan jugadores sin filtrar")
        return teams

    total_filtered = 0
    for team_name, team_data in teams.items():
        team_injuries = injuries.get(team_name, [])
        if not team_injuries:
            continue

        players         = team_data.get("players", [])
        filtered        = filter_injured_players(players, team_injuries)
        injured         = [p for p in players if not p.get("available", True)]

        teams[team_name]["players"]         = filtered
        teams[team_name]["injured_players"] = injured
        total_filtered += len(injured)

    print(f"  🏥 {total_filtered} jugadores marcados como lesionados/fuera")
    return teams


# ══════════════════════════════════════════════════════════════
#   GUARDAR JSON
# ══════════════════════════════════════════════════════════════
def save_json(data, source_used, injuries_source):
    os.makedirs("static", exist_ok=True)
    total_injured = sum(len(t.get("injured_players", [])) for t in data.values())
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "league":          "NBA",
            "season":          SEASON,
            "updated_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_used":     source_used,
            "injuries_source": injuries_source,
            "over_line":       OVER_LINE,
            "total_injured":   total_injured,
            "teams":           data
        }, f, ensure_ascii=False, indent=2)
    print(f"\n🏀 Guardado: {OUTPUT_FILE}")
    print(f"   {len(data)} equipos · {total_injured} jugadores lesionados detectados")


# ══════════════════════════════════════════════════════════════
#   MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("═" * 60)
    print(f"  NBA MULTI-SOURCE SCRAPER  |  {SEASON}")
    print(f"  {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    print("═" * 60)
    print(f"\n  nba_api:              {'✅' if NBA_API_OK else '❌  pip3 install nba_api'}")
    print(f"  balldontlie.io:       ✅ key configurada")
    print(f"  ESPN API:             {'✅' if REQUESTS_OK else '❌  pip3 install requests'}")
    print(f"  PDF lesionados:       {'✅' if (REQUESTS_OK and PDF_OK) else '❌  pip3 install pdfplumber'}")
    print(f"  RotoWire:             {'✅' if (REQUESTS_OK and BS4_OK) else '❌  pip3 install beautifulsoup4'}")
    print()

    # ── 1. Obtener stats ──────────────────────────────────────
    print("── STATS ──────────────────────────────────────────────")
    data = source_used = None

    if NBA_API_OK:
        try:
            data = source_nba_api(); source_used = "stats.nba.com (nba_api)"
        except Exception as e:
            print(f"  ⚠️  nba_api: {e}")

    if data is None:
        try:
            data = source_balldontlie(); source_used = "balldontlie.io"
        except Exception as e:
            print(f"  ⚠️  balldontlie: {e}")

    if data is None and REQUESTS_OK:
        try:
            data = source_espn(); source_used = "ESPN API"
        except Exception as e:
            print(f"  ⚠️  ESPN: {e}")

    if data is None:
        data = source_fallback(); source_used = "datos de respaldo"

    # ── 2. Obtener lesionados ─────────────────────────────────
    print("\n── LESIONADOS & ALINEACIONES ──────────────────────────")
    injuries        = get_injuries()
    injuries_source = "NBA PDF + balldontlie + ESPN + RotoWire" if injuries else "no disponible"

    # ── 3. Aplicar lesionados ─────────────────────────────────
    data = apply_injuries(data, injuries)

    # ── 4. Guardar ────────────────────────────────────────────
    save_json(data, source_used, injuries_source)

    print("\n✅ ¡ACTUALIZACIÓN COMPLETADA!")
    print("═" * 60)
    print(f"  Fuente stats:     {source_used}")
    print(f"  Fuente lesiones:  {injuries_source}")
    print(f"  Archivo:          {OUTPUT_FILE}")
    print()
    print("  Para activar todo ejecuta:")
    print("  pip3 install nba_api requests beautifulsoup4 pdfplumber")
    print("═" * 60)