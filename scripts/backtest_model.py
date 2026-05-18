"""
Backtest del motor PREDIKTOR sobre predictions_log.json.

Qué SÍ valida (datos disponibles en el log):
  · Brier Score del modelo — qué tan calibradas están las probabilidades.
  · Curva de calibración — probabilidad declarada vs acierto real, por bucket.
  · ROI con apuesta plana (1 unidad por pick).
  · ROI con Quarter-Kelly — y drawdown máximo.
  · Las mismas métricas para los últimos 30 días.

Qué NO puede validar (limitación de datos):
  · predictions_log.json NO guarda las estadísticas crudas de cada equipo,
    solo la probabilidad ya calculada por el motor viejo. Por eso este script
    NO puede recalcular qué habría predicho el modelo logístico nuevo sobre
    partidos pasados. El Brier de abajo es el del modelo VIEJO — es la línea
    base a superar. La validación del modelo nuevo debe ser hacia adelante
    (shadow-testing: loguear predicción nueva vs resultado por N días).

Uso:  python scripts/backtest_model.py
"""
from __future__ import annotations
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG_PATH = ROOT / "static" / "predictions_log.json"
OUT_PATH = ROOT / "static" / "_backtest_report.md"

QUARTER_KELLY = 0.25
START_BANKROLL = 100.0
BRIER_GATE = 0.24       # umbral de validación — Brier nuevo debe quedar por debajo
CV_FOLDS   = 5          # folds para la validación cruzada del calibrador Platt

# Funciones de calibración del motor (mismo Platt scaling usado en producción).
from scrapers.generate_predictions import fit_platt_calibrator, platt_probability


# ───────────────────────────────────────────────────────── helpers

def kelly_fraction(prob_pct, odds, fraction=QUARTER_KELLY):
    """f = (b·p − q)/b ; × fraction. 0 si no hay ventaja o datos inválidos."""
    if not odds or odds <= 1.0 or prob_pct is None:
        return 0.0
    p = max(0.0, min(1.0, prob_pct / 100.0))
    b = odds - 1.0
    q = 1.0 - p
    f = (b * p - q) / b
    return max(0.0, f) * fraction


def pnl_flat(pick):
    """Ganancia/pérdida de 1 unidad apostada (apuesta plana)."""
    return (pick["bk_odds"] - 1.0) if pick["acerto"] else -1.0


def brier_score(picks):
    """Mean((prob − outcome)²). Más bajo = mejor calibración. Rango [0,1]."""
    vals = []
    for p in picks:
        prob = p.get("prob_adjusted")
        if prob is None:
            continue
        outcome = 1.0 if p["acerto"] else 0.0
        vals.append((prob / 100.0 - outcome) ** 2)
    return sum(vals) / len(vals) if vals else None


def calibration_table(picks):
    """Agrupa por bucket de prob_adjusted; compara declarada vs real."""
    buckets = [(0, 50), (50, 60), (60, 70), (70, 75), (75, 80), (80, 90), (90, 101)]
    rows = []
    for lo, hi in buckets:
        sub = [p for p in picks
               if p.get("prob_adjusted") is not None
               and lo <= p["prob_adjusted"] < hi]
        if not sub:
            continue
        n = len(sub)
        declarada = sum(p["prob_adjusted"] for p in sub) / n
        real = sum(1 for p in sub if p["acerto"]) / n * 100
        rows.append((f"{lo}-{hi}", n, declarada, real, real - declarada))
    return rows


def roi_flat(picks):
    if not picks:
        return 0.0, 0.0
    profit = sum(pnl_flat(p) for p in picks)
    return profit, profit / len(picks) * 100


