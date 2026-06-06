#!/usr/bin/env python3
"""
Scraper UNIFICADO de córners por liga vía API-Football.

Motivación: soccerstats no publica córners para varias ligas (Colombia,
Argentina, Champions → tid=cr da 404). Antes había dos scripts a medio terminar
(colombia_corners.py con RapidAPI, argentina_corners.py con APISPORTS_KEY) que
además producían una estructura PLANA incompatible con el motor/frontend, que
espera:

    "corners": {
      "local":     {"partidos": N, "corners_favor": X.X, "corners_contra": X.X},
      "visitante": {"partidos": N, "corners_favor": X.X, "corners_contra": X.X}
    }

Este módulo usa API-Football (la misma fuente y key — API_FOOTBALL_KEY — que el
resto del proyecto), agrega córners SEPARADOS por sede (local/visitante) y los
FUSIONA en el `{liga}_stats.json` existente sin tocar goles/posiciones. Si no
hay datos, registra un WARNING y NO escribe córners vacíos en silencio.

Uso:
  python3 scrapers/corners.py colombia       # liga conocida (ver LEAGUES)
  python3 scrapers/corners.py --league-id 239 --out static/colombia_stats.json
  python3 scrapers/corners.py colombia --max-fixtures 25   # acotar (pruebas/quota)
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("corners")

SEASON_DEFAULT = 2026
# Ligas conocidas → (api_football_league_id, archivo de salida)
LEAGUES = {
    "colombia":  (239, "static/colombia_stats.json"),
    "argentina": (128, "static/argentina_stats.json"),
}
FINISHED = {"FT", "AET", "PEN"}


# ──────────────────────────────────────────────────────────────────────────
#  Agregación (PURA, testeable sin red)
# ──────────────────────────────────────────────────────────────────────────
def aggregate_corners(matches: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Agrega córners por equipo SEPARADOS por sede.

    `matches`: lista de {home, away, home_corners, away_corners} (córners ya
    extraídos por partido; None si no hay dato → se ignora ese partido).
    Devuelve {equipo: {local:{partidos,corners_favor,corners_contra},
                       visitante:{...}}} con PROMEDIOS por partido (2 decimales).
    """
    acc: Dict[str, Dict[str, Dict[str, float]]] = {}

    def bucket(team):
        return acc.setdefault(team, {
            "local":     {"partidos": 0, "cf": 0, "cc": 0},
            "visitante": {"partidos": 0, "cf": 0, "cc": 0},
        })

    for m in matches:
        h, a = m.get("home"), m.get("away")
        hc, ac = m.get("home_corners"), m.get("away_corners")
        if not h or not a or hc is None or ac is None:
            continue
        bh = bucket(h)["local"]
        bh["partidos"] += 1; bh["cf"] += hc; bh["cc"] += ac
        ba = bucket(a)["visitante"]
        ba["partidos"] += 1; ba["cf"] += ac; ba["cc"] += hc

    out: Dict[str, Dict[str, Any]] = {}
    for team, sides in acc.items():
        entry = {}
        for side, d in sides.items():
            p = d["partidos"]
            entry[side] = {
                "partidos": p,
                "corners_favor":  round(d["cf"] / p, 2) if p else 0.0,
                "corners_contra": round(d["cc"] / p, 2) if p else 0.0,
            }
        out[team] = entry
    return out


