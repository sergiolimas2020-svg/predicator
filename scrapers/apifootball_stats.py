#!/usr/bin/env python3
"""
Scraper UNIFICADO de estadísticas por liga vía API-Football.

Reemplaza el scraping frágil de soccerstats (HTML que cambia, 404 por liga,
fallos silenciosos) por la API que el proyecto YA paga. Genera el
`{liga}_stats.json` completo en el formato exacto que espera el motor:

    "Equipo": {
      "position": {"posicion","partidos","ganados","empatados","perdidos",
                   "goles_favor","goles_contra","diferencia","puntos"},
      "goals":    {"over_1_5":"79%","over_2_5":"58%","over_3_5":"16%","bts":"53%"},
      "corners":  {"local":{"partidos","corners_favor","corners_contra"},
                   "visitante":{...}}
    }

Eficiencia: posiciones = 1 request (/standings). Goles = se calculan de los
MARCADORES que ya vienen en /fixtures (0 requests extra). Córners = 1 request
por partido (/fixtures/statistics) — el único costo grande, acotable con
--max-fixtures.

Uso:
  python3 scrapers/apifootball_stats.py colombia
  python3 scrapers/apifootball_stats.py premier --max-fixtures 120
  python3 scrapers/apifootball_stats.py --all            # todas las ligas
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scrapers.api_football.client import APIFootballClient, APIFootballError  # noqa: E402
from scrapers.api_football.danger_signals import _stat_value  # noqa: E402
from scrapers.corners import aggregate_corners  # reutiliza la agregación pura  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("apifootball_stats")

FINISHED = {"FT", "AET", "PEN"}

# liga conocida → (api_football_league_id, season, archivo de salida)
LEAGUES: Dict[str, Any] = {
    "premier":     (39,  2025, "static/england_stats.json"),
    "laliga":      (140, 2025, "static/spain_stats.json"),
    "seriea":      (135, 2025, "static/italy_stats.json"),
    "bundesliga":  (78,  2025, "static/germany_stats.json"),
    "ligue1":      (61,  2025, "static/france_stats.json"),
    "superlig":    (203, 2025, "static/turkey_stats.json"),
    "champions":   (2,   2025, "static/uefa-champions-league_stats.json"),
    "brazil":      (71,  2026, "static/brazil_stats.json"),
    "brazil_b":    (72,  2026, "static/brazil_b_stats.json"),
    "argentina":   (128, 2026, "static/argentina_stats.json"),
    "colombia":    (239, 2026, "static/colombia_stats.json"),
}


# ──────────────────────────────────────────────────────────────────────────
#  Funciones puras (testeables sin red)
# ──────────────────────────────────────────────────────────────────────────
def compute_positions(team_matches: Dict[str, List[Dict[str, int]]]) -> Dict[str, Dict[str, Any]]:
    """Calcula la tabla (posición + récord) desde los partidos del equipo.

    Más robusto que /standings: una sola fuente (fixtures), sin sorpresas de
    formato (p.ej. ligas Apertura/Clausura donde /standings devuelve played=0).
    `team_matches`: {equipo: [{"gf","ga"}, ...]}. Función PURA.
    rank por (puntos, diferencia, goles_favor) desc.
    """
    rows = {}
    for team, matches in team_matches.items():
        g = w = d = l = gf = ga = 0
        for m in matches:
            g += 1; gf += m["gf"]; ga += m["ga"]
            if m["gf"] > m["ga"]:
                w += 1
            elif m["gf"] == m["ga"]:
                d += 1
            else:
                l += 1
        rows[team] = {
            "partidos": g, "ganados": w, "empatados": d, "perdidos": l,
            "goles_favor": gf, "goles_contra": ga, "diferencia": gf - ga,
            "puntos": 3 * w + d,
        }
    # Asignar posición por puntos → diferencia → goles a favor
    order = sorted(rows.items(),
                   key=lambda kv: (kv[1]["puntos"], kv[1]["diferencia"], kv[1]["goles_favor"]),
                   reverse=True)
    for i, (team, row) in enumerate(order, 1):
        row["posicion"] = i
    return rows


def compute_goals(team_matches: Dict[str, List[Dict[str, int]]]) -> Dict[str, Dict[str, str]]:
    """Calcula over_1_5/2_5/3_5 y BTS (%) por equipo desde sus partidos.

    `team_matches`: {equipo: [{"gf":int,"ga":int}, ...]}. Función PURA.
    Over X = % de partidos del equipo con (gf+ga) > X. BTS = % con gf>0 y ga>0.
    Mismo formato string-% que producía soccerstats.
    """
    out: Dict[str, Dict[str, str]] = {}
    for team, matches in team_matches.items():
        n = len(matches)
        if n == 0:
            out[team] = {"over_1_5": "0%", "over_2_5": "0%", "over_3_5": "0%", "bts": "0%"}
            continue
        o15 = sum(1 for m in matches if m["gf"] + m["ga"] > 1.5)
        o25 = sum(1 for m in matches if m["gf"] + m["ga"] > 2.5)
        o35 = sum(1 for m in matches if m["gf"] + m["ga"] > 3.5)
        bts = sum(1 for m in matches if m["gf"] > 0 and m["ga"] > 0)
        pct = lambda x: f"{round(100 * x / n)}%"
        out[team] = {"over_1_5": pct(o15), "over_2_5": pct(o25),
                     "over_3_5": pct(o35), "bts": pct(bts)}
    return out


def fixtures_to_team_matches(fixtures: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, int]]]:
    """De la lista de /fixtures FT, arma {equipo: [{gf,ga}, ...]} (para goles).
    Función PURA."""
    tm: Dict[str, List[Dict[str, int]]] = {}
    for fx in fixtures:
        teams = fx.get("teams", {}) or {}
        h = (teams.get("home") or {}).get("name")
        a = (teams.get("away") or {}).get("name")
        goals = fx.get("goals", {}) or {}
        gh, ga = goals.get("home"), goals.get("away")
        if not h or not a or gh is None or ga is None:
            continue
        tm.setdefault(h, []).append({"gf": gh, "ga": ga})
        tm.setdefault(a, []).append({"gf": ga, "ga": gh})
    return tm


# ──────────────────────────────────────────────────────────────────────────
#  Orquestación (red)
# ──────────────────────────────────────────────────────────────────────────
def build_league(client: APIFootballClient, league_id: int, season: int,
                 out_file: str, max_fixtures: Optional[int] = None) -> Dict[str, int]:
    # 1) Fixtures FT (1 request) → base para posiciones Y goles (0 requests extra)
    fx_resp = client._request("/fixtures", {"league": league_id, "season": season})
    ft = [f for f in fx_resp.get("response", [])
          if (f.get("fixture", {}).get("status", {}) or {}).get("short") in FINISHED]
    team_matches = fixtures_to_team_matches(ft)
    positions = compute_positions(team_matches)   # tabla desde resultados reales
    goals = compute_goals(team_matches)

    # 3) Córners (1 request por partido) — el costo grande, acotable
    corner_fixtures = ft[-max_fixtures:] if max_fixtures else ft
    logger.info("Liga %s: %d partidos FT (córners sobre %d)",
                league_id, len(ft), len(corner_fixtures))
    match_corners = []
    for i, fx in enumerate(corner_fixtures, 1):
        fid = fx.get("fixture", {}).get("id")
        teams = fx.get("teams", {}) or {}
        home, away = (teams.get("home") or {}), (teams.get("away") or {})
        if not fid or not home.get("id") or not away.get("id"):
            continue
        try:
            time.sleep(0.25)
            sresp = client.get_fixture_statistics(fid)
        except APIFootballError as e:
            logger.warning("  stats fixture %s falló: %s", fid, e)
            continue
        by_team = {(b.get("team") or {}).get("id"): _stat_value(b.get("statistics") or [], "corner")
                   for b in sresp.get("response", [])}
        match_corners.append({
            "home": home.get("name"), "away": away.get("name"),
            "home_corners": by_team.get(home.get("id")),
            "away_corners": by_team.get(away.get("id")),
        })
        if i % 50 == 0:
            logger.info("  ...córners %d/%d", i, len(corner_fixtures))
    corners = aggregate_corners(match_corners)

    # 4) Combinar y escribir
    all_teams = set(positions) | set(goals) | set(corners)
    combined: Dict[str, Any] = {}
    for team in all_teams:
        combined[team] = {
            "position": positions.get(team, {}),
            "goals": goals.get(team, {}),
            "corners": corners.get(team, {}),
        }
    from datetime import datetime
    combined["_metadata"] = {
        "fecha_actualizacion": datetime.now().isoformat(),
        "fuente": "API-Football",
        "league_id": league_id,
        "season": season,
        "equipos_extraidos": {
            "positions": len(positions),
            "goals": len(goals),
            "corners": sum(1 for c in corners.values()
                           if c.get("local", {}).get("partidos") or c.get("visitante", {}).get("partidos")),
        },
        "corners_disponibles": bool(corners),
    }
    p = ROOT / out_file
    p.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = combined["_metadata"]["equipos_extraidos"]
    logger.info("✅ %s — posiciones=%d goles=%d córners=%d",
                out_file, counts["positions"], counts["goals"], counts["corners"])
    return counts


def _load_key() -> Optional[str]:
    k = os.environ.get("API_FOOTBALL_KEY")
    if k:
        return k
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("API_FOOTBALL_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("league", nargs="?", help="liga conocida: " + ", ".join(LEAGUES))
    ap.add_argument("--all", action="store_true", help="todas las ligas conocidas")
    ap.add_argument("--max-fixtures", type=int, default=None,
                    help="acota nº de partidos para córners (ahorra cupo/tiempo)")
    args = ap.parse_args()

    key = _load_key()
    if not key:
        logger.error("API_FOOTBALL_KEY no encontrada (env o .env).")
        return 2
    client = APIFootballClient(api_key=key)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    client.session.verify = False

    if args.all:
        targets = list(LEAGUES.items())
    elif args.league and args.league in LEAGUES:
        targets = [(args.league, LEAGUES[args.league])]
    else:
        logger.error("Liga desconocida o no especificada. Conocidas: %s", list(LEAGUES))
        return 2

    rc = 0
    for name, (lid, season, out_file) in targets:
        try:
            build_league(client, lid, season, out_file, max_fixtures=args.max_fixtures)
        except APIFootballError as e:
            logger.error("Liga %s falló: %s", name, e)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
