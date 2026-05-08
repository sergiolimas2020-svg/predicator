"""
Simulador del Bug #2 — bajar PENALTY_LOW de 0.06 a 0.03.

Lee predictions_log.json y estima el efecto del cambio.

LIMITACIÓN CLAVE: el log solo guarda picks PUBLICADOS, no rechazados.
Por eso no podemos contar exactamente "cuántos picks nuevos aparecerían".
El simulador hace 3 análisis direccionales:

  (1) Mercados con freq actual < 0.10 que reciben PENALTY_LOW (los afectados)
  (2) Entries con reason="ev_insuficiente" dentro de markets_evaluated cuya
      ev_adjusted está en zona donde la nueva penalty los desbloquearía
  (3) Tasa histórica de los mercados que se desbloquearían

Uso:
    python3 scripts/simulate_penalty_low.py
"""
from __future__ import annotations
import json, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "static" / "predictions_log.json"
sys.path.insert(0, str(ROOT / "scrapers"))


def categorize(label):
    if not label: return "unknown"
    if "Over 1.5" in label:        return "Over 1.5"
    if "Over 2.5" in label:        return "Over 2.5"
    if "sin empate" in label:      return "DNB"
    if "Doble oportunidad" in label: return "DC"
    return "ML"


def main():
    print("═" * 78)
    print(" SIMULADOR Bug #2 — efecto de bajar PENALTY_LOW de 0.06 a 0.03")
    print("═" * 78)

    # ── 1) Mercados afectados por PENALTY_LOW (freq < 0.10) hoy ──
    from generate_predictions import _compute_market_freqs, PENALTY_FREQ_MID, MIN_EV
    freqs = _compute_market_freqs()
    print(f"\n--- (1) Frecuencias actuales en odds.json ---")
    print(f"{'mercado':<12}{'freq':>10}{'¿afectado por PENALTY_LOW?'}")
    print("-" * 55)
    afectados = []
    for k, f in sorted(freqs.items(), key=lambda x: x[1]):
        flag = "SÍ (era penalty=0.06, ahora 0.03)" if f < PENALTY_FREQ_MID else "no"
        print(f"{k:<12}{f:>10.4f}    {flag}")
        if f < PENALTY_FREQ_MID:
            afectados.append(k)

    if not afectados:
        print(f"\n  No hay mercados con freq < {PENALTY_FREQ_MID} → el cambio no afecta NADA hoy.")
    else:
        print(f"\n  Mercados afectados: {', '.join(afectados)}")

    # ── 2) markets_evaluated con reason "ev_insuficiente" en zona ──
    log = json.loads(LOG_PATH.read_text())
    verificados = [e for e in log if e.get("acerto") is not None]
    con_evals = [e for e in verificados if e.get("markets_evaluated")]

    print(f"\n--- (2) Picks que habrían sido publicados con PENALTY_LOW=0.03 ---")
    print(f"  Universo: {len(con_evals)} entries con markets_evaluated")
    print()

    # Para cada entry, buscar mercados rechazados por "ev_insuficiente"
    # cuya ev_adjusted está entre [MIN_EV - 0.03, MIN_EV) — la nueva penalty
    # subiría +3pp y pasaría el filtro. Pero solo aplica a mercados con freq<0.10
    MIN_EV_PCT = MIN_EV * 100  # 15.0
    DELTA = 3.0  # 0.06 - 0.03

    # Marcadores aproximados de qué mercados son ilíquidos
    iliquid_kw = {"Over 1.5"}  # solo Over 1.5 en odds.json actual

    candidatos = []
    for e in con_evals:
        for m in e.get("markets_evaluated", []):
            label = m.get("market", "")
            cat = categorize(label)
            ev_adj = m.get("ev_adjusted")
            reason = m.get("reason")
            if reason != "ev_insuficiente":
                continue
            if ev_adj is None:
                continue
            # ¿Sería ilíquido? (heurística por categoría)
            if cat not in ("Over 1.5",):
                continue
            # ¿Pasa con el delta? Si ev_adj + 3 >= 15 → pasa
            if ev_adj + DELTA >= MIN_EV_PCT:
                candidatos.append({
                    "fecha": e["fecha"],
                    "slug":  e["slug"],
                    "league": e["league"],
                    "market": label,
                    "ev_adj_actual": ev_adj,
                    "ev_adj_nuevo": ev_adj + DELTA,
                    "acerto_pick_publicado": e["acerto"],
                })

    if not candidatos:
        print(f"  → 0 picks habrían cambiado de estado con PENALTY_LOW=0.03")
        print(f"     (ningún markets_evaluated registró Over 1.5 con reason='ev_insuficiente'")
        print(f"      y ev_adj entre {MIN_EV_PCT-DELTA:.0f}% y {MIN_EV_PCT:.0f}%).")
    else:
        print(f"  → {len(candidatos)} picks habrían sido CONSIDERADOS adicionalmente")
        print(f"\n  {'fecha':<12}{'liga':<22}{'mercado':<22}{'ev_act':>9}{'ev_nuevo':>10}")
        print("  " + "-"*75)
        for c in candidatos:
            print(f"  {c['fecha']:<12}{c['league'][:20]:<22}{c['market'][:20]:<22}{c['ev_adj_actual']:>8.1f}%{c['ev_adj_nuevo']:>9.1f}%")

    # ── 3) Tasa histórica de mercados desbloqueables ──
    print(f"\n--- (3) Tasa histórica de Over 1.5 (el mercado afectado) ---")
    over15 = [e for e in verificados if "Over 1.5" in (e.get("prediccion") or "")]
    g = sum(1 for e in over15 if e["acerto"])
    t = len(over15)
    print(f"  Over 1.5 histórico: {g}/{t} = {g/t*100:.0f}% (n={t})")
    print(f"  Por liga:")
    by_liga = defaultdict(lambda: [0, 0])
    for e in over15:
        by_liga[e["league"]][1] += 1
        if e["acerto"]: by_liga[e["league"]][0] += 1
    for liga, (g, t) in by_liga.items():
        print(f"    {liga:<25} {g}/{t} = {g/t*100:.0f}%")
    if t < 10:
        print(f"\n  ⚠️ MUESTRA INSUFICIENTE: n={t} es ruido, no señal estadística.")

    # ── 4) Estado actual: ¿cuántos picks NO se publicaron ese mes que tuvieron Over 1.5? ──
    print(f"\n--- (4) Volumen Over 1.5 antes/después del refactor ---")
    PIVOT = "2026-04-04"
    over15_pre  = [e for e in over15 if e["fecha"] < PIVOT]
    over15_post = [e for e in over15 if e["fecha"] >= PIVOT]
    print(f"  Pre  ({PIVOT}>):    {len(over15_pre)} picks Over 1.5 (en {len([e for e in verificados if e['fecha']<PIVOT])} verificados)")
    print(f"  Post ({PIVOT}>=):  {len(over15_post)} picks Over 1.5 (en {len([e for e in verificados if e['fecha']>=PIVOT])} verificados)")

    # ── Conclusión direccional ──
    print(f"\n{'═'*78}")
    print(" CONCLUSIÓN DEL SIMULADOR")
    print(f"{'═'*78}")
    if not candidatos:
        print(f"""
  Con los datos actuales del log, el cambio PENALTY_LOW 0.06→0.03 no
  desbloquea NINGÚN pick que el log haya registrado como rechazado por
  ev_insuficiente.

  Posibles razones:
  - El log NO guarda los entries de markets_evaluated cuando el partido
    completo no produjo pick (porque entonces nada se loggea).
  - Los Over 1.5 que sí se evaluaron post-refactor probablemente
    fueron descartados con reason="mercado_no_disponible" (la cuota
    no estaba en el feed de The Odds API ese día), no por ev_insuficiente.
  - Otros descartes: ev_negativo, ev_excesivo, cuota_baja.

  Implicación: este simulador NO puede validar el cambio. La validación
  real requiere correr el motor en CI con el nuevo PENALTY_LOW durante
  N días y medir el efecto empírico vs el grupo de control.
""")
    else:
        print(f"\n  {len(candidatos)} picks habrían sido considerados adicionalmente.")
        print(f"  Tasa histórica del mercado desbloqueado: ver sección (3) arriba.")


if __name__ == "__main__":
    main()
