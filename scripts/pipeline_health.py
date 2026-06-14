#!/usr/bin/env python3
"""
PREDIKTOR pipeline health check.

Checks local artifacts without network:
- daily_picks.json date matches today in Colombia.
- odds.json status is reported when present, but it is not required for the
  statistical engine.
- API-Football daily data status is reported because recent form and danger
  signals are statistical inputs.
- calibrator.json is valid when present.
- local branch is visible, so audits do not confuse feature branches with main.

Exit code:
  0 = no critical issues
  1 = one or more critical issues
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DAILY_PATH = ROOT / "static" / "predictions" / "daily_picks.json"
ODDS_PATH = ROOT / "static" / "odds.json"
CALIBRATOR_PATH = ROOT / "static" / "calibrator.json"
LOG_PATH = ROOT / "static" / "predictions_log.json"
API_FOOTBALL_DIR = ROOT / "static" / "api_football" / "data"
WORLD_CUP_STATS_PATH = ROOT / "static" / "worldcup_stats.json"
WORLD_CUP_FIXTURES_PATH = ROOT / "static" / "worldcup_fixtures.json"
FRIENDLIES_STATS_PATH = ROOT / "static" / "friendlies_stats.json"
FRIENDLIES_FIXTURES_PATH = ROOT / "static" / "friendlies_fixtures.json"
SELECTION_LEAGUES = {"Mundial 2026", "Amistoso Selección"}


def today_colombia() -> str:
    return datetime.now(timezone(timedelta(hours=-5))).strftime("%Y-%m-%d")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def file_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=str(ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip() or "(detached)"
    except Exception:
        return "(unknown)"


def daily_pick_entries() -> List[Dict[str, Any]]:
    if not DAILY_PATH.exists():
        return []
    try:
        daily = load_json(DAILY_PATH)
    except Exception:
        return []
    picks: List[Dict[str, Any]] = []
    for key in ("pick_dia", "pick_gratuito", "pick_exploratorio"):
        value = daily.get(key)
        if isinstance(value, dict):
            picks.append(value)
    for value in daily.get("picks_suscripcion") or []:
        if isinstance(value, dict):
            picks.append(value)
    unique: List[Dict[str, Any]] = []
    seen = set()
    for pick in picks:
        marker = (
            pick.get("slug"),
            pick.get("matchup"),
            pick.get("market"),
            pick.get("tipo"),
        )
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(pick)
    return unique


def split_matchup(matchup: str) -> Tuple[str, str]:
    if " vs " not in matchup:
        return "", ""
    home, away = matchup.split(" vs ", 1)
    return home.strip(), away.strip()


def colombia_date_from_iso(date_iso: str) -> str:
    dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt.astimezone(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d")


def check_daily(today: str) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    if not DAILY_PATH.exists():
        errors.append(f"{rel(DAILY_PATH)} missing")
        return errors, warnings

    try:
        data = load_json(DAILY_PATH)
    except Exception as exc:
        errors.append(f"{rel(DAILY_PATH)} unreadable: {exc}")
        return errors, warnings

    json_date = data.get("date")
    if json_date != today:
        errors.append(f"{rel(DAILY_PATH)} stale: date={json_date}, expected={today}")

    n_picks = (
        (1 if data.get("pick_dia") else 0)
        + (1 if data.get("pick_gratuito") else 0)
        + len(data.get("picks_suscripcion") or [])
    )
    if data.get("shadow_mode"):
        warnings.append(
            f"shadow_mode=true until {data.get('shadow_until')} "
            f"(bot should not publish regular picks)"
        )
    warnings.append(
        f"{rel(DAILY_PATH)} mtime={file_mtime(DAILY_PATH)} date={json_date} picks={n_picks}"
    )
    return errors, warnings


def check_odds(today: str) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    if not ODDS_PATH.exists():
        warnings.append(f"{rel(ODDS_PATH)} missing; statistical engine can still run")
        return errors, warnings

    try:
        odds = load_json(ODDS_PATH)
    except Exception as exc:
        errors.append(f"{rel(ODDS_PATH)} unreadable: {exc}")
        return errors, warnings

    if not isinstance(odds, dict) or not odds:
        warnings.append(f"{rel(ODDS_PATH)} empty or invalid; statistical engine can still run")
        return errors, warnings

    dates = sorted({str(v.get("date")) for v in odds.values() if isinstance(v, dict)})
    today_events = sum(1 for v in odds.values() if isinstance(v, dict) and v.get("date") == today)
    latest_fetch = None
    for v in odds.values():
        if not isinstance(v, dict):
            continue
        fetched = v.get("fetched_at")
        if fetched and (latest_fetch is None or fetched > latest_fetch):
            latest_fetch = fetched

    if today_events == 0:
        warnings.append(f"{rel(ODDS_PATH)} has no events for today={today}")
    if latest_fetch:
        latest_fetch_date = latest_fetch[:10]
        if latest_fetch_date != today:
            warnings.append(
                f"{rel(ODDS_PATH)} stale fetch: latest_fetch={latest_fetch_date}, "
                f"expected={today}; ignored for statistical picks"
            )
    else:
        warnings.append(f"{rel(ODDS_PATH)} has no fetched_at timestamps")
    warnings.append(
        f"{rel(ODDS_PATH)} mtime={file_mtime(ODDS_PATH)} events={len(odds)} "
        f"dates={','.join(dates[:5])}{'...' if len(dates) > 5 else ''} "
        f"latest_fetch={latest_fetch}"
    )
    return errors, warnings


def check_api_football(today: str) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    path = API_FOOTBALL_DIR / f"{today}.json"
    if not path.exists():
        club_picks = [
            pick for pick in daily_pick_entries()
            if pick.get("league") not in SELECTION_LEAGUES
        ]
        if club_picks:
            errors.append(
                f"{rel(path)} missing but daily_picks has {len(club_picks)} club pick(s); "
                "club football picks require API-Football backing"
            )
            return errors, warnings
        warnings.append(
            f"{rel(path)} missing; no club picks require recent form/danger backing today"
        )
        return errors, warnings

    try:
        rows = load_json(path)
    except Exception as exc:
        errors.append(f"{rel(path)} unreadable: {exc}")
        return errors, warnings

    if not isinstance(rows, list):
        errors.append(f"{rel(path)} invalid: expected list")
        return errors, warnings

    with_ids = sum(1 for r in rows if isinstance(r, dict) and r.get("home_id") and r.get("away_id"))
    with_form = sum(1 for r in rows if isinstance(r, dict) and r.get("home_form") and r.get("away_form"))
    with_stats = sum(1 for r in rows if isinstance(r, dict) and r.get("home_stats") and r.get("away_stats"))
    with_danger = sum(1 for r in rows if isinstance(r, dict) and r.get("home_danger") and r.get("away_danger"))
    warnings.append(
        f"{rel(path)} mtime={file_mtime(path)} matches={len(rows)} "
        f"ids={with_ids} form={with_form} stats={with_stats} danger={with_danger}"
    )
    return errors, warnings


def check_selection_backing(today: str) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    selection_picks = [
        pick for pick in daily_pick_entries()
        if pick.get("league") in SELECTION_LEAGUES
    ]
    if not selection_picks:
        warnings.append("no selection picks today")
        return errors, warnings

    stats_by_league = {
        "Mundial 2026": WORLD_CUP_STATS_PATH,
        "Amistoso Selección": FRIENDLIES_STATS_PATH,
    }
    fixtures_by_league = {
        "Mundial 2026": WORLD_CUP_FIXTURES_PATH,
        "Amistoso Selección": FRIENDLIES_FIXTURES_PATH,
    }

    for league in sorted({str(p.get("league")) for p in selection_picks}):
        stats_path = stats_by_league.get(league)
        fixtures_path = fixtures_by_league.get(league)
        league_picks = [p for p in selection_picks if p.get("league") == league]
        if not stats_path or not fixtures_path:
            errors.append(f"{league}: no backing contract configured")
            continue
        if not stats_path.exists():
            errors.append(f"{rel(stats_path)} missing but daily_picks has {len(league_picks)} {league} pick(s)")
            continue
        if not fixtures_path.exists():
            errors.append(f"{rel(fixtures_path)} missing but daily_picks has {len(league_picks)} {league} pick(s)")
            continue

        try:
            stats = load_json(stats_path)
            fixtures = load_json(fixtures_path)
        except Exception as exc:
            errors.append(f"{league} backing unreadable: {exc}")
            continue
        if not isinstance(stats, dict):
            errors.append(f"{rel(stats_path)} invalid: expected object")
            continue
        if not isinstance(fixtures, list):
            errors.append(f"{rel(fixtures_path)} invalid: expected list")
            continue

        todays_pairs = set()
        for fx in fixtures:
            if not isinstance(fx, dict):
                continue
            try:
                fx_date = colombia_date_from_iso(str(fx.get("date") or ""))
            except Exception:
                continue
            if fx_date != today:
                continue
            home, away = fx.get("home"), fx.get("away")
            if home and away:
                todays_pairs.add((str(home), str(away)))

        for pick in league_picks:
            home, away = split_matchup(str(pick.get("matchup") or ""))
            if not home or not away:
                errors.append(f"{league}: invalid matchup in daily_picks: {pick.get('matchup')!r}")
                continue
            missing_stats = [team for team in (home, away) if team not in stats]
            if missing_stats:
                errors.append(f"{league}: missing stats for {', '.join(missing_stats)} in {rel(stats_path)}")
            if (home, away) not in todays_pairs:
                errors.append(f"{league}: {home} vs {away} not found for today in {rel(fixtures_path)}")

        warnings.append(
            f"{league} backing OK: picks={len(league_picks)} "
            f"stats_teams={len(stats)} today_fixtures={len(todays_pairs)} "
            f"mtime_stats={file_mtime(stats_path)}"
        )
    return errors, warnings


def check_calibrator() -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    if not CALIBRATOR_PATH.exists():
        warnings.append(f"{rel(CALIBRATOR_PATH)} missing; motor will run uncalibrated")
        return errors, warnings

    try:
        data = load_json(CALIBRATOR_PATH)
    except Exception as exc:
        errors.append(f"{rel(CALIBRATOR_PATH)} unreadable: {exc}")
        return errors, warnings

    A = data.get("A")
    B = data.get("B")
    valid = data.get("valid")
    if A is None or B is None:
        errors.append(f"{rel(CALIBRATOR_PATH)} missing A/B")
    elif valid is False or float(A) >= 0:
        warnings.append(
            f"{rel(CALIBRATOR_PATH)} invalid for production: "
            f"A={A} B={B} reason={data.get('invalid_reason', 'A>=0')}"
        )
    else:
        warnings.append(f"{rel(CALIBRATOR_PATH)} valid: A={A} B={B}")
    return errors, warnings


def check_log(today: str) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    if not LOG_PATH.exists():
        warnings.append(f"{rel(LOG_PATH)} missing")
        return errors, warnings

    try:
        log = load_json(LOG_PATH)
    except Exception as exc:
        errors.append(f"{rel(LOG_PATH)} unreadable: {exc}")
        return errors, warnings

    today_rows = [e for e in log if isinstance(e, dict) and e.get("fecha") == today]
    unresolved = [e for e in log if isinstance(e, dict) and e.get("acerto") is None]
    warnings.append(
        f"{rel(LOG_PATH)} entries={len(log)} today_entries={len(today_rows)} "
        f"unresolved={len(unresolved)} mtime={file_mtime(LOG_PATH)}"
    )
    return errors, warnings


def main() -> int:
    today = today_colombia()
    branch = git_branch()
    errors: List[str] = []
    warnings: List[str] = []

    warnings.append(f"today_colombia={today}")
    warnings.append(f"git_branch={branch}")
    if branch not in ("main", "master"):
        warnings.append("local branch is not main; compare with production before acting on stale files")

    for check in (check_daily, check_api_football, check_selection_backing, check_odds, check_log):
        e, w = check(today)
        errors.extend(e)
        warnings.extend(w)
    e, w = check_calibrator()
    errors.extend(e)
    warnings.extend(w)

    print("PREDIKTOR pipeline health")
    print("=" * 60)
    for msg in warnings:
        print(f"[info] {msg}")
    for msg in errors:
        print(f"[error] {msg}")
    print("=" * 60)
    print("status=" + ("FAIL" if errors else "OK"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
