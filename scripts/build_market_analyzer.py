#!/usr/bin/env python3
"""Construye el analizador universal de mercados para el chat PREDIKTOR.

El motor calcula primero; el chat solo explica. Este script toma los datos ya
guardados por API-Football y deja un JSON consultable por mercado/linea:

- corners totales del partido
- corners por equipo
- tiros a puerta totales
- tiros a puerta por equipo

Cada mercado incluye variables usadas, tabla de lineas, linea ideal y muestra.
"""
from __future__ import annotations

import json
import math
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
DATA_DIR = STATIC / "api_football" / "data"
OUT = STATIC / "market_analyzer.json"
SELECTION_SOURCES = [
    (STATIC / "worldcup_stats.json", STATIC / "worldcup_fixtures.json", "worldcup_stats.json"),
    (STATIC / "friendlies_stats.json", STATIC / "friendlies_fixtures.json", "friendlies_stats.json"),
]

MIN_SAMPLE = 4
SELECTION_MIN_SAMPLE = 2
LOW_SAMPLE_CONFIDENCE_FACTOR = 0.85
IDEAL_MIN_CONFIDENCE = 60.0

TOTAL_CORNERS_LINES = [5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5]
TEAM_CORNERS_LINES = [2.5, 3.5, 4.5, 5.5, 6.5]
TOTAL_SHOTS_LINES = [5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]
TEAM_SHOTS_LINES = [1.5, 2.5, 3.5, 4.5, 5.5]
PLAYER_TOTAL_LINES = [0.5, 1.5, 2.5, 3.5]
PLAYER_SOT_LINES = [0.5, 1.5]
PLAYER_MIN_APPS = 2
PLAYER_MIN_MINUTES = 30.0


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def norm(value: Any) -> str:
    text = str(value or "").lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text).split())


def poisson_over_probability(lam: float | int | None, line: float | int) -> float | None:
    if lam is None:
        return None
    lam = float(lam)
    if lam < 0:
        return None
    min_hits = math.floor(float(line)) + 1
    term = math.exp(-lam)
    cdf = term
    for k in range(1, min_hits):
        term *= lam / k
        cdf += term
    return round(max(0.0, min(100.0, (1.0 - cdf) * 100.0)), 1)


def verdict(prob: float | None) -> str:
    if prob is None:
        return "SIN DATO"
    if prob >= 60.0:
        return "SI"
    if prob >= 52.0:
        return "JUSTO"
    return "NO"


def stake(prob: float | None) -> dict[str, str]:
    if prob is None:
        return {"stake": "0u", "label": "Sin dato"}
    if prob >= 70:
        return {"stake": "0.50u", "label": "Stake bajo-moderado"}
    if prob >= 60:
        return {"stake": "0.25u", "label": "Stake bajo"}
    if prob >= 52:
        return {"stake": "0.10u", "label": "Muy bajo"}
    return {"stake": "0u", "label": "No tomar"}


def line_table(lam: float, lines: list[float], confidence_factor: float = 1.0) -> list[dict[str, Any]]:
    out = []
    for line in lines:
        raw_prob = poisson_over_probability(lam, line)
        prob = round(raw_prob * confidence_factor, 1) if raw_prob is not None else None
        out.append({
            "line": line,
            "prob": prob,
            "raw_prob": raw_prob,
            "confidence_factor": round(confidence_factor, 2),
            "verdict": verdict(prob),
            **stake(prob),
        })
    return out


def ideal_line(lam: float, lines: list[float], confidence_factor: float = 1.0) -> dict[str, Any] | None:
    best = None
    for item in line_table(lam, lines, confidence_factor):
        if item["prob"] is not None and item["prob"] >= IDEAL_MIN_CONFIDENCE:
            best = item
    return best


def finite(value: Any) -> float | None:
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass
    return None


def sample_ok(*danger_blocks: dict[str, Any]) -> bool:
    return all((block.get("n_fixtures") or 0) >= MIN_SAMPLE for block in danger_blocks)


def sample_ok_for(min_sample: int, *danger_blocks: dict[str, Any]) -> bool:
    return all((block.get("n_fixtures") or 0) >= min_sample for block in danger_blocks)


def market_entry(
    *,
    key: str,
    label: str,
    metric: str,
    scope: str,
    lam: float,
    lines: list[float],
    variables: dict[str, Any],
    confidence_factor: float = 1.0,
) -> dict[str, Any]:
    table = line_table(lam, lines, confidence_factor)
    ideal = ideal_line(lam, lines, confidence_factor)
    return {
        "key": key,
        "label": label,
        "metric": metric,
        "scope": scope,
        "lambda": round(lam, 2),
        "method": "poisson_recent_averages",
        "min_sample": MIN_SAMPLE,
        "ideal_min_confidence": IDEAL_MIN_CONFIDENCE,
        "confidence_factor": round(confidence_factor, 2),
        "ideal_line": ideal,
        "line_table": table,
        "variables": variables,
    }


