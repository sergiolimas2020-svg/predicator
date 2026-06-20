"""
Extracción de "indicadores de peligro" desde API-Football.

Motor v1.2 — PREPARACIÓN (Acción 3). Apunta a sumar señal predictiva más
allá del resultado del partido: tiros a puerta (shots on target) y corners
de los últimos N partidos en liga doméstica de cada equipo.

Estos indicadores NO se usan todavía en el modelo (h_score). Se recolectan
durante el shadow mode de 14 días. Si al día 14 el Brier Score no baja de
0.24, se integran formalmente en la fórmula (Acción 4).

Endpoint usado: /fixtures/statistics (1 request por fixture).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scrapers.api_football.client import APIFootballClient, APIFootballError  # noqa: E402


# IDs de torneos NO domésticos (la señal se mide solo en liga doméstica,
# coherente con el Filtro 1 del motor).
INTL_LEAGUE_IDS = {
    2, 3, 848,        # UEFA Champions / Europa / Conference
    13, 11,           # CONMEBOL Libertadores / Sudamericana
    9, 1, 4, 32,      # Copa America / WC / Euro / WC qualifiers
    34, 15, 22, 480,  # CONCACAF / FIFA Club WC / otros
}

DEFAULT_LOOKBACK = 5


def _stat_value(statistics: List[Dict], *names: str) -> Optional[float]:
    """Busca un stat por nombre (substring, case-insensitive). Número o None."""
    for s in statistics or []:
        t = (s.get("type") or "").lower()
        if any(n in t for n in names):
            v = s.get("value")
            if v is None:
                return None
            try:
                return float(str(v).replace("%", "").strip())
            except (ValueError, TypeError):
                return None
    return None


def _domestic_recent(form_fixtures: List[Dict], lookback: int,
                     team_id: Optional[int] = None,
                     venue: Optional[str] = None,
                     include_intl: bool = False) -> List[Dict]:
    """Últimos `lookback` fixtures domésticos terminados, más reciente primero.

    Si se pasa `venue` ("home"|"away") y `team_id`, filtra solo los partidos
    donde el equipo jugó en esa localía. Esto implementa el método de córners
    por localía: para el local de un partido se miran sus últimos N DE LOCAL,
    para el visitante sus últimos N DE VISITANTE."""
    domestic = []
    for f in form_fixtures or []:
        lid = ((f.get("league") or {}).get("id"))
        if lid in INTL_LEAGUE_IDS and not include_intl:
            continue
        status = ((f.get("fixture") or {}).get("status") or {}).get("short")
        if status not in ("FT", "AET", "PEN"):
            continue
        if venue and team_id:
            teams = f.get("teams") or {}
            is_home = ((teams.get("home") or {}).get("id")) == team_id
            if venue == "home" and not is_home:
                continue
            if venue == "away" and is_home:
                continue
        domestic.append(f)
    domestic.sort(
        key=lambda f: (f.get("fixture") or {}).get("date") or "",
        reverse=True,
    )
    return domestic[:lookback]


def extract_danger_signals(
    client: APIFootballClient,
    team_id: int,
    form_fixtures: List[Dict],
    lookback: int = DEFAULT_LOOKBACK,
    logger: Optional[logging.Logger] = None,
    venue: Optional[str] = None,
    include_intl: bool = False,
) -> Dict[str, Any]:
    """Promedio de tiros a puerta y corners de un equipo en sus últimos
    `lookback` partidos domésticos.

    Args:
      client:        APIFootballClient ya autenticado.
      team_id:       ID del equipo en API-Football.
      form_fixtures: lista de fixtures (salida de get_team_last_fixtures).
      lookback:      cuántos partidos domésticos considerar.

    Returns:
      {
        "shots_on_target_avg": float|None,
        "corners_avg":         float|None,
        "n_fixtures":          int,
        "fixture_ids":         [int, ...],
        "errors":              [str, ...],
      }
    """
    log = logger or logging.getLogger("danger_signals")
    if not form_fixtures or not team_id:
        return {
            "shots_on_target_avg": None, "corners_avg": None, "venue": venue,
            "n_fixtures": 0, "fixture_ids": [], "errors": ["sin_form_data"],
        }

    chosen = _domestic_recent(
        form_fixtures, lookback, team_id=team_id, venue=venue, include_intl=include_intl
    )
    shots: List[float] = []
    corners: List[float] = []
    used: List[int] = []
    errors: List[str] = []

    for f in chosen:
        fid = ((f.get("fixture") or {}).get("id"))
        if not fid:
            continue
        try:
            payload = client.get_fixture_statistics(fid, team=team_id)
        except APIFootballError as e:
            errors.append(f"fixture {fid}: {e}")
            continue
        resp = payload.get("response") or []
        block = None
        for b in resp:
            if ((b.get("team") or {}).get("id")) == team_id:
                block = b
                break
        if block is None and resp:
            block = resp[0]
        if not block:
            continue
        stats = block.get("statistics") or []
        sot = _stat_value(stats, "shots on goal", "shots on target")
        cor = _stat_value(stats, "corner")
        if sot is not None:
            shots.append(sot)
        if cor is not None:
            corners.append(cor)
        used.append(fid)

    def _avg(xs: List[float]) -> Optional[float]:
        return round(sum(xs) / len(xs), 2) if xs else None

    result = {
        "shots_on_target_avg": _avg(shots),
        "corners_avg": _avg(corners),
        "venue": venue,
        "n_fixtures": len(used),
        "fixture_ids": used,
        "errors": errors,
    }
    log.info("    danger_signals team=%s venue=%s: SoT=%s corners=%s (n=%d)",
             team_id, venue or "any", result["shots_on_target_avg"],
             result["corners_avg"], result["n_fixtures"])
    return result
