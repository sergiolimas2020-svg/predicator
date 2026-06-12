#!/usr/bin/env python3
"""
Calibración conservadora SHADOW por mercado — PROPUESTA, NO producción.

Genera una propuesta de calibración Platt por tipo de mercado a partir del
histórico verificado (static/predictions_log.json). NO la activa: el motor
sigue usando static/calibrator.json (calibrador global) con su guard A<0.

Base de datos: las mismas señales que mide scripts/statistical_signal_audit.py
(probabilidad publicada parseada de `prob_adjusted` o del texto `confianza`).

Reglas de la propuesta (conservadoras y verificables):
  - Solo se PROPONE un calibrador de mercado si cumple LAS DOS condiciones:
      1. Platt válido para producción: A < 0 (monótono creciente).
      2. Mejora el Brier en validación cruzada honesta (leave-one-out),
         no solo in-sample. Esto evita "mejorar" probabilidades artificialmente.
  - Muestra mínima por mercado: MIN_CALIBRATION_SAMPLES (igual que producción).
    Si no alcanza, se documenta y se mantiene el fallback SIN calibrar.
  - Mercados deshabilitados (corners, over_2_5, draw_no_bet, double_chance) se
    reportan como diagnóstico pero NUNCA se proponen para picks oficiales: el
    blindaje estadístico los mantiene fuera con o sin calibración.

Salida (artefactos shadow; el motor NO los lee):
  static/calibration_shadow.json
  static/_calibration_shadow_report.md

No reintroduce EV, cuotas ni Betplay estimado: solo calibra probabilidad.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Reutilizamos el MÉTODO de fit y el guard A<0 de producción para que la
# propuesta sea coherente con cómo se entrenaría/aceptaría un calibrador real.
from scrapers.generate_predictions import (  # noqa: E402
    MIN_CALIBRATION_SAMPLES,
    MODEL_VERSION,
    fit_platt_calibrator,
    platt_probability,
)

LOG_PATH = ROOT / "static" / "predictions_log.json"
SHADOW_JSON = ROOT / "static" / "calibration_shadow.json"
SHADOW_REPORT = ROOT / "static" / "_calibration_shadow_report.md"

# Mercados que el blindaje mantiene fuera de picks oficiales. La calibración
# NO los reactiva; se reportan solo como diagnóstico.
DISABLED_MARKETS = {"corners", "over_2_5", "draw_no_bet", "double_chance"}
# Mercados estadísticos vivos para picks oficiales.
ACTIVE_MARKETS = {"winner", "over_1_5"}


def _prob(entry: dict[str, Any]) -> float | None:
    value = entry.get("prob_adjusted")
    if value is not None:
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", str(entry.get("confianza") or ""))
    return float(match.group(1)) if match else None


def _market_type(pred: str) -> str:
    p = (pred or "").lower()
    if "over 1.5" in p:
        return "over_1_5"
    if "over 2.5" in p:
        return "over_2_5"
    if "córner" in p or "corner" in p:
        return "corners"
    if "doble oportunidad" in p:
        return "double_chance"
    if "sin empate" in p:
        return "draw_no_bet"
    return "winner"


def _pairs_by_market(log: list[dict[str, Any]]) -> dict[str, list[tuple[float, int]]]:
    """Devuelve {market: [(f, y), ...]} con f∈[0,1] (prob publicada) y y∈{0,1}."""
    buckets: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for e in log:
        if e.get("acerto") is None or e.get("tipo_pick") == "rejected_recent_form":
            continue
        p = _prob(e)
        if p is None:
            continue
        market = _market_type(str(e.get("prediccion") or ""))
        buckets[market].append((p / 100.0, 1 if e.get("acerto") else 0))
    return buckets


def _brier(pairs: list[tuple[float, int]], get_p) -> float:
    return mean((get_p(f) - y) ** 2 for f, y in pairs)


def _loo_brier(pairs: list[tuple[float, int]]) -> tuple[float | None, float | None]:
    """Brier leave-one-out: para cada i, entrena sin i y predice i.

    Devuelve (brier_raw, brier_calibrado) o (raw, None) si algún fold no pudo
    entrenar (n-1 < MIN_CALIBRATION_SAMPLES). Honesto: ningún punto se evalúa
    con un calibrador que vio ese mismo punto.
    """
    n = len(pairs)
    raw = _brier(pairs, lambda f: f)
    if n - 1 < MIN_CALIBRATION_SAMPLES:
        return raw, None
    se_cal = 0.0
    for i in range(n):
        train = pairs[:i] + pairs[i + 1:]
        A, B = fit_platt_calibrator(train)
        if A is None:
            return raw, None
        f, y = pairs[i]
        se_cal += (platt_probability(f, A, B) - y) ** 2
    return raw, se_cal / n


def _analyze_market(market: str, pairs: list[tuple[float, int]]) -> dict[str, Any]:
    n = len(pairs)
    hit_rate = round(100 * mean(y for _, y in pairs), 1)
    avg_prob = round(100 * mean(f for f, _ in pairs), 1)
    out: dict[str, Any] = {
        "n": n,
        "hit_rate": hit_rate,
        "avg_prob": avg_prob,
        "cal_gap": round(hit_rate - avg_prob, 1),
        "A": None,
        "B": None,
        "valid_monotonic": None,
        "brier_in_sample_before": None,
        "brier_in_sample_after": None,
        "brier_cv_before": None,
        "brier_cv_after": None,
        "status": None,
        "proposed_calibrator": None,
    }

    # Mercados deshabilitados: diagnóstico, nunca propuesta oficial.
    if market in DISABLED_MARKETS:
        out["brier_in_sample_before"] = round(_brier(pairs, lambda f: f), 4)
        out["status"] = "disabled_market"
        return out

    # Muestra insuficiente: documentar y mantener fallback sin calibrar.
    if n < MIN_CALIBRATION_SAMPLES:
        out["brier_in_sample_before"] = round(_brier(pairs, lambda f: f), 4)
        out["status"] = "insufficient_sample"
        return out

    A, B = fit_platt_calibrator(pairs)
    if A is None:
        out["status"] = "insufficient_sample"
        out["brier_in_sample_before"] = round(_brier(pairs, lambda f: f), 4)
        return out

    out["A"], out["B"] = A, B
    out["valid_monotonic"] = A < 0
    out["brier_in_sample_before"] = round(_brier(pairs, lambda f: f), 4)
    out["brier_in_sample_after"] = round(_brier(pairs, lambda f: platt_probability(f, A, B)), 4)

    cv_before, cv_after = _loo_brier(pairs)
    out["brier_cv_before"] = round(cv_before, 4) if cv_before is not None else None
    out["brier_cv_after"] = round(cv_after, 4) if cv_after is not None else None

    # Guard 1: monotonicidad (mismo criterio que producción).
    if not out["valid_monotonic"]:
        out["status"] = "rejected_non_monotonic"
        return out
    # Guard 2: la calibración debe mejorar fuera de muestra, no solo in-sample.
    if cv_after is None:
        out["status"] = "cv_unavailable"
        return out
    if cv_after >= cv_before:
        out["status"] = "rejected_no_cv_improvement"
        return out

    out["status"] = "proposed"
    out["proposed_calibrator"] = {"A": A, "B": B}
    return out


def main() -> int:
    log = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    by_market = _pairs_by_market(log)

    markets = {m: _analyze_market(m, pairs) for m, pairs in by_market.items()}
    proposed = {m: s["proposed_calibrator"] for m, s in markets.items()
                if s["status"] == "proposed"}

    artifact = {
        "is_shadow": True,
        "note": ("PROPUESTA shadow de calibración por mercado. El motor NO lee "
                 "este archivo. Producción sigue usando static/calibrator.json "
                 "(global) con el guard A<0. No activar hasta validar."),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model_version": MODEL_VERSION,
        "min_samples": MIN_CALIBRATION_SAMPLES,
        "active_markets": sorted(ACTIVE_MARKETS),
        "disabled_markets": sorted(DISABLED_MARKETS),
        "markets": markets,
        "proposed_calibrators": proposed,
    }
    SHADOW_JSON.write_text(json.dumps(artifact, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    # ── Reporte markdown ──
    order = sorted(markets.items(), key=lambda kv: (-kv[1]["n"], kv[0]))
    lines = [
        "# Calibración conservadora — propuesta SHADOW",
        "",
        f"Generado: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "**Artefacto shadow.** No toca publicación oficial. El motor sigue sin "
        "calibrar (o con el calibrador global válido si lo hubiera). Una "
        "propuesta solo se acepta si Platt es monótono (A<0) **y** mejora el "
        "Brier en validación cruzada leave-one-out. No reintroduce EV/cuotas.",
        "",
        f"- Muestra mínima por mercado: **{MIN_CALIBRATION_SAMPLES}**",
        f"- Mercados con propuesta válida: **{len(proposed)}**"
        + (f" ({', '.join(sorted(proposed))})" if proposed else ""),
        "",
        "## Por mercado",
        "",
        "| Mercado | N | Acierto | Prob. media | Gap | A | B | Brier CV antes→después | Estado |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for m, s in order:
        a = "—" if s["A"] is None else f"{s['A']}"
        b = "—" if s["B"] is None else f"{s['B']}"
        if s["brier_cv_before"] is not None and s["brier_cv_after"] is not None:
            cv = f"{s['brier_cv_before']} → {s['brier_cv_after']}"
        elif s["brier_in_sample_before"] is not None:
            cv = f"in-sample {s['brier_in_sample_before']}"
        else:
            cv = "—"
        lines.append(
            f"| {m} | {s['n']} | {s['hit_rate']}% | {s['avg_prob']}% | "
            f"{s['cal_gap']:+}% | {a} | {b} | {cv} | {s['status']} |"
        )

    lines += [
        "",
        "## Estados",
        "",
        "- `proposed`: Platt válido (A<0) y mejora Brier CV. Candidato a shadow.",
        "- `rejected_non_monotonic`: A≥0, no se acepta (mismo guard que producción).",
        "- `rejected_no_cv_improvement`: no mejora fuera de muestra; sería mejora ficticia.",
        "- `insufficient_sample`: n < mínimo; se mantiene fallback SIN calibrar.",
        "- `disabled_market`: mercado fuera de picks oficiales; diagnóstico, sin propuesta.",
        "",
        "## Reglas mantenidas",
        "",
        "- Corners, Over 2.5, DNB y doble oportunidad siguen deshabilitados como "
        "picks oficiales, con o sin calibración.",
        "- Ningún calibrador se activa en producción desde aquí. Para activar uno "
        "habría que: (1) entrenar con más muestra del modelo actual, (2) confirmar "
        "A<0, (3) confirmar mejora en validación cruzada, (4) correr en shadow.",
        "- Mientras no haya propuesta válida, el motor publica SIN calibrar.",
        "",
    ]
    SHADOW_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Shadow JSON:   {SHADOW_JSON}")
    print(f"Shadow report: {SHADOW_REPORT}")
    print(f"mercados analizados={len(markets)} propuestas_validas={len(proposed)}")
    for m, s in order:
        print(f"  {m:14} n={s['n']:3} status={s['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