def build_for_record(record: dict[str, Any]) -> dict[str, Any] | None:
    home = record.get("home") or record.get("home_name")
    away = record.get("away") or record.get("away_name")
    if not home or not away:
        return None

    home_danger = record.get("home_danger") or {}
    away_danger = record.get("away_danger") or {}
    home_player_shots = record.get("home_player_shots") or {}
    away_player_shots = record.get("away_player_shots") or {}
    markets: list[dict[str, Any]] = []
    source_file = record.get("_source_file") or ""
    is_selection = source_file in {"worldcup_stats.json", "friendlies_stats.json"}
    min_sample = SELECTION_MIN_SAMPLE if is_selection else MIN_SAMPLE
    min_pair_sample = min(
        int(home_danger.get("n_fixtures") or 0),
        int(away_danger.get("n_fixtures") or 0),
    )
    confidence_factor = LOW_SAMPLE_CONFIDENCE_FACTOR if is_selection and min_pair_sample < MIN_SAMPLE else 1.0

    if sample_ok_for(min_sample, home_danger, away_danger):
        home_corners = finite(home_danger.get("corners_avg"))
        away_corners = finite(away_danger.get("corners_avg"))
        home_shots = finite(home_danger.get("shots_on_target_avg"))
        away_shots = finite(away_danger.get("shots_on_target_avg"))

        if home_corners is not None and away_corners is not None:
            total = home_corners + away_corners
            variables = {
                "home_team": home,
                "away_team": away,
                "home_recent_avg": round(home_corners, 2),
                "away_recent_avg": round(away_corners, 2),
                "combined_avg": round(total, 2),
                "home_sample": home_danger.get("n_fixtures"),
                "away_sample": away_danger.get("n_fixtures"),
                "home_fixture_ids": home_danger.get("fixture_ids") or [],
                "away_fixture_ids": away_danger.get("fixture_ids") or [],
                "sample_quality": "low" if confidence_factor < 1 else "normal",
            }
            markets.append(market_entry(
                key="corners_total",
                label="Corners totales del partido",
                metric="corners",
                scope="match",
                lam=total,
                lines=TOTAL_CORNERS_LINES,
                variables=variables,
                confidence_factor=confidence_factor,
            ))
            for side, team, lam, danger in (
                ("home", home, home_corners, home_danger),
                ("away", away, away_corners, away_danger),
            ):
                markets.append(market_entry(
                    key=f"corners_team_{side}",
                    label=f"Corners de {team}",
                    metric="corners",
                    scope="team",
                    lam=lam,
                    lines=TEAM_CORNERS_LINES,
                    variables={
                        "team": team,
                        "side": side,
                        "recent_avg": round(lam, 2),
                        "sample": danger.get("n_fixtures"),
                        "fixture_ids": danger.get("fixture_ids") or [],
                        "sample_quality": "low" if confidence_factor < 1 else "normal",
                    },
                    confidence_factor=confidence_factor,
                ))

        if home_shots is not None and away_shots is not None:
            total = home_shots + away_shots
            variables = {
                "home_team": home,
                "away_team": away,
                "home_recent_avg": round(home_shots, 2),
                "away_recent_avg": round(away_shots, 2),
                "combined_avg": round(total, 2),
                "home_sample": home_danger.get("n_fixtures"),
                "away_sample": away_danger.get("n_fixtures"),
                "home_fixture_ids": home_danger.get("fixture_ids") or [],
                "away_fixture_ids": away_danger.get("fixture_ids") or [],
                "sample_quality": "low" if confidence_factor < 1 else "normal",
            }
            markets.append(market_entry(
                key="shots_on_target_total",
                label="Tiros a puerta totales",
                metric="shots_on_target",
                scope="match",
                lam=total,
                lines=TOTAL_SHOTS_LINES,
                variables=variables,
                confidence_factor=confidence_factor,
            ))
            for side, team, lam, danger in (
                ("home", home, home_shots, home_danger),
                ("away", away, away_shots, away_danger),
            ):
                markets.append(market_entry(
                    key=f"shots_on_target_team_{side}",
                    label=f"Tiros a puerta de {team}",
                    metric="shots_on_target",
                    scope="team",
                    lam=lam,
                    lines=TEAM_SHOTS_LINES,
                    variables={
                        "team": team,
                        "side": side,
                        "recent_avg": round(lam, 2),
                        "sample": danger.get("n_fixtures"),
                        "fixture_ids": danger.get("fixture_ids") or [],
                        "sample_quality": "low" if confidence_factor < 1 else "normal",
                    },
                    confidence_factor=confidence_factor,
                ))

    for side, team, pdata in (
        ("home", home, home_player_shots),
        ("away", away, away_player_shots),
    ):
        sample = int((pdata or {}).get("n_fixtures") or 0)
        player_confidence = LOW_SAMPLE_CONFIDENCE_FACTOR if is_selection and sample < MIN_SAMPLE else 1.0
        for player in (pdata or {}).get("players") or []:
            apps = int(player.get("appearances") or 0)
            minutes = finite(player.get("minutes_avg")) or 0.0
            if apps < PLAYER_MIN_APPS or minutes < PLAYER_MIN_MINUTES:
                continue
            if (player.get("position") or "").upper() == "G":
                continue

            total_avg = finite(player.get("shots_total_avg"))
            sot_avg = finite(player.get("shots_on_target_avg"))
            base_vars = {
                "team": team,
                "side": side,
                "player_id": player.get("player_id"),
                "player_name": player.get("name"),
                "player_search": norm(player.get("name")),
                "position": player.get("position"),
                "appearances": apps,
                "starts": player.get("starts"),
                "minutes_avg": player.get("minutes_avg"),
                "sample": sample,
                "fixture_ids": player.get("fixture_ids") or [],
                "sample_quality": "low" if player_confidence < 1 else "normal",
            }
            if total_avg is not None:
                markets.append(market_entry(
                    key=f"player_shots_total_{side}_{player.get('player_id')}",
                    label=f"{player.get('name')} tiros totales",
                    metric="player_shots_total",
                    scope="player",
                    lam=total_avg,
                    lines=PLAYER_TOTAL_LINES,
                    variables={**base_vars, "recent_avg": round(total_avg, 2)},
                    confidence_factor=player_confidence,
                ))
            if sot_avg is not None:
                markets.append(market_entry(
                    key=f"player_shots_on_target_{side}_{player.get('player_id')}",
                    label=f"{player.get('name')} tiros a puerta",
                    metric="player_shots_on_target",
                    scope="player",
                    lam=sot_avg,
                    lines=PLAYER_SOT_LINES,
                    variables={**base_vars, "recent_avg": round(sot_avg, 2)},
                    confidence_factor=player_confidence,
                ))

    if not markets:
        return None

    return {
        "key": record.get("key") or f"{home}|{away}|{record.get('date') or ''}",
        "matchup": f"{home} vs {away}",
        "home": home,
        "away": away,
        "league": record.get("league"),
        "date": record.get("date"),
        "source_file": record.get("_source_file"),
        "search": norm(f"{home} {away} {record.get('key')} {record.get('league')}"),
        "markets": markets,
    }


