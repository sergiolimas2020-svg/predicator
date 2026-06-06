#!/usr/bin/env python3
"""
Reporte de CALIBRACIÓN público — el foso anti-tipster de PREDIKTOR.

Mide si nuestras PROBABILIDADES significan algo: cuando el modelo dice 70%,
¿gana el 70% de las veces? Usa SOLO datos que tenemos y son verificables:
las predicciones publicadas (static/predictions_log.json) y su resultado real.
NO usa cuotas.

Salida: static/calibration.json
  {
    "n": int,                      # picks resueltos
    "brier": float,                # error cuadrático medio (menor = mejor)
    "brier_baseline": float,       # Brier de predecir siempre la tasa base
    "acierto_global": float,       # % global
    "actualizado": "YYYY-MM-DD",
    "buckets": [ {"rango","n","prob_predicha","acierto_real"} ]
  }

Uso:  python3 scripts/calibration_report.py
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "static" / "predictions_log.json"
OUT = ROOT / "static" / "calibration.json"

# Buckets de probabilidad (cota inferior inclusive, superior exclusive salvo el último)
BUCKETS = [(50, 60), (60, 70), (70, 80), (80, 90), (90, 101)]


def _prob_of(item) -> float | None:
    """Extrae la probabilidad (0-100) del campo confianza ('Probabilidad: 76.3%')."""
    c = item.get("confianza")
    if isinstance(c, (int, float)):
        return float(c)
    if isinstance(c, str):
        m = re.search(r"([\d]+(?:\.\d+)?)\s*%", c)
        if m:
            return float(m.group(1))
    return None


def build_calibration(log: list) -> dict:
    rows = []
    for it in log:
        if it.get("acerto") is None:
            continue
        p = _prob_of(it)
        if p is None:
            continue
        rows.append((p, 1 if it["acerto"] else 0))

    n = len(rows)
    if n == 0:
        return {"n": 0}

    base = sum(y for _, y in rows) / n
    brier = sum(((p / 100.0) - y) ** 2 for p, y in rows) / n
    brier_base = sum((base - y) ** 2 for _, y in rows) / n

    buckets = []
    for lo, hi in BUCKETS:
        grp = [(p, y) for p, y in rows if lo <= p < hi]
        if not grp:
            continue
        buckets.append({
            "rango": f"{lo}-{min(hi,100)}%",
            "n": len(grp),
            "prob_predicha": round(sum(p for p, _ in grp) / len(grp), 1),
            "acierto_real": round(100 * sum(y for _, y in grp) / len(grp), 1),
        })

    today = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d")
    return {
        "n": n,
        "brier": round(brier, 4),
        "brier_baseline": round(brier_base, 4),
        "acierto_global": round(100 * base, 1),
        "actualizado": today,
        "buckets": buckets,
    }


def main() -> int:
    if not LOG.exists():
        print(f"No existe {LOG}")
        return 1
    log = json.loads(LOG.read_text(encoding="utf-8"))
    rep = build_calibration(log if isinstance(log, list) else [])
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    if rep.get("n"):
        print(f"calibration.json → n={rep['n']} Brier={rep['brier']} "
              f"(baseline {rep['brier_baseline']}) acierto={rep['acierto_global']}%")
        for b in rep["buckets"]:
            print(f"   {b['rango']:8s} n={b['n']:3d}  dice {b['prob_predicha']}%  gana {b['acierto_real']}%")
    else:
        print("Sin picks resueltos para calibrar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
