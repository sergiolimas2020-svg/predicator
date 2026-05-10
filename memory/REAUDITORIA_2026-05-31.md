# REAUDITORÍA — Filtro 1 (forma reciente del favorito) — 2026-05-31

**Fecha objetivo:** sábado 31 de mayo de 2026
**Programado el:** 2026-05-10
**Commit que activó el filtro en producción:** `9520a3c` (2026-05-10)
**Primer día con filtro activo:** 2026-05-12

---

## Contexto

El 11-may simulamos retroactivamente sobre 38 picks históricos un filtro
que rechaza al favorito si tiene **<2 victorias en sus últimos 5 partidos
de su liga doméstica**. Resultado: yield −16.19% → +2.66% (Δ +18.85 pp),
precisión rechazo 75% (9/12 fallos correctamente rechazados).

Lo desplegamos en producción el 2026-05-10. Tras 20 días de operación
(2026-05-12 → 2026-05-31), corresponde validar prospectivamente.

**Riesgo a confirmar:** el primer día con datos reales (2026-05-12, La
Liga) los 3 favoritos del día tenían `W5=2` exactamente — pasaron por
borde mínimo. Si esa cohorte rinde sistemáticamente peor que `W5≥3`, el
umbral debe subir.

---

## Pasos a ejecutar el 2026-05-31

### 1. Filtrar el log

```python
import json
from datetime import date
log = json.load(open("static/predictions_log.json"))

published = [
    e for e in log
    if e.get("fecha", "") >= "2026-05-12"
    and e.get("fecha", "") <= "2026-05-31"
    and e.get("tipo_pick") != "rejected_recent_form"
    and e.get("acerto") is not None
    and e.get("bk_odds") is not None
]
rejected = [
    e for e in log
    if e.get("fecha", "") >= "2026-05-12"
    and e.get("fecha", "") <= "2026-05-31"
    and e.get("tipo_pick") == "rejected_recent_form"
]
```

### 2. Yield agregado de publicados

```python
def pnl(e):
    return (e["bk_odds"] - 1) if e["acerto"] else -1

n = len(published)
hit = sum(1 for e in published if e["acerto"])
yld = sum(pnl(e) for e in published) / n * 100 if n else 0
print(f"Publicados — n={n}  hit={hit}/{n}={hit/n*100:.1f}%  yield={yld:+.2f}%")
```

Comparar contra el baseline de la simulación retrospectiva (yield −16.19%
sobre n=38). El filtro debería sostener yield ≥ 0% en producción para
considerarse validado.

### 3. Segmentar publicados por `rf_wins`

Los picks publicados después del 2026-05-12 deben tener el campo
`rf_wins` (cuando había datos suficientes). Agrupar:

```python
from collections import defaultdict
buckets = defaultdict(list)
for e in published:
    w5 = e.get("rf_wins")
    key = "W5=2" if w5 == 2 else ("W5=3" if w5 == 3 else
          ("W5≥4" if w5 and w5 >= 4 else "sin_datos"))
    buckets[key].append(e)

for k, v in buckets.items():
    if not v: continue
    n = len(v)
    hit = sum(1 for e in v if e["acerto"])
    yld = sum(pnl(e) for e in v) / n * 100
    print(f"  {k:10s} n={n:3d}  hit={hit/n*100:5.1f}%  yield={yld:+6.2f}%")
```

**Lectura:** si `W5=2` muestra yield <0% mientras `W5≥3` rinde >0%, hay
señal para subir umbral a `<3`. Si todos los buckets rinden similar, el
umbral actual está bien.

### 4. Auditoría del rechazo (would-have-acerto)

```python
ver_real = [e for e in rejected if e.get("would_have_acerto") is not None]
n_rej = len(ver_real)
wha_hit = sum(1 for e in ver_real if e.get("would_have_acerto"))
wha_yld = (
    sum((e["bk_odds"] - 1) if e.get("would_have_acerto") else -1
        for e in ver_real) / n_rej * 100
    if n_rej else 0
)
print(f"Rechazados verificados — n={n_rej}  would_have_hit={wha_hit/n_rej*100:.1f}%  "
      f"would_have_yield={wha_yld:+.2f}%")
```

**Lectura:** si `would_have_yield` < yield publicados → filtro acertó al
rechazar (los rechazados eran picks malos). Si `would_have_yield` > yield
publicados → filtro está perdiendo dinero.

### 5. Por liga — atención especial Süper Lig

```python
from collections import Counter
by_league = defaultdict(list)
for e in published:
    by_league[e["league"]].append(e)
for league in sorted(by_league):
    sub = by_league[league]
    if len(sub) < 2: continue
    n = len(sub); hit = sum(1 for e in sub if e["acerto"])
    yld = sum(pnl(e) for e in sub) / n * 100
    print(f"  {league:25s} n={n:2d}  hit={hit/n*100:5.1f}%  yield={yld:+6.2f}%")
```

Verificar específicamente:
- **Süper Lig:** ¿el tier 0.92 + Filtro 1 logró yield ≥ 0%? Si sigue
  negativo, agregar a `EXCLUDED_LEAGUES` definitivamente.
- **Otras ligas con yield <0% sostenido:** evaluar si el problema es
  sample size o estructural.

### 6. Cobertura del filtro

```python
with_data = sum(1 for e in published if e.get("rf_wins") is not None)
print(f"Picks publicados con rf_wins: {with_data}/{len(published)} "
      f"({with_data/len(published)*100:.0f}%)")
```

Si el % es bajo (<60%), revisar:
- Si `secrets.API_FOOTBALL_KEY` está bien en GitHub Actions
- Si `collect_daily.py` corrió en cada cron (revisar logs de Actions)
- Si `teams_map.json` está vigente (re-correr `mapping.py` si hay equipos
  nuevos en `odds.json`)

---

## Decisiones posibles post-reauditoría

| Resultado | Acción |
|---|---|
| Yield publicados >0% sostenido | Mantener filtro como está |
| `W5=2` rinde mucho peor que `W5≥3` | Subir `RECENT_FORM_MIN_WINS = 3` |
| Süper Lig yield <0% pese a tier 0.92 | Re-agregar a `EXCLUDED_LEAGUES` |
| Yield publicados <0% (filtro empeora cosas) | Bajar `USE_RECENT_FORM_FILTER = False` y replantear |

## Constantes a tocar

`scrapers/generate_predictions.py`:
- `USE_RECENT_FORM_FILTER` — toggle global (línea ~272)
- `RECENT_FORM_MIN_WINS` — umbral de victorias (línea ~273)
- `EXCLUDED_LEAGUES` — set de ligas bloqueadas (línea ~150)
- `CONF_LEAGUE_TIERS["Super Lig"]` — tier de la liga (línea ~262)

## Entregable

Informe en markdown comparable al [report del 11-may en `/tmp/filter1_report.md`]
para auditoría longitudinal. Guardarlo en `analysis/reauditoria_2026-05-31.md`
si se decide commitear, o `/tmp/` para análisis efímero.

---

## Memoria asociada

Esta reauditoría también está registrada en la memoria persistente de
Claude Code:
`~/.claude/projects/-Users-sergiolimas-Desktop-PREDICATOR/memory/project_filtro1_w5_reauditoria.md`