def load_records() -> list[dict[str, Any]]:
    if not DATA_DIR.exists():
        return []

    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for path in sorted(DATA_DIR.glob("*.json"), reverse=True):
        rows = read_json(path)
        if not isinstance(rows, list):
            continue
        for row in rows:
            key = row.get("key") or f"{row.get('home')}|{row.get('away')}|{row.get('date')}"
            if key in seen:
                continue
            seen.add(key)
            records.append({**row, "_source_file": path.name})
    return records


def load_selection_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for stats_path, fixtures_path, source_name in SELECTION_SOURCES:
        stats = read_json(stats_path)
        fixtures = read_json(fixtures_path)
        if not isinstance(stats, dict) or not isinstance(fixtures, list):
            continue

        for fx in fixtures:
            home = fx.get("home")
            away = fx.get("away")
            if not home or not away:
                continue
            home_danger = (stats.get(home) or {}).get("danger")
            away_danger = (stats.get(away) or {}).get("danger")
            home_players = (stats.get(home) or {}).get("player_shots")
            away_players = (stats.get(away) or {}).get("player_shots")
            if not home_danger and not away_danger and not home_players and not away_players:
                continue
            records.append({
                "key": f"{home}|{away}|{(fx.get('date') or '')[:10]}",
                "home": home,
                "away": away,
                "league": "Mundial 2026" if "worldcup" in source_name else "Amistosos internacionales",
                "date": (fx.get("date") or "")[:10],
                "home_danger": home_danger,
                "away_danger": away_danger,
                "home_player_shots": home_players,
                "away_player_shots": away_players,
                "_source_file": source_name,
            })
    return records


def main() -> int:
    all_records = [*load_records(), *load_selection_records()]
    matches = [item for row in all_records if (item := build_for_record(row))]
    artifact = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "version": 1,
        "method": {
            "name": "poisson_recent_averages",
            "description": (
                "Calcula expectativas por mercado con promedios recientes de "
                "ambos equipos y estima P(Over linea) mediante Poisson."
            ),
            "min_sample": MIN_SAMPLE,
            "ideal_min_confidence": IDEAL_MIN_CONFIDENCE,
        },
        "matches": matches,
    }
    OUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Market analyzer: {OUT}")
    print(f"matches={len(matches)} markets={sum(len(m['markets']) for m in matches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
