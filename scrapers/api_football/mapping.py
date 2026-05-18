"""
Script one-shot para mapear ligas y equipos de PREDIKTOR a IDs de API-Football.

Salidas:
  static/api_football/leagues_map.json  →  liga PREDIKTOR → {id, season, name, country}
  static/api_football/teams_map.json    →  equipo PREDIKTOR → {id, name, league, league_id}

Uso:
  python -m scrapers.api_football.mapping
  o
  python scrapers/api_football/mapping.py

Requiere API_FOOTBALL_KEY en el entorno.
NO se ejecuta en cron. Correr manualmente al inicio de cada temporada o cuando
aparezcan equipos nuevos en odds.json.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# permitir ejecución directa (`python scrapers/api_football/mapping.py`)
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scrapers.api_football.client import APIFootballClient, APIFootballError  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
ODDS_PATH = ROOT / "static" / "odds.json"
OUT_DIR = ROOT / "static" / "api_football"
LEAGUES_OUT = OUT_DIR / "leagues_map.json"
TEAMS_OUT = OUT_DIR / "teams_map.json"

# Ligas PREDIKTOR → criterios para localizarlas en API-Football.
# (NBA queda fuera: API-Football es solo fútbol; NBA sigue con nba_api oficial.)
PREDIKTOR_LEAGUES = {
    "Premier League":   {"name": "Premier League",       "country": "England"},
    "La Liga":          {"name": "La Liga",              "country": "Spain"},
    "Serie A":          {"name": "Serie A",              "country": "Italy"},
    "Bundesliga":       {"name": "Bundesliga",           "country": "Germany"},
    "Ligue 1":          {"name": "Ligue 1",              "country": "France"},
    "Champions League": {"name": "UEFA Champions League","country": "World"},
    "Liga Argentina":   {"name": "Liga Profesional Argentina", "country": "Argentina"},
    "Brasileirao":      {"name": "Serie A",              "country": "Brazil"},
    "Super Lig":        {"name": "Süper Lig",            "country": "Turkey"},
    "Copa Libertadores":{"name": "CONMEBOL Libertadores","country": "World"},
    "Copa Sudamericana":{"name": "CONMEBOL Sudamericana","country": "World"},
    "Liga Colombiana":  {"name": "Primera A",            "country": "Colombia"},
}

MIN_FUZZY_RATIO = 0.72

# Overrides manuales para equipos donde API-Football usa un nombre legacy o
# distinto al de The Odds API. Clave: nombre PREDIKTOR (como aparece en odds.json).
# Valor: ID del equipo en API-Football.
MANUAL_TEAM_OVERRIDES: Dict[str, int] = {
    # Montevideo City Torque ↔ Atletico Torque (nombre pre-rebrand 2017)
    "Montevideo City Torque": 2365,
}


# ─────────────────────────────────────────────────────────────── helpers

def _norm(s: str) -> str:
    """Normaliza nombres: minúsculas, sin acentos, sin sufijos comunes."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    # quita sufijos típicos que API-Football a veces incluye
    s = re.sub(r"\b(fc|cf|ac|sc|club|de|cd|sad|ssd|ssc|asd|cs|c\.f\.|f\.c\.)\b",
               " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _best_match(target: str, candidates: List[Dict]) -> Tuple[Optional[Dict], float]:
    best, best_r = None, 0.0
    tn = _norm(target)
    for c in candidates:
        for field in ("name", "code"):
            v = c.get(field)
            if not v:
                continue
            r = SequenceMatcher(None, tn, _norm(v)).ratio()
            # bonus si una contiene a la otra como substring
            if tn and _norm(v) and (tn in _norm(v) or _norm(v) in tn):
                r = max(r, 0.90)
            if r > best_r:
                best_r, best = r, c
    return best, best_r


# ─────────────────────────────────────────────────────────── league mapping

def find_league(client: APIFootballClient, predictor_name: str, criteria: Dict) -> Optional[Dict]:
    """Busca la liga vigente en API-Football. Retorna dict con id, season, name, country."""
    name = criteria["name"]
    country = criteria["country"]

    # current=true devuelve solo ligas con temporada activa
    payload = client.get_leagues(name=name, country=country, current="true")
    candidates = payload.get("response", [])

    if not candidates:
        # algunas ligas (Champions, Libertadores) usan country='World'
        payload = client.get_leagues(name=name, current="true")
        candidates = payload.get("response", [])

    if not candidates:
        logging.warning("Sin candidatos para liga %s (%s, %s)",
                        predictor_name, name, country)
        return None

    # tomar la temporada current=true del primer match razonable
    for cand in candidates:
        league = cand.get("league", {})
        seasons = cand.get("seasons", [])
        country_obj = cand.get("country", {})
        # priorizar match exacto de país
        if country and country_obj.get("name", "").lower() != country.lower() \
                and country.lower() != "world":
            continue
        active_season = next((s for s in seasons if s.get("current")), None)
        if not active_season:
            continue
        return {
            "id": league.get("id"),
            "season": active_season.get("year"),
            "name": league.get("name"),
            "country": country_obj.get("name"),
        }

    # último recurso: primer candidato con cualquier season
    cand = candidates[0]
    league = cand.get("league", {})
    season = next((s for s in cand.get("seasons", []) if s.get("current")), None)
    if not season and cand.get("seasons"):
        season = cand["seasons"][-1]
    return {
        "id": league.get("id"),
        "season": (season or {}).get("year"),
        "name": league.get("name"),
        "country": cand.get("country", {}).get("name"),
    }


# ─────────────────────────────────────────────────────────── team mapping

def fetch_teams_for_league(client: APIFootballClient, league_id: int, season: int) -> List[Dict]:
    """Devuelve lista normalizada de equipos {id, name}."""
    payload = client.get_teams(league=league_id, season=season)
    teams = []
    for t in payload.get("response", []):
        team = t.get("team", {})
        if team.get("id") and team.get("name"):
            teams.append({
                "id": team["id"],
                "name": team["name"],
                "code": team.get("code"),
            })
    return teams


def collect_predictor_teams(odds_path: Path) -> Dict[str, set]:
    """Lee odds.json y agrupa nombres de equipos por liga PREDIKTOR."""
    if not odds_path.exists():
        logging.warning("odds.json no encontrado en %s", odds_path)
        return {}
    raw = json.loads(odds_path.read_text())
    by_league: Dict[str, set] = {}
    for ev in raw.values():
        if not isinstance(ev, dict):
            continue
        league = ev.get("league")
        if not league or league == "NBA":
            continue
        by_league.setdefault(league, set())
        for k in ("home", "away"):
            v = ev.get(k)
            if v:
                by_league[league].add(v)
    return by_league


# ────────────────────────────────────────────────────────────────── runner

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    log = logging.getLogger("mapping")

    if not os.environ.get("API_FOOTBALL_KEY"):
        log.error("API_FOOTBALL_KEY no está en el entorno. Abortando.")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = APIFootballClient()

    # 1. Sanity check: status
    try:
        status = client.get_status()
        acct = (status.get("response") or {}).get("account", {})
        sub = (status.get("response") or {}).get("subscription", {})
        req = (status.get("response") or {}).get("requests", {})
        log.info("Cuenta: %s | plan: %s | requests hoy: %s/%s",
                 acct.get("email"), sub.get("plan"),
                 req.get("current"), req.get("limit_day"))
    except APIFootballError as e:
        log.error("get_status falló: %s", e)
        sys.exit(2)

    # 2. Mapeo de ligas
    leagues_map: Dict[str, Dict] = {}
    log.info("─── mapeando %d ligas ───", len(PREDIKTOR_LEAGUES))
    for predictor_name, criteria in PREDIKTOR_LEAGUES.items():
        try:
            info = find_league(client, predictor_name, criteria)
        except APIFootballError as e:
            log.error("Error buscando %s: %s", predictor_name, e)
            info = None
        if info and info.get("id") and info.get("season"):
            leagues_map[predictor_name] = info
            log.info("  ✓ %-22s → id=%s season=%s name='%s' country='%s'",
                     predictor_name, info["id"], info["season"],
                     info.get("name"), info.get("country"))
        else:
            log.warning("  ✗ %s sin match utilizable", predictor_name)

    LEAGUES_OUT.write_text(json.dumps(leagues_map, ensure_ascii=False, indent=2))
    log.info("Escrito %s (%d ligas)", LEAGUES_OUT, len(leagues_map))

    # 3. Mapeo de equipos contra odds.json
    predictor_by_league = collect_predictor_teams(ODDS_PATH)
    log.info("─── mapeando equipos (%d ligas con datos en odds.json) ───",
             len(predictor_by_league))

    teams_map: Dict[str, Dict] = {}
    coverage: Dict[str, Dict] = {}

    for predictor_name, info in leagues_map.items():
        predictor_teams = predictor_by_league.get(predictor_name, set())
        if not predictor_teams:
            log.info("  · %s: sin equipos en odds.json (skip teams)",
                     predictor_name)
            coverage[predictor_name] = {
                "total_predictor": 0, "matched": 0, "unmatched": []
            }
            continue

        try:
            api_teams = fetch_teams_for_league(client, info["id"], info["season"])
        except APIFootballError as e:
            log.error("  ✗ %s fetch_teams error: %s", predictor_name, e)
            continue

        matched, unmatched = 0, []
        for pred_team in sorted(predictor_teams):
            override_id = MANUAL_TEAM_OVERRIDES.get(pred_team)
            if override_id:
                api_team = next((t for t in api_teams if t["id"] == override_id), None)
                if api_team:
                    teams_map[pred_team] = {
                        "id": api_team["id"],
                        "name": api_team["name"],
                        "league": predictor_name,
                        "league_id": info["id"],
                        "season": info["season"],
                        "match_ratio": 1.0,
                        "override": True,
                    }
                    matched += 1
                    continue
            best, ratio = _best_match(pred_team, api_teams)
            if best and ratio >= MIN_FUZZY_RATIO:
                teams_map[pred_team] = {
                    "id": best["id"],
                    "name": best["name"],
                    "league": predictor_name,
                    "league_id": info["id"],
                    "season": info["season"],
                    "match_ratio": round(ratio, 3),
                }
                matched += 1
            else:
                unmatched.append({
                    "name": pred_team,
                    "best_guess": (best or {}).get("name"),
                    "ratio": round(ratio, 3) if best else 0.0,
                })

        coverage[predictor_name] = {
            "total_predictor": len(predictor_teams),
            "matched": matched,
            "unmatched": unmatched,
        }
        log.info("  · %-22s matched=%d/%d (%s sin match)",
                 predictor_name, matched, len(predictor_teams),
                 len(unmatched) if unmatched else 0)

    TEAMS_OUT.write_text(json.dumps(teams_map, ensure_ascii=False, indent=2))
    log.info("Escrito %s (%d equipos)", TEAMS_OUT, len(teams_map))

    # 4. Reporte de coverage
    log.info("─── COVERAGE ───")
    total_pred = sum(c["total_predictor"] for c in coverage.values())
    total_match = sum(c["matched"] for c in coverage.values())
    pct = (total_match / total_pred * 100) if total_pred else 0
    log.info("Global: %d/%d equipos mapeados (%.1f%%)", total_match, total_pred, pct)
    for league, c in coverage.items():
        if c["unmatched"]:
            log.info("  %s — sin match: %s", league,
                     ", ".join(u["name"] for u in c["unmatched"]))

    # cupo restante reportado por el último request
    log.info("Requests diarios restantes (post-mapping): %s",
             client.requests_remaining)


if __name__ == "__main__":
    main()
