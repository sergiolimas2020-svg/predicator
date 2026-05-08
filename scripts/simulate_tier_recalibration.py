"""
Simulador del Bug #3 — recalibrar Premier/LaLiga/Bundes/Ligue1 a tier MID.

Para cada pick de las 4 ligas afectadas en el log:
  1. Recalcula prob_adjusted con cf=0.97 en lugar de cf=1.00
  2. Recalcula ev_adjusted con la nueva prob_adjusted (manteniendo penalty)
  3. Determina si el nuevo ev_adjusted >= MIN_EV
  4. Si NO → pick rechazado retroactivamente

Reporta:
  - Picks rechazados retroactivamente (acierto vs fallo)
  - Impacto neto en tasa global

LIMITACIÓN: solo simula sobre picks PUBLICADOS (los rechazados no están en
el log). El cambio podría también dejar pasar nuevos picks (los que estaban
justo bajo el filtro y al cambiar el cf... espera, NO: bajar cf reduce
prob_adjusted, así que solo rechaza más, no menos).

Uso:
    python3 scripts/simulate_tier_recalibration.py
"""
from __future__ import annotations
import json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "static" / "predictions_log.json"
sys.path.insert(0, str(ROOT / "scrapers"))

# Importar constantes del motor (post-cambio)
from generate_predictions import (
    MIN_EV, CONF_LEAGUE_TOP, CONF_LEAGUE_MID, CONF_LEAGUE_TIERS,
)

# Ligas que el cambio mueve a MID (cf 1.00 → 0.97)
# Versión conservadora: solo Premier y Ligue 1 (datos más contundentes).
# La Liga (n=5, 40%) y Bundesliga (n=3, 33%) se mantienen en TOP — la
# simulación con las 4 mostraba que mover Bundes perdía 1 acierto.
LIGAS_AFECTADAS = {"Premier League", "Ligue 1"}
CF_OLD = CONF_LEAGUE_TOP   # 1.00
CF_NEW = CONF_LEAGUE_MID   # 0.97
MIN_EV_PCT = MIN_EV * 100  # 15.0


