#!/usr/bin/env python3
"""
Auditoría estadística de señales PREDIKTOR.

No usa cuotas ni EV. Mide confiabilidad real del motor con:
- hit rate por liga
- hit rate por tipo de mercado
- calibración por bandas de probabilidad
- Brier score

Salida:
  static/_statistical_signal_report.md
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "static" / "predictions_log.json"
REPORT_PATH = ROOT / "static" / "_statistical_signal_report.md"


def _prob(entry: dict[str, Any]) -> float | None:
    value = entry.get("prob_adjusted")
    if value is not None:
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
    text = str(entry.get("confianza") or "")
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", text)
    if not match:
        return None
    return float(match.group(1))


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


def _prob_band(prob: float) -> str:
    start = int(prob // 10) * 10
    end = min(start + 9, 99)
    return f"{start}-{end}%"


def _eligible(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("tipo_pick") == "rejected_recent_form":
            continue
        if row.get("acerto") is None:
            continue
        prob = _prob(row)
        if prob is None:
            continue
        row = dict(row)
        row["_prob"] = prob
        row["_market_type"] = _market_type(str(row.get("prediccion") or ""))
        row["_hit"] = 1 if row.get("acerto") is True else 0
        out.append(row)
    return out


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {"n": 0, "hit_rate": 0.0, "avg_prob": 0.0, "brier": 0.0, "cal_gap": 0.0}
    hit_rate = mean(r["_hit"] for r in rows) * 100
    avg_prob = mean(r["_prob"] for r in rows)
    brier = mean(((r["_prob"] / 100.0) - r["_hit"]) ** 2 for r in rows)
    return {
        "n": n,
        "hit_rate": round(hit_rate, 1),
        "avg_prob": round(avg_prob, 1),
        "brier": round(brier, 4),
        "cal_gap": round(hit_rate - avg_prob, 1),
    }


def _group(rows: list[dict[str, Any]], key: str) -> list[tuple[str, dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key) or "—")].append(row)
    return sorted(
        ((name, _summary(items)) for name, items in buckets.items()),
        key=lambda item: (-item[1]["n"], item[0]),
    )


def _group_prob_bands(rows: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[_prob_band(row["_prob"])].append(row)
    return sorted(
        ((name, _summary(items)) for name, items in buckets.items()),
        key=lambda item: int(item[0].split("-", 1)[0]),
    )


def _table(title: str, rows: list[tuple[str, dict[str, Any]]], min_n: int = 1) -> list[str]:
    out = [f"## {title}", "", "| Grupo | N | Acierto | Prob. media | Gap | Brier |", "|---|---:|---:|---:|---:|---:|"]
    visible = [(name, s) for name, s in rows if s["n"] >= min_n]
    if not visible:
        out.append("| — | 0 | — | — | — | — |")
    for name, s in visible:
        out.append(
            f"| {name} | {s['n']} | {s['hit_rate']}% | {s['avg_prob']}% | "
            f"{s['cal_gap']:+}% | {s['brier']} |"
        )
    out.append("")
    return out


def main() -> int:
    data = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    rows = _eligible(data)
    overall = _summary(rows)

    lines = [
        "# Auditoría estadística del motor",
        "",
        f"Generado: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Este reporte NO usa cuotas, EV ni ROI. Evalúa únicamente si la probabilidad "
        "del modelo se corresponde con los aciertos reales.",
        "",
        "## Resumen",
        "",
        f"- Picks resueltos evaluables: **{overall['n']}**",
        f"- Acierto total: **{overall['hit_rate']}%**",
        f"- Probabilidad media publicada: **{overall['avg_prob']}%**",
        f"- Gap calibración (acierto - prob): **{overall['cal_gap']:+}%**",
        f"- Brier score: **{overall['brier']}**",
        "",
    ]

    lines += _table("Por banda de probabilidad", _group_prob_bands(rows))
    lines += _table("Por tipo de mercado", _group(rows, "_market_type"))
    lines += _table("Por liga", _group(rows, "league"), min_n=2)

    lines += [
        "## Lectura rápida",
        "",
        "- Gap positivo: el motor fue conservador en esa muestra.",
        "- Gap negativo: el motor sobreestimó su probabilidad.",
        "- Brier más bajo es mejor; penaliza confianza alta cuando falla.",
        "- Grupos con muestra pequeña no deben usarse para cambiar umbrales solos.",
        "",
        "## Reglas operativas derivadas",
        "",
        "- Córners queda fuera de picks oficiales hasta nueva muestra: histórico actual 0/6.",
        "- Doble oportunidad y apuesta sin empate quedan fuera de Featured/Pick oficial: gap negativo alto.",
        "- Over 1.5 se mantiene como mercado estadístico viable: 88.9% de acierto en la muestra actual.",
        "- Winner/1X2 se mantiene con cautela: gap cercano a calibración neutral.",
        "",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Reporte escrito: {REPORT_PATH}")
    print(
        f"n={overall['n']} hit_rate={overall['hit_rate']}% "
        f"avg_prob={overall['avg_prob']}% brier={overall['brier']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