# ──────────────────────────────────────────────────────────────────────────
#  Red (API-Football)
# ──────────────────────────────────────────────────────────────────────────
def fetch_match_corners(client: APIFootballClient, league_id: int, season: int,
                        max_fixtures: Optional[int] = None) -> List[Dict[str, Any]]:
    """Trae los partidos FT de la liga y extrae córners local/visitante por
    partido. Devuelve la lista para aggregate_corners()."""
    resp = client._request("/fixtures", {"league": league_id, "season": season})
    fixtures = [fx for fx in resp.get("response", [])
                if (fx.get("fixture", {}).get("status", {}) or {}).get("short") in FINISHED]
    if max_fixtures:
        fixtures = fixtures[-max_fixtures:]
    logger.info("Liga %s: %d partidos FT", league_id, len(fixtures))

    matches = []
    for i, fx in enumerate(fixtures, 1):
        fid = fx.get("fixture", {}).get("id")
        teams = fx.get("teams", {}) or {}
        home = (teams.get("home") or {}); away = (teams.get("away") or {})
        if not fid or not home.get("id") or not away.get("id"):
            continue
        try:
            time.sleep(0.25)
            sresp = client.get_fixture_statistics(fid)
        except APIFootballError as e:
            logger.warning("  stats fixture %s falló: %s", fid, e)
            continue
        by_team = {}
        for block in sresp.get("response", []):
            tid = (block.get("team") or {}).get("id")
            by_team[tid] = _stat_value(block.get("statistics") or [], "corner")
        matches.append({
            "home": home.get("name"), "away": away.get("name"),
            "home_corners": by_team.get(home.get("id")),
            "away_corners": by_team.get(away.get("id")),
        })
        if i % 25 == 0:
            logger.info("  ...%d/%d", i, len(fixtures))
    return matches


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def merge_into_stats(out_file: str, corners_by_team: Dict[str, Dict[str, Any]]) -> int:
    """Fusiona córners en {liga}_stats.json existente (sin tocar goles/posiciones).
    Empareja por nombre normalizado. Actualiza _metadata. Devuelve nº equipos
    con córners fusionados."""
    p = ROOT / out_file
    existing = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    keys = [k for k in existing if not k.startswith("_")]
    norm_index = {_norm(k): k for k in keys}

    merged = 0
    for team, corners in corners_by_team.items():
        if corners["local"]["partidos"] == 0 and corners["visitante"]["partidos"] == 0:
            continue
        key = norm_index.get(_norm(team))
        if key is None:
            # match parcial por substring
            nt = _norm(team)
            key = next((k for k in keys if nt and (nt in _norm(k) or _norm(k) in nt)), None)
        if key is None:
            existing[team] = {"corners": corners, "goals": {}, "position": {}}
        else:
            existing.setdefault(key, {}).setdefault("corners", {})
            existing[key]["corners"] = corners
        merged += 1

    meta = existing.setdefault("_metadata", {})
    meta.setdefault("equipos_extraidos", {})["corners"] = merged
    meta["corners_disponibles"] = merged > 0
    meta.setdefault("fuente_datos", {})["corners"] = "API-Football /fixtures/statistics"
    p.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def _load_key() -> Optional[str]:
    k = os.environ.get("API_FOOTBALL_KEY") or os.environ.get("APISPORTS_KEY")
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
    ap.add_argument("--league-id", type=int)
    ap.add_argument("--out")
    ap.add_argument("--season", type=int, default=SEASON_DEFAULT)
    ap.add_argument("--max-fixtures", type=int, default=None)
    args = ap.parse_args()

    if args.league:
        if args.league not in LEAGUES:
            logger.error("Liga desconocida '%s'. Conocidas: %s", args.league, list(LEAGUES))
            return 2
        league_id, out_file = LEAGUES[args.league]
    elif args.league_id and args.out:
        league_id, out_file = args.league_id, args.out
    else:
        logger.error("Especifica una liga conocida o --league-id + --out")
        return 2

    key = _load_key()
    if not key:
        logger.error("API_FOOTBALL_KEY no encontrada (env o .env).")
        return 2
    client = APIFootballClient(api_key=key)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    client.session.verify = False

    matches = fetch_match_corners(client, league_id, args.season, args.max_fixtures)
    corners = aggregate_corners(matches)
    if not corners:
        logger.warning("⚠️ Sin córners para league_id=%s — no se modifica %s",
                       league_id, out_file)
        return 1
    merged = merge_into_stats(out_file, corners)
    logger.info("✅ Córners fusionados en %s: %d equipos", out_file, merged)
    return 0


if __name__ == "__main__":
    sys.exit(main())
