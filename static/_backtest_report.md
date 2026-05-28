# Backtest del motor PREDIKTOR

Generado: 2026-05-28T11:24:51

Fuente: `static/predictions_log.json` — 110 entradas, 62 picks cuantificables (verificados, con cuota, sin rechazados por Filtro 1).


## 1. Histórico completo

### Todos los picks cuantificables

- Picks: **62**  ·  Aciertos: 29/62 = **46.8%**
- Brier Score (modelo viejo): **0.3059**  _(más bajo = mejor; baseline sin skill ≈ 0.2490)_
- ROI apuesta plana: **-14.94%**  (-9.26 u sobre 62 u)
- ROI Quarter-Kelly: **-66.69%**  (bankroll 100 → 33.31)
- Drawdown máximo (Quarter-Kelly): **71.3%**


## 2. Últimos 30 días

_(picks con fecha ≥ 2026-04-28)_


### Últimos 30 días

- Picks: **41**  ·  Aciertos: 18/41 = **43.9%**
- Brier Score (modelo viejo): **0.3207**  _(más bajo = mejor; baseline sin skill ≈ 0.2463)_
- ROI apuesta plana: **-22.64%**  (-9.28 u sobre 41 u)
- ROI Quarter-Kelly: **-63.96%**  (bankroll 100 → 36.04)
- Drawdown máximo (Quarter-Kelly): **68.0%**


## 3. Curva de calibración (modelo viejo)

Si el modelo estuviera bien calibrado, 'declarada' ≈ 'real'.


| Bucket prob | n | Prob declarada | Hit real | Gap |
|---|---|---|---|---|
| 0-50% | 3 | 48.1% | 33.3% | -14.7 pp |
| 50-60% | 7 | 56.8% | 71.4% | +14.6 pp |
| 60-70% | 26 | 65.3% | 46.2% | -19.1 pp |
| 70-75% | 11 | 72.5% | 36.4% | -36.1 pp |
| 75-80% | 11 | 76.9% | 45.5% | -31.5 pp |
| 80-90% | 4 | 84.7% | 50.0% | -34.7 pp |


## 4. Validación de la calibración (Platt scaling)

Validación cruzada 5-fold (out-of-fold, sin fuga de datos) sobre 62 picks:

- Brier modelo crudo (sin calibrar): **0.3109**
- Brier modelo calibrado (Platt, CV): **0.2543**
- Mejora por calibración: **+0.0567**
- Umbral objetivo: Brier < **0.24**

❌ **GATE NO SUPERADO** — Brier calibrado 0.2543 ≥ 0.24.

Platt scaling solo corrige la **calibración** (que los porcentajes declarados coincidan con la realidad). NO añade **poder de discriminación**: es una transformación monótona, no puede separar mejor aciertos de fallos de lo que ya los separa el modelo. Si el Brier calibrado ronda el baseline (p̄·(1−p̄) ≈ 0.2490), significa que el modelo subyacente casi no discrimina sobre esta muestra — y la muestra está contaminada por los bugs BUG-1/BUG-2 ya corregidos. La conclusión NO es 'Platt falló', sino que el gate < 0.24 no es alcanzable con este histórico: hay que rehacer la validación con datos limpios del modelo nuevo tras el shadow-testing.


## 5. Limitación importante

Este backtest mide el modelo **viejo** (las probabilidades guardadas en el log). NO puede simular el modelo logístico nuevo sobre partidos pasados porque el log no guarda las estadísticas crudas de cada equipo. El Brier Score de arriba es la **línea base a superar**.

Para validar el modelo nuevo:
1. Dejar el motor nuevo corriendo en modo shadow (loguear su predicción sin publicarla) por 2-4 semanas.
2. Volver a correr este script sobre el log nuevo.
3. Comparar Brier Score y ROI nuevo vs el de esta corrida.
