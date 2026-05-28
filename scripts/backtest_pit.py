"""
Backtest POINT-IN-TIME del motor v1.2 (Opción B).

Reconstruye la tabla y la forma de cada equipo TAL COMO ESTABAN el día del
partido (sin lookahead) a partir del historial de fixtures de API-Football,
corre prob_futbol() de v1.2 — la del fix logístico — y mide el Brier Score.

Métrica: Brier sobre la probabilidad de victoria local.
  predicho = hp/100   ·   resultado = 1 si ganó el local, 0 si no.
Baseline "azar puro" ≈ 0.25.

Si el Brier crudo > 0.25, ajusta Platt scaling sobre esos partidos y
recalcula — in-sample y con validación cruzada 5-fold (la honesta).

Uso:  API_FOOTBALL_KEY=... python scripts/backtest_pit.py
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scrapers.api_football.client import APIFootballClient, APIFootballError
from scrapers.generate_predictions import (
    prob_futbol, fit_platt_calibrator, platt_probability,
)
import json

# Ligas europeas domésticas (donde vive el fix logístico de v1.2).
EURO_LEAGUES = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]
N_MATCHES   = 50      # últimos N partidos a evaluar
MIN_PRIOR   = 5       # cada equipo debe tener ≥ este nº de partidos previos
BRIER_GATE  = 0.24
CV_FOLDS    = 5


def fetch_league_fixtures(client, league_id, season):
    """Todos los fixtures terminados de una liga/temporada, normalizados."""
    payload = client._request("/fixtures", {"league": league_id, "season": season})
    out = []
    for f in payload.get("response", []):
        fx = f.get("fixture") or {}
        status = ((fx.get("status") or {}).get("short"))
        if status not in ("FT", "AET", "PEN"):
            continue
        goals = f.get("goals") or {}
        teams = f.get("teams") or {}
        hg, ag = goals.get("home"), goals.get("away")
        hid = (teams.get("home") or {}).get("id")
        aid = (teams.get("away") or {}).get("id")
        date = (fx.get("date") or "")[:10]
        if None in (hg, ag, hid, aid) or not date:
            continue
        out.append({"date": date, "home_id": hid, "away_id": aid,
                    "home_goals": hg, "away_goals": ag})
    return out


def build_table(fixtures, before_date):
    """Tabla de posiciones usando SOLO fixtures estrictamente anteriores a
    `before_date` (sin lookahead)."""
    table = {}
    for f in fixtures:
        if f["date"] >= before_date:
            continue
        hid, aid = f["home_id"], f["away_id"]
        hg, ag = f["home_goals"], f["away_goals"]
        for tid in (hid, aid):
            table.setdefault(tid, {"pj": 0, "g": 0, "gf": 0, "gc": 0, "pts": 0})
        th, ta = table[hid], table[aid]
        th["pj"] += 1; ta["pj"] += 1
        th["gf"] += hg; th["gc"] += ag
        ta["gf"] += ag; ta["gc"] += hg
        if hg > ag:
            th["g"] += 1; th["pts"] += 3
        elif ag > hg:
            ta["g"] += 1; ta["pts"] += 3
        else:
            th["pts"] += 1; ta["pts"] += 1
    for t in table.values():
        t["gd"] = t["gf"] - t["gc"]
    ranked = sorted(table.items(),
                    key=lambda kv: (-kv[1]["pts"], -kv[1]["gd"], -kv[1]["gf"]))
    for rank, (tid, t) in enumerate(ranked, 1):
        t["posicion"] = rank
    return table


def _pos_dict(rec):
    return {"position": {
        "posicion":   rec["posicion"],
        "partidos":   rec["pj"],
        "ganados":    rec["g"],
        "diferencia": rec["gd"],
    }}


def brier(pairs, get_p):
    return sum((get_p(f) - y) ** 2 for f, y in pairs) / len(pairs)


def calibration_table(pairs):
    buckets = [(0, 50), (50, 60), (60, 70), (70, 75), (75, 80), (80, 101)]
    rows = []
    for lo, hi in buckets:
        sub = [(f, y) for f, y in pairs if lo <= f * 100 < hi]
        if not sub:
            continue
        n = len(sub)
        decl = sum(f for f, _ in sub) / n * 100
        real = sum(y for _, y in sub) / n * 100
        rows.append((f"{lo}-{hi}", n, decl, real, real - decl))
    return rows


def cv_platt(pairs, folds=CV_FOLDS):
    """Brier con Platt vía validación cruzada k-fold (out-of-fold)."""
    n = len(pairs)
    oof = []
    for i in range(folds):
        train = [pairs[j] for j in range(n) if j % folds != i]
        test  = [pairs[j] for j in range(n) if j % folds == i]
        A, B = fit_platt_calibrator(train)
        for f, y in test:
            cal = platt_probability(f, A, B) if A is not None else f
            oof.append((cal, y))
    return sum((c - y) ** 2 for c, y in oof) / len(oof)


def main():
    print("── Backtest point-in-time del motor v1.2 ──\n")
    client = APIFootballClient()
    leagues_map = json.loads(
        (ROOT / "static" / "api_football" / "leagues_map.json").read_text())

    all_fixtures = {}   # league -> [fixtures]
    for lg in EURO_LEAGUES:
        info = leagues_map.get(lg)
        if not info:
            print(f"  ⚠ {lg} no está en leagues_map.json — salteada")
            continue
        try:
            fx = fetch_league_fixtures(client, info["id"], info["season"])
        except APIFootballError as e:
            print(f"  ⚠ {lg}: error API ({e})")
            continue
        all_fixtures[lg] = fx
        print(f"  {lg:18s} {len(fx)} partidos terminados (season {info['season']})")

    # Candidatos: fixtures con ≥ MIN_PRIOR partidos previos por equipo.
    candidates = []
    for lg, fx in all_fixtures.items():
        fx_sorted = sorted(fx, key=lambda f: f["date"])
        for f in fx_sorted:
            table = build_table(fx, f["date"])
            hr = table.get(f["home_id"])
            ar = table.get(f["away_id"])
            if not hr or not ar:
                continue
            if hr["pj"] < MIN_PRIOR or ar["pj"] < MIN_PRIOR:
                continue
            candidates.append((f, hr, ar, lg))

    candidates.sort(key=lambda c: c[0]["date"], reverse=True)
    if len(candidates) < CV_FOLDS * 4:
        print("  Datos insuficientes para un backtest fiable.")
        return

    # Dos muestras:
    #  A) "últimas 50" — lo que se pidió. Sesgo: fin de temporada europea =
    #     partidos intrascendentes (rotación, nada en juego) → peor caso para
    #     un modelo de tabla.
    #  B) "mid-season 50" — ambos equipos con 10-28 partidos jugados: ventana
    #     competitiva, sin ruido de inicio ni de fin de temporada. Test justo.
    sample_last = candidates[:N_MATCHES]
    sample_mid = [c for c in candidates
                  if 10 <= c[1]["pj"] <= 28 and 10 <= c[2]["pj"] <= 28][:N_MATCHES]

    def evaluate(sample, label):
        if len(sample) < CV_FOLDS * 4:
            print(f"\n### {label}: muestra insuficiente ({len(sample)})")
            return None
        pairs = []
        for f, hr, ar, lg in sample:
            hp, ap = prob_futbol(_pos_dict(hr), _pos_dict(ar))
            outcome = 1 if f["home_goals"] > f["away_goals"] else 0
            pairs.append((hp / 100.0, outcome))
        n = len(pairs)
        hit = sum(y for _, y in pairs) / n * 100
        brier_raw = brier(pairs, lambda f: f)

        print("\n" + "═" * 56)
        print(f"  MUESTRA: {label}  (n={n})")
        print(f"  Victorias locales reales : {hit:.1f}%")
        print(f"  Brier v1.2 (crudo)       : {brier_raw:.4f}")
        print("═" * 56)
        print("  Calibración (declarada vs real):")
        print("  | Bucket | n | declarada | real | gap |")
        for nombre, nb, decl, real, gap in calibration_table(pairs):
            print(f"  | {nombre}% | {nb} | {decl:.1f}% | {real:.1f}% | {gap:+.1f} pp |")

        final = brier_raw
        if brier_raw > 0.25:
            A, B = fit_platt_calibrator(pairs)
            if A is not None:
                bis = brier(pairs, lambda f: platt_probability(f, A, B))
                bcv = cv_platt(pairs)
                print(f"  Platt in-sample: {bis:.4f}  ·  Platt CV 5-fold: {bcv:.4f}")
                final = bcv
        else:
            print("  Brier ≤ 0.25 → Platt no aplicado.")
        verdict = "✅ CUMPLE" if final < BRIER_GATE else "❌ NO cumple"
        print(f"  → Brier final: {final:.4f}  ({verdict} el gate < {BRIER_GATE})")
        return final

    print(f"\n  Muestra A 'últimas 50': {len(sample_last)} partidos")
    print(f"  Muestra B 'mid-season': {len(sample_mid)} partidos")
    b_last = evaluate(sample_last, "A) últimas 50 (fin de temporada — sesgada)")
    b_mid  = evaluate(sample_mid,  "B) mid-season 50 (ventana competitiva — justa)")

    print("\n" + "═" * 56)
    print("  RESUMEN")
    if b_last is not None:
        print(f"   A) últimas 50    : Brier {b_last:.4f}")
    if b_mid is not None:
        print(f"   B) mid-season 50 : Brier {b_mid:.4f}")
    ref = b_mid if b_mid is not None else b_last
    if ref is not None and ref < BRIER_GATE:
        print(f"  Criterio < {BRIER_GATE}: CUMPLIDO (referencia: muestra justa).")
    else:
        print(f"  Criterio < {BRIER_GATE}: NO cumplido ni en la muestra justa.")
    print("═" * 56)


if __name__ == "__main__":
    main()
