"""
Simulador del Bug #1 — reordenar market_priority().

Lee predictions_log.json y para cada pick post-refactor (con markets_evaluated)
determina si el NUEVO orden habría elegido un mercado distinto. Reporta:

  - Cuántos picks NO cambian (1 solo "ok" disponible o ordenamiento no afecta)
  - Cuántos picks cambian de mercado
  - Tasa histórica del mercado nuevo vs el original
  - Estimación direccional del impacto (no determinístico — solo señal)

LIMITACIÓN: el log solo guarda el resultado del mercado efectivamente
publicado. NO sabemos si el mercado alternativo habría acertado en cada
partido específico. Por eso la simulación da SEÑAL DIRECCIONAL, no
predicción exacta.

Uso:
    python3 scripts/simulate_market_priority.py
"""
from __future__ import annotations
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "static" / "predictions_log.json"


# ── Order viejo ──────────────────────────────────────────────
def market_priority_OLD(label, league=None):
    if "Over" in label:               return 0
    if "sin empate" in label:         return 1
    if "Doble oportunidad" in label:  return 2
    return 3


# ── Order nuevo (mi cambio) ──────────────────────────────────
def market_priority_NEW(label, league=None):
    if "Over 1.5" in label:
        return 0 if league == "Liga Colombiana" else 4
    if "Over" in label:               return 4
    if "sin empate" in label:         return 3
    if "Doble oportunidad" in label:  return 2
    return 1


def categorize(label):
    if not label: return "unknown"
    if "Over 1.5" in label:        return "Over 1.5"
    if "Over 2.5" in label:        return "Over 2.5"
    if "sin empate" in label:      return "DNB"
    if "Doble oportunidad" in label: return "DC"
    return "ML"


def main():
    log = json.loads(LOG_PATH.read_text())
    verificados = [e for e in log if e.get("acerto") is not None]
    con_evals   = [e for e in verificados if e.get("markets_evaluated")]

    # Tasas históricas por categoría (todos los 64 verificados)
    tasas = defaultdict(lambda: [0, 0])
    for e in verificados:
        cat = categorize(e.get("prediccion") or "")
        tasas[cat][1] += 1
        if e["acerto"]: tasas[cat][0] += 1

    print("═" * 80)
    print(" SIMULADOR market_priority — efecto del reorden")
    print("═" * 80)
    print(f"\nUniverso: {len(con_evals)} picks post-refactor con markets_evaluated")
    print(f"          ({len(verificados)} verificados totales en el log)\n")

    print(f"{'Mercado':<15}{'Tasa histórica':<25}{'Prioridad NEW'}")
    print("-" * 60)
    for cat in ("ML", "DC", "DNB", "Over 2.5", "Over 1.5"):
        g, t = tasas[cat]
        pct = f"{g}/{t} = {g/t*100:.1f}%" if t else "—"
        prio = market_priority_NEW({"ML":"x","DC":"Doble oportunidad: x","DNB":"Apuesta sin empate: x",
                                     "Over 2.5":"Over 2.5 goles","Over 1.5":"Over 1.5 goles"}[cat])
        print(f"{cat:<15}{pct:<25}{prio}")

    # ── simulación ──────────────────────────────────────────
    no_change = 0
    changed   = []  # list of (slug, league, original, simulated, acerto_original)

    for e in con_evals:
        league = e.get("league")
        evals  = e["markets_evaluated"]
        # Filtrar solo mercados "ok" (los únicos que el motor consideraría)
        ok_evals = [m for m in evals if m.get("reason") == "ok"]
        if len(ok_evals) <= 1:
            no_change += 1
            continue

        # Original: el mercado con menor priority_OLD (o el publicado, que es lo mismo)
        original_label = e.get("prediccion") or ""

        # Nuevo: el mercado con menor priority_NEW (desempate por value_score desc)
        def key_new(m):
            return (market_priority_NEW(m["market"], league), -(m.get("value_score") or 0))
        sim_choice = min(ok_evals, key=key_new)
        sim_label  = sim_choice["market"]

        if categorize(sim_label) == categorize(original_label):
            no_change += 1
        else:
            changed.append({
                "slug":     e["slug"],
                "league":   league,
                "original": original_label,
                "orig_cat": categorize(original_label),
                "sim":      sim_label,
                "sim_cat":  categorize(sim_label),
                "acerto":   e["acerto"],
            })

    print(f"\n{'─'*80}")
    print(f"Resultado:")
    print(f"  Picks sin cambio:    {no_change} de {len(con_evals)}")
    print(f"  Picks que cambian:   {len(changed)} de {len(con_evals)}")
    print(f"{'─'*80}")

    if changed:
        print(f"\n{'Pick':<55}{'Original → Nuevo':<20}{'Acertó orig?'}")
        print("-" * 100)
        # Tablas de cambios direccionales
        flujo = Counter()
        for c in changed:
            flujo[(c["orig_cat"], c["sim_cat"])] += 1
            ok_str = "✓" if c["acerto"] else "✗"
            print(f"  [{c['league'][:18]}] {c['slug'][:32]:<35}{c['orig_cat']:>5} → {c['sim_cat']:<10}  {ok_str}")

        print(f"\n=== Direcciones del cambio ===")
        for (orig, sim), n in flujo.most_common():
            tasa_orig = tasas[orig]; tasa_sim = tasas[sim]
            t_o = f"{tasa_orig[0]}/{tasa_orig[1]} = {tasa_orig[0]/tasa_orig[1]*100:.0f}%" if tasa_orig[1] else "n/a"
            t_s = f"{tasa_sim[0]}/{tasa_sim[1]} = {tasa_sim[0]/tasa_sim[1]*100:.0f}%" if tasa_sim[1] else "n/a"
            print(f"  {orig:<10} → {sim:<10}  ({n} picks)  histórico: {t_o} → {t_s}")

        # Estimación direccional
        print(f"\n=== Estimación direccional (NO determinística) ===")
        # Para cada cambio: ¿el mercado destino tiene mejor tasa que el original?
        better, worse, neutral = 0, 0, 0
        for c in changed:
            orig_pct = tasas[c["orig_cat"]][0] / tasas[c["orig_cat"]][1] if tasas[c["orig_cat"]][1] else 0
            sim_pct  = tasas[c["sim_cat"]][0] / tasas[c["sim_cat"]][1]  if tasas[c["sim_cat"]][1]  else 0
            if sim_pct > orig_pct + 0.01:   better += 1
            elif sim_pct < orig_pct - 0.01: worse += 1
            else:                           neutral += 1
        print(f"  Cambios HACIA mercado de mejor tasa histórica: {better}")
        print(f"  Cambios HACIA mercado de peor tasa histórica:  {worse}")
        print(f"  Cambios neutrales (~misma tasa):               {neutral}")

        # Análisis del subconjunto que cambia
        acertados_orig = sum(1 for c in changed if c["acerto"])
        print(f"\n  De los {len(changed)} picks que cambiarían:")
        print(f"    El mercado ORIGINAL acertó en: {acertados_orig}/{len(changed)} = {acertados_orig/len(changed)*100:.1f}%")
        print(f"    Si el nuevo mercado tiene tasa histórica X%, el efecto neto es ~ X% - {acertados_orig/len(changed)*100:.1f}%")
    else:
        print("\n  Ningún pick cambia de mercado con el nuevo orden.")
        print("  El bug #1 en sí no afectaría picks pasados — el efecto sería en partidos FUTUROS")
        print("  donde múltiples mercados estén 'ok' simultáneamente (raro post-refactor).")


if __name__ == "__main__":
    main()