def cv_platt_brier(picks, folds=CV_FOLDS):
    """Brier del modelo calibrado con Platt, vía validación cruzada k-fold
    (out-of-fold — sin fuga de datos). Devuelve (brier_cv, brier_raw, n).

    brier_raw  = Brier de la probabilidad cruda del modelo (prob_original).
    brier_cv   = Brier de la probabilidad calibrada, evaluada en folds que
                 NO se usaron para entrenar ese calibrador.
    """
    pares = []  # (f, y) — f = prob_original/100
    for p in picks:
        f = p.get("prob_original")
        if f is None:
            continue
        pares.append((f / 100.0, 1 if p["acerto"] else 0))
    n = len(pares)
    if n < folds * 4:
        return None, None, n

    brier_raw = sum((f - y) ** 2 for f, y in pares) / n

    oof = []  # (calibrada, y) fuera de fold
    for i in range(folds):
        train = [pares[j] for j in range(n) if j % folds != i]
        test  = [pares[j] for j in range(n) if j % folds == i]
        A, B = fit_platt_calibrator(train)
        for f, y in test:
            cal = platt_probability(f, A, B) if A is not None else f
            oof.append((cal, y))
    brier_cv = sum((c - y) ** 2 for c, y in oof) / len(oof)
    return brier_cv, brier_raw, n


def roi_kelly(picks):
    """Simula bankroll con Quarter-Kelly. Devuelve (final, roi%, max_drawdown%)."""
    bankroll = START_BANKROLL
    peak = bankroll
    max_dd = 0.0
    for p in picks:
        f = kelly_fraction(p.get("prob_adjusted"), p["bk_odds"])
        stake = bankroll * f
        if p["acerto"]:
            bankroll += stake * (p["bk_odds"] - 1.0)
        else:
            bankroll -= stake
        peak = max(peak, bankroll)
        dd = (peak - bankroll) / peak * 100 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    roi = (bankroll - START_BANKROLL) / START_BANKROLL * 100
    return bankroll, roi, max_dd


# ───────────────────────────────────────────────────────── runner

def analizar(picks, etiqueta):
    n = len(picks)
    if n == 0:
        return f"### {etiqueta}\n\n_(sin picks en este rango)_\n"
    aciertos = sum(1 for p in picks if p["acerto"])
    hit = aciertos / n * 100
    brier = brier_score(picks)
    profit_flat, roi_f = roi_flat(picks)
    final_k, roi_k, dd_k = roi_kelly(picks)

    out = [f"### {etiqueta}\n"]
    out.append(f"- Picks: **{n}**  ·  Aciertos: {aciertos}/{n} = **{hit:.1f}%**")
    out.append(f"- Brier Score (modelo viejo): **{brier:.4f}**  "
               f"_(más bajo = mejor; baseline sin skill ≈ {hit/100*(1-hit/100):.4f})_")
    out.append(f"- ROI apuesta plana: **{roi_f:+.2f}%**  ({profit_flat:+.2f} u sobre {n} u)")
    out.append(f"- ROI Quarter-Kelly: **{roi_k:+.2f}%**  "
               f"(bankroll {START_BANKROLL:.0f} → {final_k:.2f})")
    out.append(f"- Drawdown máximo (Quarter-Kelly): **{dd_k:.1f}%**")
    return "\n".join(out) + "\n"


