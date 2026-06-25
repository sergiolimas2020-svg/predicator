#!/usr/bin/env python3
"""Checks that World Cup player shot data is exposed to the chat analyzer."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value) -> str:
    text = str(value or "").lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text).split())


def main() -> int:
    stats = read_json(ROOT / "static" / "worldcup_stats.json")
    analyzer = read_json(ROOT / "static" / "market_analyzer.json")

    expected: set[tuple[str, str]] = set()
    for team, block in stats.items():
        players = ((block or {}).get("player_shots") or {}).get("players") or []
        for player in players:
            name = player.get("name")
            if name:
                expected.add((norm(team), norm(name)))

    total_markets: set[tuple[str, str]] = set()
    sot_markets: set[tuple[str, str]] = set()
    for match in analyzer.get("matches") or []:
        if match.get("source_file") != "worldcup_stats.json":
            continue
        for market in match.get("markets") or []:
            if market.get("scope") != "player":
                continue
            variables = market.get("variables") or {}
            key = (norm(variables.get("team")), norm(variables.get("player_name")))
            if market.get("metric") == "player_shots_total":
                total_markets.add(key)
            if market.get("metric") == "player_shots_on_target":
                sot_markets.add(key)

    missing_total = sorted(expected - total_markets)
    missing_sot = sorted(expected - sot_markets)
    if missing_total or missing_sot:
        for team, player in missing_total[:20]:
            print(f"Missing total shots market: {team} / {player}")
        for team, player in missing_sot[:20]:
            print(f"Missing shots on target market: {team} / {player}")
        print(f"missing_total={len(missing_total)} missing_sot={len(missing_sot)} expected={len(expected)}")
        return 1

    print(f"World Cup player coverage OK: {len(expected)} players")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
