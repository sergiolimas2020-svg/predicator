#!/usr/bin/env python3
"""
Backtest POINT-IN-TIME del modelo de selecciones (Mundial / fútbol internacional).

Responde la pregunta honesta: ¿el modelo está bien calibrado en fútbol de
selecciones? Mide aciertos y Brier sin fuga de información (cada partido se
predice usando SOLO datos previos).

Método:
  1. Descarga el histórico internacional reciente de las 48 selecciones del
     Mundial vía API-Football (reusa scrapers.worldcup) y arma un pool único
     de partidos jugados, dedup por fixture_id, orden cronológico.
  2. Recorre el stream cronológicamente. Mantiene un Elo dinámico (arranca
     flat en 1500 → sin sesgo de un seed que ya "conoce" el futuro) y una
     ventana de forma (goles favor/contra) por selección.
  3. Para cada partido, ANTES de verlo, predice P(local), P(empate),
     P(visita) con el MISMO modelo Poisson del motor (intl=True, neutral
     según corresponda), usando Elo+forma previos. Registra la predicción
     frente al resultado real. Luego actualiza Elo y forma.
  4. Descarta el primer tramo (warmup) para que Elo/forma se asienten y
     reporta sobre el resto:
        - n, hit-rate (argmax 1X2 acierta el resultado real)
        - hit-rate del favorito DNB (ignora empates)
        - Brier multiclase (0=perfecto, menor=mejor)
        - log-loss
        - tabla de calibración (prob predicha vs frecuencia real)
        - baseline: predecir siempre "gana el de mayor Elo"

Uso:
  python3 scripts/backtest_intl.py                 # depth por defecto
  python3 scripts/backtest_intl.py --depth 60 --warmup 0.35
  python3 scripts/backtest_intl.py --report static/_backtest_intl.md
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.worldcup import (  # noqa: E402
    _load_api_key, fetch_wc_teams, fetch_team_history,
    is_neutral_venue, HOST_NATIONS,
)
from scrapers.api_football.client import APIFootballClient  # noqa: E402
from scrapers.elo_ratings import calculate_elo_update, ELO_BASE  # noqa: E402
import scrapers.generate_predictions as g  # noqa: E402

FORM_WINDOW = 10  # nº de partidos para la forma (ataque/defensa) PIT


def build_pool(depth: int) -> List[Dict[str, Any]]:
    key = _load_api_key()
    if not key:
        print("ERROR: API_FOOTBALL_KEY no encontrada (.env o entorno).")
        sys.exit(2)
    client = APIFootballClient(api_key=key)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    client.session.verify = False

    teams = fetch_wc_teams(client)
    print(f"Selecciones: {len(teams)} | profundidad histórica: {depth}")
    seen, pool = set(), []
    for t in teams:
        for m in fetch_team_history(client, t["id"], last=depth):
            fid = m.get("fixture_id")
            if fid in seen:
                continue
            seen.add(fid)
            pool.append(m)
    pool.sort(key=lambda m: m.get("ts", 0))
    print(f"Partidos internacionales únicos en el pool: {len(pool)}")
    return pool


def _form_dict(window: Deque[Tuple[int, int]]) -> Dict[str, Any]:
    """Construye el dict 'position' que espera el modelo desde una ventana de
    (goles_favor, goles_contra)."""
    gf = sum(x for x, _ in window)
    gc = sum(y for _, y in window)
    n = len(window)
    return {"position": {"partidos": n, "goles_favor": gf, "goles_contra": gc}}


def run_backtest(pool: List[Dict[str, Any]], warmup: float) -> Dict[str, Any]:
    elos: Dict[str, float] = defaultdict(lambda: ELO_BASE)
    forms: Dict[str, Deque[Tuple[int, int]]] = defaultdict(lambda: deque(maxlen=FORM_WINDOW))

    n_total = len(pool)
    warm_n = int(n_total * warmup)

    records = []  # (probs[3], actual_idx, elo_pick_correct)
    for i, m in enumerate(pool):
        h, a = m["home"], m["away"]
        gh, ga = m["gh"], m["ga"]
        neutral = is_neutral_venue(h)

        # Predicción PIT (solo si pasó el warmup y ambos tienen algo de forma)
        eligible = i >= warm_n and len(forms[h]) >= 3 and len(forms[a]) >= 3
        if eligible:
            hd = _form_dict(forms[h]); hd["elo"] = elos[h]
            ad = _form_dict(forms[a]); ad["elo"] = elos[a]
            w, d, l = g.prob_futbol_3way(hd, ad, neutral=neutral, intl=True)
            probs = [max(1e-6, w / 100.0), max(1e-6, d / 100.0), max(1e-6, l / 100.0)]
            s = sum(probs); probs = [p / s for p in probs]
            actual = 0 if gh > ga else (1 if gh == ga else 2)
            elo_pick = 0 if elos[h] >= elos[a] else 2  # de mayor Elo
            records.append((probs, actual, elo_pick))

        # Actualizar Elo y forma DESPUÉS de predecir
        dh, da = calculate_elo_update(elos[h], elos[a], gh, ga)
        elos[h] += dh; elos[a] += da
        forms[h].append((gh, ga))
        forms[a].append((ga, gh))

    return _metrics(records, n_total, warm_n)


def _metrics(records, n_total, warm_n) -> Dict[str, Any]:
    n = len(records)
    if n == 0:
        return {"n": 0}
    hits = sum(1 for p, act, _ in records if max(range(3), key=lambda k: p[k]) == act)
    # DNB: ignora partidos que terminaron en empate; acierta si el lado más
    # probable (entre local/visita) coincide con el ganador real.
    dnb = [(p, act) for p, act, _ in records if act != 1]
    dnb_hits = sum(1 for p, act in dnb if (0 if p[0] >= p[2] else 2) == act)
    elo_hits = sum(1 for p, act, ep in records if act != 1 and ep == act)
    brier = sum(sum((p[k] - (1.0 if act == k else 0.0)) ** 2 for k in range(3))
                for p, act, _ in records) / n
    logloss = -sum(math.log(p[act]) for p, act, _ in records) / n

    # Calibración del lado favorito (max prob) en buckets de 10pp
    buckets = defaultdict(lambda: [0, 0])  # bucket -> [n, aciertos]
    for p, act, _ in records:
        k = max(range(3), key=lambda j: p[j])
        b = min(9, int(p[k] * 10))
        buckets[b][0] += 1
        buckets[b][1] += 1 if k == act else 0

    return {
        "n_total": n_total, "warmup_skipped": warm_n, "n": n,
        "hit_rate_1x2": hits / n,
        "dnb_n": len(dnb), "dnb_hit_rate": (dnb_hits / len(dnb)) if dnb else None,
        "elo_baseline_dnb": (elo_hits / len(dnb)) if dnb else None,
        "brier": brier, "logloss": logloss,
        "calibration": {f"{b*10}-{b*10+10}%": {"n": v[0], "acc": round(v[1]/v[0], 3)}
                        for b, v in sorted(buckets.items()) if v[0] > 0},
    }


def _apply_temperature(probs: List[float], T: float) -> List[float]:
    """Temperature scaling: aplana (T>1) o agudiza (T<1) sin mover el argmax."""
    if T <= 0:
        return probs
    pw = [max(1e-9, p) ** (1.0 / T) for p in probs]
    s = sum(pw)
    return [p / s for p in pw]


def fit_temperature(records) -> Tuple[float, Dict[str, Any]]:
    """Ajusta la temperatura que minimiza log-loss en los registros PIT.

    T>1 reduce la sobre-confianza. Devuelve (T, métricas antes/después).
    Barrido fino en [0.5, 4.0]; suficiente y robusto para 1 parámetro.
    """
    def logloss(T):
        tot = 0.0
        for p, act, _ in records:
            pc = _apply_temperature(p, T)
            tot += -math.log(max(1e-12, pc[act]))
        return tot / len(records)

    def brier(T):
        tot = 0.0
        for p, act, _ in records:
            pc = _apply_temperature(p, T)
            tot += sum((pc[k] - (1.0 if act == k else 0.0)) ** 2 for k in range(3))
        return tot / len(records)

    best_T, best_ll = 1.0, logloss(1.0)
    T = 0.5
    while T <= 4.001:
        ll = logloss(T)
        if ll < best_ll:
            best_ll, best_T = ll, round(T, 2)
        T += 0.05
    metrics = {
        "T": best_T,
        "logloss_before": round(logloss(1.0), 4), "logloss_after": round(best_ll, 4),
        "brier_before": round(brier(1.0), 4), "brier_after": round(brier(best_T), 4),
    }
    return best_T, metrics


def calibrated_calibration_table(records, T: float) -> Dict[str, Any]:
    buckets = defaultdict(lambda: [0, 0])
    for p, act, _ in records:
        pc = _apply_temperature(p, T)
        k = max(range(3), key=lambda j: pc[j])
        b = min(9, int(pc[k] * 10))
        buckets[b][0] += 1
        buckets[b][1] += 1 if k == act else 0
    return {f"{b*10}-{b*10+10}%": {"n": v[0], "acc": round(v[1]/v[0], 3)}
            for b, v in sorted(buckets.items()) if v[0] > 0}


def format_report(r: Dict[str, Any]) -> str:
    if r.get("n", 0) == 0:
        return "Sin muestras evaluables (pool insuficiente)."
    lines = [
        "# Backtest internacional (point-in-time) — modelo selecciones",
        "",
        f"- Partidos en el pool: **{r['n_total']}** (warmup descartado: {r['warmup_skipped']})",
        f"- Muestras evaluadas: **{r['n']}**",
        f"- **Hit-rate 1X2** (argmax acierta L/E/V): **{r['hit_rate_1x2']:.1%}**",
        f"- **Hit-rate DNB** (sin empates, n={r['dnb_n']}): **{r['dnb_hit_rate']:.1%}**"
        if r['dnb_hit_rate'] is not None else "- DNB: s/d",
        f"- Baseline 'gana mayor Elo' (DNB): {r['elo_baseline_dnb']:.1%}"
        if r['elo_baseline_dnb'] is not None else "",
        f"- **Brier** multiclase: **{r['brier']:.4f}** (menor = mejor; azar 3-way ≈ 0.667)",
        f"- **Log-loss**: **{r['logloss']:.4f}** (azar 3-way ≈ 1.099)",
        "",
        "## Calibración del favorito (prob predicha vs acierto real)",
        "| Bucket prob | n | acierto |",
        "|---|---|---|",
    ]
    for b, v in r["calibration"].items():
        lines.append(f"| {b} | {v['n']} | {v['acc']:.1%} |")
    return "\n".join(x for x in lines if x != "")


def run_backtest_records(pool: List[Dict[str, Any]], warmup: float):
    """Igual que run_backtest pero devuelve también los registros crudos
    (para ajustar la temperatura)."""
    elos: Dict[str, float] = defaultdict(lambda: ELO_BASE)
    forms: Dict[str, Deque[Tuple[int, int]]] = defaultdict(lambda: deque(maxlen=FORM_WINDOW))
    n_total = len(pool)
    warm_n = int(n_total * warmup)
    records = []
    for i, m in enumerate(pool):
        h, a = m["home"], m["away"]
        gh, ga = m["gh"], m["ga"]
        neutral = is_neutral_venue(h)
        if i >= warm_n and len(forms[h]) >= 3 and len(forms[a]) >= 3:
            hd = _form_dict(forms[h]); hd["elo"] = elos[h]
            ad = _form_dict(forms[a]); ad["elo"] = elos[a]
            w, d, l = g.prob_futbol_3way(hd, ad, neutral=neutral, intl=True)
            probs = [max(1e-6, w/100.0), max(1e-6, d/100.0), max(1e-6, l/100.0)]
            s = sum(probs); probs = [p/s for p in probs]
            actual = 0 if gh > ga else (1 if gh == ga else 2)
            elo_pick = 0 if elos[h] >= elos[a] else 2
            records.append((probs, actual, elo_pick))
        dh, da = calculate_elo_update(elos[h], elos[a], gh, ga)
        elos[h] += dh; elos[a] += da
        forms[h].append((gh, ga)); forms[a].append((ga, gh))
    return records, n_total, warm_n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=40, help="histórico por equipo")
    ap.add_argument("--warmup", type=float, default=0.30, help="fracción inicial descartada")
    ap.add_argument("--report", type=str, default=None, help="ruta para guardar el .md")
    ap.add_argument("--fit", action="store_true",
                    help="ajusta la temperatura y escribe static/calibrator_intl.json")
    args = ap.parse_args()

    pool = build_pool(args.depth)
    records, n_total, warm_n = run_backtest_records(pool, args.warmup)
    r = _metrics(records, n_total, warm_n)
    report = format_report(r)
    print("\n" + report)

    if args.fit and records:
        import json
        T, fm = fit_temperature(records)
        print(f"\n=== Calibración (temperature scaling) ===")
        print(f"T óptimo = {T}")
        print(f"log-loss: {fm['logloss_before']} → {fm['logloss_after']}")
        print(f"Brier:    {fm['brier_before']} → {fm['brier_after']}")
        print("Calibración del favorito DESPUÉS:")
        for b, v in calibrated_calibration_table(records, T).items():
            print(f"  {b}: n={v['n']} acc={v['acc']:.1%}")
        out = Path(__file__).resolve().parents[1] / "static" / "calibrator_intl.json"
        out.write_text(json.dumps({
            "method": "temperature_scaling",
            "temperature": T,
            "n_samples": len(records),
            "logloss_before": fm["logloss_before"], "logloss_after": fm["logloss_after"],
            "brier_before": fm["brier_before"], "brier_after": fm["brier_after"],
            "note": "Aplicar a probs 1X2 con intl=True: p_k^(1/T) normalizado.",
        }, ensure_ascii=False, indent=2))
        print(f"\nCalibrador escrito en {out}")

    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
        print(f"\nReporte escrito en {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
