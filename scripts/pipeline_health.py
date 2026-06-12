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
        try:
            daily = load_json(DAILY_PATH) if DAILY_PATH.exists() else {}
        except Exception:
            daily = {}
        n_picks = (
            (1 if daily.get("pick_dia") else 0)
            + (1 if daily.get("pick_gratuito") else 0)
            + len(daily.get("picks_suscripcion") or [])
        )
        if n_picks:
            errors.append(
                f"{rel(path)} missing but daily_picks has {n_picks} pick(s); "
                "football picks require API-Football backing"
            )
            return errors, warnings
        warnings.append(
            f"{rel(path)} missing; recent form/danger filters unavailable today"
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

    for check in (check_daily, check_api_football, check_odds, check_log):
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
