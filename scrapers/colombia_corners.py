"""
════════════════════════════════════════════════════════════════
  COLOMBIA CORNERS SCRAPER
  Archivo: scrapers/colombia_corners.py

  API: Free API Live Football Data (RapidAPI)
  Host: free-api-live-football-data.p.rapidapi.com
  Liga BetPlay Colombia ID: 274
  Temporada: 2026

  USO:
    .venv/bin/python scrapers/colombia_corners.py
════════════════════════════════════════════════════════════════
"""

import json, os, sys, time, requests
from datetime import datetime

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
if not RAPIDAPI_KEY:
    print("⚠️  RAPIDAPI_KEY no está configurada en variables de entorno",
          file=sys.stderr)
    print("   Este script no se puede ejecutar sin ella.",
          file=sys.stderr)
    sys.exit(1)

LEAGUE_ID    = 274   # Primera A — Liga BetPlay Colombia
SEASON       = 2026
OUTPUT_FILE  = "static/colombia_stats.json"

HEADERS = {
    "x-rapidapi-key":  RAPIDAPI_KEY,
    "x-rapidapi-host": "free-api-live-football-data.p.rapidapi.com",
    "Content-Type":    "application/json"
}
BASE = "https://free-api-live-football-data.p.rapidapi.com"


def get_fixtures():
    """Obtiene los partidos jugados de la Liga BetPlay 2026."""
    print("📡 Obteniendo partidos de la Liga BetPlay 2026...")
    url = f"{BASE}/football-get-matches-by-league-and-season"
    params = {"leagueid": LEAGUE_ID, "season": SEASON}
    r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    matches = data.get("response", {}).get("matches", [])
    # Solo partidos terminados
    finished = [m for m in matches if m.get("status", {}).get("short") in ["FT", "AET", "PEN"]]
    print(f"   ✅ {len(finished)} partidos finalizados encontrados")
    return finished


def get_match_stats(event_id):
    """Obtiene estadísticas de un partido incluyendo córners."""
    url = f"{BASE}/football-get-match-event-all-stats"
    params = {"eventid": event_id}
    time.sleep(0.4)
    r = requests.get(url, headers=HEADERS, params=params, timeout=10)
    if r.status_code != 200:
        return None
    return r.json().get("response", {})


def build_corners_stats(fixtures):
    """
    Procesa todos los partidos y acumula córners por equipo.
    """
    print("📐 Procesando córners por equipo...")
    team_corners = {}

    total = len(fixtures)
    for i, match in enumerate(fixtures, 1):
        event_id   = match.get("id")
        home_name  = match.get("home", {}).get("name", "")
        away_name  = match.get("away", {}).get("name", "")

        if not event_id or not home_name or not away_name:
            continue

        print(f"   [{i}/{total}] {home_name} vs {away_name}...")

        stats = get_match_stats(event_id)
        if not stats:
            continue

        # Inicializar equipos
        for team in [home_name, away_name]:
            if team not in team_corners:
                team_corners[team] = {
                    "partidos": 0,
                    "corners_favor": 0,
                    "corners_contra": 0,
                }

        # Extraer córners del response
        home_stats = stats.get("home", {}).get("stats", [])
        away_stats = stats.get("away", {}).get("stats", [])

        home_corners = 0
        away_corners = 0

        for stat in home_stats:
            if "corner" in stat.get("name", "").lower():
                try:
                    home_corners = int(stat.get("value", 0) or 0)
                except:
                    pass

        for stat in away_stats:
            if "corner" in stat.get("name", "").lower():
                try:
                    away_corners = int(stat.get("value", 0) or 0)
                except:
                    pass

        # Acumular
        team_corners[home_name]["corners_favor"]  += home_corners
        team_corners[home_name]["corners_contra"] += away_corners
        team_corners[home_name]["partidos"]       += 1

        team_corners[away_name]["corners_favor"]  += away_corners
        team_corners[away_name]["corners_contra"] += home_corners
        team_corners[away_name]["partidos"]       += 1

    # Calcular promedios
    result = {}
    for team, data in team_corners.items():
        p = data["partidos"]
        cf = data["corners_favor"]
        cc = data["corners_contra"]
        ct = cf + cc
        result[team] = {
            "partidos":              p,
            "corners_favor":         cf,
            "corners_contra":        cc,
            "corners_total":         ct,
            "corners_favor_avg":     round(cf / p, 2) if p else 0,
            "corners_contra_avg":    round(cc / p, 2) if p else 0,
            "corners_total_avg":     round(ct / p, 2) if p else 0,
        }
        print(f"   ✅ {team}: {round(cf/p,1) if p else 0} favor / {round(cc/p,1) if p else 0} contra")

    return result


def update_colombia_json(corners_data):
    """Actualiza el JSON existente de Colombia con los datos de córners."""
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)

    updated = 0
    for team_name, corners in corners_data.items():
        # Buscar el equipo en el JSON (nombre puede variar ligeramente)
        matched_key = None
        for key in existing.keys():
            if team_name.lower() in key.lower() or key.lower() in team_name.lower():
                matched_key = key
                break

        if matched_key:
            if "corners" not in existing[matched_key]:
                existing[matched_key]["corners"] = {}
            existing[matched_key]["corners"].update({
                "partidos":           corners["partidos"],
                "promedio":           corners["corners_total_avg"],
                "corners_favor":      corners["corners_favor"],
                "corners_contra":     corners["corners_contra"],
                "corners_total":      corners["corners_total"],
                "corners_favor_avg":  corners["corners_favor_avg"],
                "corners_contra_avg": corners["corners_contra_avg"],
            })
            updated += 1
        else:
            # Crear entrada nueva
            existing[team_name] = {
                "corners": {
                    "partidos":           corners["partidos"],
                    "promedio":           corners["corners_total_avg"],
                    "corners_favor":      corners["corners_favor"],
                    "corners_contra":     corners["corners_contra"],
                    "corners_total":      corners["corners_total"],
                    "corners_favor_avg":  corners["corners_favor_avg"],
                    "corners_contra_avg": corners["corners_contra_avg"],
                }
            }
            updated += 1

    os.makedirs("static", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    return updated


if __name__ == "__main__":
    print("═" * 55)
    print(f"  COLOMBIA CORNERS | Liga BetPlay {SEASON}")
    print(f"  API: Free API Live Football Data (RapidAPI)")
    print("═" * 55 + "\n")

    try:
        fixtures     = get_fixtures()
        corners_data = build_corners_stats(fixtures)
        updated      = update_colombia_json(corners_data)

        print(f"\n✅ ¡COMPLETADO!")
        print("═" * 55)
        print(f"  Equipos actualizados: {updated}")
        print(f"  Archivo: {OUTPUT_FILE}")
        print("═" * 55)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        