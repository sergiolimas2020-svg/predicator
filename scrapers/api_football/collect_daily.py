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
from scrapers.api_football.danger_signals import extract_danger_signals  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
ODDS_PATH = ROOT / "static" / "odds.json"
LEAGUES_MAP = ROOT / "static" / "api_football" / "leagues_map.json"
TEAMS_MAP = ROOT / "static" / "api_football" / "teams_map.json"
DATA_DIR = ROOT / "static" / "api_football" / "data"

# Motor v1.2 — recolección de indicadores de peligro (tiros a puerta + corners).
# Agrega ~10 requests por partido (5 fixtures × 2 equipos). Sobre el plan Pro
# (7.500/día) sigue siendo holgado. Desactivable si hace falta ahorrar cupo.
COLLECT_DANGER_SIGNALS = True


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


def fixtures_from_apifootball(client, target: date, leagues_map: Dict,
                             tz: str = "America/Bogota") -> List[Dict]:
    """Obtiene los partidos de la fecha DIRECTO de API-Football /fixtures, por
    cada liga mapeada. Independiente de odds.json (The Odds API) — fuente única
    viva. Trae IDs y nombres nativos de API-Football, así no depende del
    teams_map (que está incompleto para ligas sudamericanas).

    Retorna match dicts con home_id/away_id ya resueltos (collect_for_match los
    usa directamente sin mirar teams_map)."""
    date_str = target.isoformat()
    out: List[Dict] = []
    for league_name, info in leagues_map.items():
        lid = info.get("id")
        season = info.get("season")
        if not lid:
            continue
        try:
            resp = client.get_fixtures_by_date(
                date_str, league=lid, season=season, timezone=tz
            ).get("response", [])
        except APIFootballError as e:
            logging.warning("[fixtures] %s (id=%s): %s", league_name, lid, e)
            continue
        for fx in resp or []:
            teams = fx.get("teams") or {}
            home = teams.get("home") or {}
            away = teams.get("away") or {}
            if not home.get("id") or not away.get("id"):
                continue
            out.append({
                "key": f"{home.get('name')}|{away.get('name')}|{date_str}",
                "home": home.get("name"),
                "away": away.get("name"),
                "league": league_name,
                "date": date_str,
                "home_id": home.get("id"),
                "away_id": away.get("id"),
                "league_id": lid,
                "season": season,
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

    # IDs: preferir los que vienen del fixture de API-Football (fuente B1);
    # caer a teams_map solo si el partido no los trae (compatibilidad con
    # la fuente vieja basada en odds.json).
    home_t = teams_map.get(match["home"]) or {}
    away_t = teams_map.get(match["away"]) or {}
    home_id = match.get("home_id") or home_t.get("id")
    away_id = match.get("away_id") or away_t.get("id")
    league_id = match.get("league_id") or league_id
    season = match.get("season") or season

    record: Dict[str, Any] = {
        "key": match["key"],
        "home": match["home"],
        "away": match["away"],
        "league": league,
        "date": match["date"],
        "home_id": home_id,
        "away_id": away_id,
        "league_id": league_id,
        "season": season,
        "h2h": None,
        "home_form": None,
        "away_form": None,
        "home_stats": None,
        "away_stats": None,
        # Indicadores de peligro (motor v1.2 — preparación, aún sin usar)
        "home_danger": None,
        "away_danger": None,
        "errors": [],
    }

    if not home_id or not away_id:
        record["errors"].append("missing_team_mapping")
        log.warning("  · %s vs %s: sin ID de equipo (home=%s away=%s)",
                    match["home"], match["away"],
                    bool(home_id), bool(away_id))
        return record

    # h2h
    try:
        record["h2h"] = client.get_h2h(home_id, away_id, last=10).get("response")
    except APIFootballError as e:
        record["errors"].append(f"h2h: {e}")

    # forma reciente — last=10 (no 5) para que el motor pueda filtrar a
    # los 5 más recientes en liga doméstica aunque haya copas mezcladas.
    try:
        record["home_form"] = client.get_team_last_fixtures(home_id, last=10).get("response")
    except APIFootballError as e:
        record["errors"].append(f"home_form: {e}")
    try:
        record["away_form"] = client.get_team_last_fixtures(away_id, last=10).get("response")
    except APIFootballError as e:
        record["errors"].append(f"away_form: {e}")

    # stats (separa local/visita en goles a favor/contra)
    if league_id and season:
        try:
            record["home_stats"] = client.get_team_statistics(
                home_id, league_id, season).get("response")
        except APIFootballError as e:
            record["errors"].append(f"home_stats: {e}")
        try:
            record["away_stats"] = client.get_team_statistics(
                away_id, league_id, season).get("response")
        except APIFootballError as e:
            record["errors"].append(f"away_stats: {e}")

    # Indicadores de peligro — tiros a puerta y corners de los últimos 5
    # partidos domésticos (motor v1.2, preparación). Reusa los fixtures de
    # form ya descargados; solo agrega las llamadas a /fixtures/statistics.
    if COLLECT_DANGER_SIGNALS:
        try:
            record["home_danger"] = extract_danger_signals(
                client, home_id, record.get("home_form") or [], logger=log)
        except APIFootballError as e:
            record["errors"].append(f"home_danger: {e}")
        try:
            record["away_danger"] = extract_danger_signals(
                client, away_id, record.get("away_form") or [], logger=log)
        except APIFootballError as e:
            record["errors"].append(f"away_danger: {e}")

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

    leagues_map = load_json(LEAGUES_MAP, {})
    teams_map = load_json(TEAMS_MAP, {})

    if not leagues_map:
        log.error("leagues_map.json vacío. Corré scrapers/api_football/mapping.py primero.")
        sys.exit(2)

    client = APIFootballClient()

    # Fuente de partidos: API-Football /fixtures (B1) — independiente de
    # odds.json (The Odds API murió: 401). Si por algún motivo no devuelve
    # nada, cae a la fuente vieja basada en odds.json.
    matches = fixtures_from_apifootball(client, target_date, leagues_map)
    if not matches:
        log.warning("API-Football /fixtures sin partidos — fallback a odds.json")
        odds = load_json(ODDS_PATH, {})
        matches = fixtures_for_target_date(odds, target_date, leagues_map)

    log.info("Partidos a procesar: %d", len(matches))
    if not matches:
        log.info("Nada para hacer.")
        return

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