def main():
    log = json.loads(LOG_PATH.read_text())
    verificados = [e for e in log if e.get("acerto") is not None]

    # Solo entries con campos numéricos suficientes (post-refactor 4-abril)
    eligibles = [e for e in verificados
                 if e.get("prob_adjusted") and e.get("bk_odds") and e.get("ev_adjusted") is not None]

    print("═" * 80)
    print(" SIMULADOR Bug #3 — recalibración tier europeo")
    print("═" * 80)
    print(f"\nUniverso post-refactor: {len(eligibles)} entries con datos completos")
    print(f"De ellos, en ligas afectadas (Premier/LaLiga/Bundes/Ligue1): "
          f"{sum(1 for e in eligibles if e['league'] in LIGAS_AFECTADAS)}")
    print(f"\nMIN_EV = {MIN_EV_PCT}%, CF_OLD = {CF_OLD}, CF_NEW = {CF_NEW}\n")

    # Picks de ligas afectadas
    afectados = [e for e in eligibles if e["league"] in LIGAS_AFECTADAS]
    print(f"{'Liga':<18}{'Match':<35}{'EV act':>9}{'EV new':>9}{'¿pasa?':>9}{'Acertó?':>10}")
    print("-" * 100)

    rechazados = []
    sobreviven = []
    for e in afectados:
        prob_adj_orig = e["prob_adjusted"]   # ya con cf antiguo (≈1.00 para TOP)
        cf_orig = e.get("confidence_factor", CF_OLD)
        bk = e["bk_odds"]
        penalty_pct = e.get("penalty", 0) or 0  # en %

        # 1. Reconstruir prob_original (deshacer cf antiguo)
        prob_original = prob_adj_orig / cf_orig if cf_orig else prob_adj_orig

        # 2. Aplicar cf nuevo
        prob_adj_new = prob_original * CF_NEW

        # 3. Recalcular ev_model y ev_adjusted nuevos
        ev_model_new = (prob_adj_new / 100) * bk - 1   # como decimal
        ev_adj_new_pct = ev_model_new * 100 - penalty_pct  # restar penalty (en pp)

        pasa_nuevo = ev_adj_new_pct >= MIN_EV_PCT
        ok_str = "✓" if pasa_nuevo else "✗ rechazado"
        ac_str = "✓" if e["acerto"] else "✗"

        match = f"{e['home']} vs {e['away']}"[:33]
        print(f"{e['league'][:17]:<18}{match:<35}{e['ev_adjusted']:>8.1f}%{ev_adj_new_pct:>8.1f}%{ok_str:>10}{ac_str:>10}")

        if not pasa_nuevo:
            rechazados.append(e)
        else:
            sobreviven.append(e)

    # ── Impacto neto ──
    aciertos_perdidos = sum(1 for e in rechazados if e["acerto"])
    fallos_evitados   = sum(1 for e in rechazados if not e["acerto"])

    print(f"\n{'─'*80}")
    print(f" Picks afectados:        {len(afectados)}")
    print(f"   Sobreviven:           {len(sobreviven)}")
    print(f"   Rechazados:           {len(rechazados)}")
    print(f"     - Aciertos perdidos:  {aciertos_perdidos}")
    print(f"     - Fallos evitados:    {fallos_evitados}")
    print(f"     - Impacto neto:       {fallos_evitados - aciertos_perdidos:+d} (positivo = mejora)")
    print(f"{'─'*80}")

    # ── Tasas comparadas ──
    total_actual    = len(verificados)
    aciertos_actual = sum(1 for e in verificados if e["acerto"])

    total_simulado    = total_actual - len(rechazados)
    aciertos_simulado = aciertos_actual - aciertos_perdidos

    if total_simulado > 0:
        tasa_actual    = aciertos_actual    / total_actual * 100
        tasa_simulada  = aciertos_simulado  / total_simulado * 100
        delta_tasa     = tasa_simulada - tasa_actual

        print(f"\n=== Comparación de tasas (universo COMPLETO incl. pre-refactor) ===")
        print(f"  Tasa actual    {aciertos_actual:>3}/{total_actual:>3} = {tasa_actual:.2f}%")
        print(f"  Tasa simulada  {aciertos_simulado:>3}/{total_simulado:>3} = {tasa_simulada:.2f}%")
        print(f"  Δ tasa         {delta_tasa:+.2f} pp")

    # Solo post-refactor
    post = [e for e in verificados if (e.get("bk_odds") or 0) > 0]
    post_g = sum(1 for e in post if e["acerto"])
    post_g_sim = post_g - aciertos_perdidos
    post_t_sim = len(post) - len(rechazados)
    if post_t_sim > 0:
        ta = post_g / len(post) * 100
        ts = post_g_sim / post_t_sim * 100
        print(f"\n=== Solo post-refactor (donde el cambio puede actuar) ===")
        print(f"  Tasa actual   {post_g}/{len(post)} = {ta:.2f}%")
        print(f"  Tasa simulada {post_g_sim}/{post_t_sim} = {ts:.2f}%")
        print(f"  Δ tasa        {ts - ta:+.2f} pp")

    # ── Breakdown por liga ──
    if rechazados:
        print(f"\n=== Picks rechazados — breakdown por liga ===")
        by_l = defaultdict(lambda: {"acert": 0, "fall": 0})
        for e in rechazados:
            (by_l[e["league"]]["acert"] if e["acerto"] else by_l[e["league"]]["fall"]) ; # noop
            if e["acerto"]: by_l[e["league"]]["acert"] += 1
            else:           by_l[e["league"]]["fall"]  += 1
        print(f"\n  {'Liga':<20}{'Aciertos perdidos':<22}{'Fallos evitados':<20}{'Neto'}")
        print(f"  {'-'*70}")
        for liga, d in sorted(by_l.items(), key=lambda x: -x[1]["fall"] + x[1]["acert"]):
            neto = d["fall"] - d["acert"]
            print(f"  {liga:<20}{d['acert']:<22}{d['fall']:<20}{neto:+d}")


if __name__ == "__main__":
    main()