def main():
    if not LOG_PATH.exists():
        print(f"No existe {LOG_PATH}")
        sys.exit(1)

    log = json.loads(LOG_PATH.read_text())

    picks = [
        e for e in log
        if e.get("acerto") is not None
        and e.get("bk_odds") is not None
        and e.get("tipo_pick") != "rejected_recent_form"
    ]
    picks.sort(key=lambda e: e.get("fecha", ""))

    hoy = date.today()
    hace_30 = hoy - timedelta(days=30)
    def _fecha(e):
        try:
            return datetime.fromisoformat(e["fecha"]).date()
        except Exception:
            return None
    picks_30 = [p for p in picks if (_fecha(p) and _fecha(p) >= hace_30)]

    md = []
    md.append("# Backtest del motor PREDIKTOR\n")
    md.append(f"Generado: {datetime.now().isoformat(timespec='seconds')}\n")
    md.append(f"Fuente: `static/predictions_log.json` — "
              f"{len(log)} entradas, {len(picks)} picks cuantificables "
              f"(verificados, con cuota, sin rechazados por Filtro 1).\n")

    md.append("\n## 1. Histórico completo\n")
    md.append(analizar(picks, "Todos los picks cuantificables"))

    md.append("\n## 2. Últimos 30 días\n")
    md.append(f"_(picks con fecha ≥ {hace_30.isoformat()})_\n\n")
    md.append(analizar(picks_30, "Últimos 30 días"))

    md.append("\n## 3. Curva de calibración (modelo viejo)\n")
    md.append("Si el modelo estuviera bien calibrado, 'declarada' ≈ 'real'.\n")
    md.append("\n| Bucket prob | n | Prob declarada | Hit real | Gap |")
    md.append("|---|---|---|---|---|")
    for nombre, n, decl, real, gap in calibration_table(picks):
        md.append(f"| {nombre}% | {n} | {decl:.1f}% | {real:.1f}% | {gap:+.1f} pp |")
    md.append("")

    # ── Sección 4: validación de la calibración Platt ──
    md.append("\n## 4. Validación de la calibración (Platt scaling)\n")
    brier_cv, brier_raw, n_cv = cv_platt_brier(picks)
    if brier_cv is None:
        md.append(f"_(datos insuficientes para validación cruzada: "
                  f"n={n_cv}, se necesitan ≥{CV_FOLDS * 4})_\n")
        gate_ok = False
    else:
        delta = brier_raw - brier_cv
        gate_ok = brier_cv < BRIER_GATE
        md.append(f"Validación cruzada {CV_FOLDS}-fold (out-of-fold, sin fuga "
                  f"de datos) sobre {n_cv} picks:\n")
        md.append(f"- Brier modelo crudo (sin calibrar): **{brier_raw:.4f}**")
        md.append(f"- Brier modelo calibrado (Platt, CV): **{brier_cv:.4f}**")
        md.append(f"- Mejora por calibración: **{delta:+.4f}**")
        md.append(f"- Umbral objetivo: Brier < **{BRIER_GATE}**")
        md.append("")
        if gate_ok:
            md.append(f"✅ **GATE SUPERADO** — Brier calibrado "
                      f"{brier_cv:.4f} < {BRIER_GATE}.")
        else:
            md.append(f"❌ **GATE NO SUPERADO** — Brier calibrado "
                      f"{brier_cv:.4f} ≥ {BRIER_GATE}.")
            md.append("")
            md.append(
                "Platt scaling solo corrige la **calibración** (que los "
                "porcentajes declarados coincidan con la realidad). NO añade "
                "**poder de discriminación**: es una transformación monótona, "
                "no puede separar mejor aciertos de fallos de lo que ya los "
                "separa el modelo. Si el Brier calibrado ronda el baseline "
                f"(p̄·(1−p̄) ≈ {sum(1 for p in picks if p['acerto'])/len(picks)*(1-sum(1 for p in picks if p['acerto'])/len(picks)):.4f}), "
                "significa que el modelo subyacente casi no discrimina sobre "
                "esta muestra — y la muestra está contaminada por los bugs "
                "BUG-1/BUG-2 ya corregidos. La conclusión NO es 'Platt falló', "
                "sino que el gate < 0.24 no es alcanzable con este histórico: "
                "hay que rehacer la validación con datos limpios del modelo "
                "nuevo tras el shadow-testing.")
        md.append("")

    md.append("\n## 5. Limitación importante\n")
    md.append(
        "Este backtest mide el modelo **viejo** (las probabilidades guardadas "
        "en el log). NO puede simular el modelo logístico nuevo sobre partidos "
        "pasados porque el log no guarda las estadísticas crudas de cada "
        "equipo. El Brier Score de arriba es la **línea base a superar**.\n\n"
        "Para validar el modelo nuevo:\n"
        "1. Dejar el motor nuevo corriendo en modo shadow (loguear su "
        "predicción sin publicarla) por 2-4 semanas.\n"
        "2. Volver a correr este script sobre el log nuevo.\n"
        "3. Comparar Brier Score y ROI nuevo vs el de esta corrida.\n"
    )

    report = "\n".join(md)
    OUT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[Reporte guardado en {OUT_PATH}]")


if __name__ == "__main__":
    main()
