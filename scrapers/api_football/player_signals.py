"""
Señales individuales de jugador desde API-Football.

Fuente: /fixtures/players sobre fixtures históricos recientes. Si la API no
entrega estos datos para una liga/plan, el colector registra el error y el
motor simplemente no propone props de jugador.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scrapers.api_football.client import APIFootballClient, APIFootballError  # noqa: E402
from scrapers.api_football.danger_signals import _domestic_recent  # noqa: E402


DEFAULT_LOOKBACK = 5
MIN_MINUTES_FOR_APPEARANCE = 15


def _player_stats_block(payload: Dict[str, Any], team_id: int) -> List[Dict[str, Any]]:
    """Extrae la lista `players` del bloque correspondiente al equipo."""
    for block in payload.get("response") or []:
        if ((block.get("team") or {}).get("id")) == team_id:
            return block.get("players") or []
    return []


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return float(default)


def extract_player_shot_signals(
    client: APIFootballClient,
    team_id: int,
    form_fixtures: List[Dict[str, Any]],
    lookback: int = DEFAULT_LOOKBACK,
    logger: Optional[logging.Logger] = None,
    venue: Optional[str] = None,
    include_intl: bool = False,
) -> Dict[str, Any]:
    """Promedios recientes de tiros por jugador.

    Devuelve:
    {
      "venue": "home"|"away"|None,
      "n_fixtures": int,
      "fixture_ids": [...],
      "players": [
        {
          "player_id", "name", "position",
          "appearances", "starts", "minutes_avg",
          "shots_total_avg", "shots_on_target_avg",
          "shots_total_per90", "shots_on_target_per90"
        }
      ],
      "errors": [...]
    }
    """
    log = logger or logging.getLogger("player_signals")
    if not form_fixtures or not team_id:
        return {
            "venue": venue, "n_fixtures": 0, "fixture_ids": [],
            "players": [], "errors": ["sin_form_data"],
        }

    chosen = _domestic_recent(
        form_fixtures, lookback, team_id=team_id, venue=venue, include_intl=include_intl
    )
    by_player: Dict[int, Dict[str, Any]] = {}
    used: List[int] = []
    errors: List[str] = []

    for f in chosen:
        fid = ((f.get("fixture") or {}).get("id"))
        if not fid:
            continue
        try:
            payload = client.get_fixture_players(fid, team=team_id)
        except APIFootballError as e:
            errors.append(f"fixture {fid}: {e}")
            continue

        players = _player_stats_block(payload, team_id)
        if not players:
            continue
        used.append(fid)

        for row in players:
            player = row.get("player") or {}
            pid = player.get("id")
            if not pid:
                continue
            stats = (row.get("statistics") or [{}])[0] or {}
            games = stats.get("games") or {}
            shots = stats.get("shots") or {}
            minutes = _safe_float(games.get("minutes"), 0.0)
            if minutes < MIN_MINUTES_FOR_APPEARANCE:
                continue

            rec = by_player.setdefault(pid, {
                "player_id": pid,
                "name": player.get("name"),
                "position": games.get("position"),
                "appearances": 0,
                "starts": 0,
                "minutes": 0.0,
                "shots_total": 0.0,
                "shots_on_target": 0.0,
                "fixture_ids": [],
            })
            rec["appearances"] += 1
            rec["starts"] += 0 if games.get("substitute") else 1
            rec["minutes"] += minutes
            rec["shots_total"] += _safe_float(shots.get("total"), 0.0)
            rec["shots_on_target"] += _safe_float(shots.get("on"), 0.0)
            rec["fixture_ids"].append(fid)

    out_players = []
    for rec in by_player.values():
        apps = rec["appearances"] or 1
        minutes = rec["minutes"]
        total_avg = rec["shots_total"] / apps
        on_avg = rec["shots_on_target"] / apps
        per90_factor = 90.0 / minutes if minutes > 0 else 0.0
        out_players.append({
            "player_id": rec["player_id"],
            "name": rec["name"],
            "position": rec["position"],
            "appearances": rec["appearances"],
            "starts": rec["starts"],
            "minutes_avg": round(minutes / apps, 1),
            "shots_total_avg": round(total_avg, 2),
            "shots_on_target_avg": round(on_avg, 2),
            "shots_total_per90": round(rec["shots_total"] * per90_factor, 2),
            "shots_on_target_per90": round(rec["shots_on_target"] * per90_factor, 2),
            "fixture_ids": rec["fixture_ids"],
        })

    out_players.sort(
        key=lambda p: (
            p["shots_on_target_avg"],
            p["shots_total_avg"],
            p["minutes_avg"],
        ),
        reverse=True,
    )
    result = {
        "venue": venue,
        "n_fixtures": len(used),
        "fixture_ids": used,
        "players": out_players,
        "errors": errors,
    }
    log.info("    player_shots team=%s venue=%s: players=%d fixtures=%d",
             team_id, venue or "any", len(out_players), len(used))
    return result
