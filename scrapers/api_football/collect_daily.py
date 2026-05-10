"""
Recolección diaria desde API-Football, en paralelo al motor actual.

NO se llama desde el cron todavía: corre on-demand para validar datos.
Para activarlo en producción se enganchará al workflow después de verificar
que cubre todos los partidos de odds.json sin reventar el cupo diario.

Estimación de carga:
  ~30 partidos/día × 5 requests (h2h + 2× last5 + 2× statistics) ≈ 150/día
  Plan Pro: 7.500/día → margen amplio.

Salida:
  static/api_football/data/{YYYY-MM-DD}.json
  Estructura por partido:
    {
      "fixture_id": int|null,
      "home": str, "away": str, "league": str,
      "h2h": [...], "home_form": [...], "away_form": [...],
      "home_stats": {...}, "away_stats": {...},
      "errors": [str]   # endpoints que fallaron
    }
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scrapers.api_football.client import (  # noqa: E402
    APIFootballClient,
    APIFootballError,
    APIFootballRateLimitError,
)


ROOT = Path(__file__).resolve().parents[2]
ODDS_PATH = ROOT / "static" / "odds.json"
LEAGUES_MAP = ROOT / "static" / "api_football" / "leagues_map.json"
TEAMS_MAP = ROOT / "static" / "api_football" / "teams_map.json"
DATA_DIR = ROOT / "static" / "api_football" / "data"


def load_json(p: Path, default):
    if not p.exists():
        return default
    return json.loads(p.read_text())


def parse_iso_date(s: str) -> Optional[date]:
    try:
        return datetime.fromisoformat(s).date()
    except (TypeError, ValueError):
        return None


def fixtures_for_target_date(odds: Dict, target: date, leagues_map: Dict) -> List[Dict]:
    """Filtra eventos de odds.json que caen en la fecha objetivo y tienen liga mapeada."""
    out = []
    for k, ev in odds.items():
        if not isinstance(ev, dict):
            continue
        league = ev.get("league")
        if league not in leagues_map:
            continue
        d = parse_iso_date(ev.get("date", ""))
        if d != target:
            continue
        out.append({
            "key": k,
            "home": ev.get("home"),
            "away": ev.get("away"),
            "league": league,
            "date": ev.get("date"),
        })
    return out


def collect_for_match(
    client: APIFootballClient,
    match: Dict,
    teams_map: Dict,
    leagues_map: Dict,
    log: logging.Logger,
) -> Dict[str, Any]:
    league = match["league"]
    league_info = leagues_map.get(league, {})
    league_id = league_info.get("id")
    season = league_info.get("season")

    home_t = teams_map.get(match["home"]) or {}
    away_t = teams_map.get(match["away"]) or {}

    record: Dict[str, Any] = {
        "key": match["key"],
        "home": match["home"],
        "away": match["away"],
        "league": league,
        "date": match["date"],
        "home_id": home_t.get("id"),
        "away_id": away_t.get("id"),
        "league_id": league_id,
        "season": season,
        "h2h": None,
        "home_form": None,
        "away_form": None,
        "home_stats": None,
        "away_stats": None,
        "errors": [],
    }

    if not home_t.get("id") or not away_t.get("id"):
        record["errors"].append("missing_team_mapping")
        log.warning("  · %s vs %s: sin mapeo de equipo (home=%s away=%s)",
                    match["home"], match["away"],
                    bool(home_t.get("id")), bool(away_t.get("id")))
        return record

    # h2h
    try:
        record["h2h"] = client.get_h2h(home_t["id"], away_t["id"], last=10).get("response")
    except APIFootballError as e:
        record["errors"].append(f"h2h: {e}")

    # forma reciente — last=10 (no 5) para que el motor pueda filtrar a
    # los 5 más recientes en liga doméstica aunque haya copas mezcladas.
    try:
        record["home_form"] = client.get_team_last_fixtures(home_t["id"], last=10).get("response")
    except APIFootballError as e:
        record["errors"].append(f"home_form: {e}")
    try:
        record["away_form"] = client.get_team_last_fixtures(away_t["id"], last=10).get("response")
    except APIFootballError as e:
        record["errors"].append(f"away_form: {e}")

    # stats (separa local/visita en goles a favor/contra)
    if league_id and season:
        try:
            record["home_stats"] = client.get_team_statistics(
                home_t["id"], league_id, season).get("response")
        except APIFootballError as e:
            record["errors"].append(f"home_stats: {e}")
        try:
            record["away_stats"] = client.get_team_statistics(
                away_t["id"], league_id, season).get("response")
        except APIFootballError as e:
            record["errors"].append(f"away_stats: {e}")

    return record


def main(target: Optional[str] = None):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    log = logging.getLogger("collect_daily")

    if not os.environ.get("API_FOOTBALL_KEY"):
        log.error("API_FOOTBALL_KEY no está en el entorno. Abortando.")
        sys.exit(1)

    target_date = (
        datetime.fromisoformat(target).date() if target
        else date.today() + timedelta(days=1)
    )
    log.info("Recolectando data para %s", target_date.isoformat())

    odds = load_json(ODDS_PATH, {})
    leagues_map = load_json(LEAGUES_MAP, {})
    teams_map = load_json(TEAMS_MAP, {})

    if not leagues_map:
        log.error("leagues_map.json vacío. Corré scrapers/api_football/mapping.py primero.")
        sys.exit(2)

    matches = fixtures_for_target_date(odds, target_date, leagues_map)
    log.info("Partidos a procesar: %d", len(matches))
    if not matches:
        log.info("Nada para hacer.")
        return

    client = APIFootballClient()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{target_date.isoformat()}.json"

    out: List[Dict[str, Any]] = []
    for i, m in enumerate(matches, 1):
        log.info("[%d/%d] %s vs %s (%s)", i, len(matches),
                 m["home"], m["away"], m["league"])
        try:
            rec = collect_for_match(client, m, teams_map, leagues_map, log)
        except APIFootballRateLimitError as e:
            log.error("Rate limit alcanzado (%s). Detengo recolección.", e)
            break
        out.append(rec)

    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    log.info("Escrito %s (%d registros)", out_path, len(out))
    log.info("Requests diarios restantes: %s", client.requests_remaining)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(arg)
