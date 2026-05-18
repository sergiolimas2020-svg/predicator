# Backtest del motor PREDIKTOR

Generado: 2026-05-17T23:42:38

Fuente: `static/predictions_log.json` — 80 entradas, 49 picks cuantificables (verificados, con cuota, sin rechazados por Filtro 1).


## 1. Histórico completo

### Todos los picks cuantificables

- Picks: **49**  ·  Aciertos: 26/49 = **53.1%**
- Brier Score (modelo viejo): **0.2746**  _(más bajo = mejor; baseline sin skill ≈ 0.2491)_
- ROI apuesta plana: **-4.46%**  (-2.19 u sobre 49 u)
- ROI Quarter-Kelly: **-32.62%**  (bankroll 100 → 67.38)
- Drawdown máximo (Quarter-Kelly): **51.3%**


## 2. Últimos 30 días

_(picks con fecha ≥ 2026-04-17)_


### Últimos 30 días

- Picks: **34**  ·  Aciertos: 18/34 = **52.9%**
- Brier Score (modelo viejo): **0.2810**  _(más bajo = mejor; baseline sin skill ≈ 0.2491)_
- ROI apuesta plana: **-5.26%**  (-1.79 u sobre 34 u)
- ROI Quarter-Kelly: **-27.63%**  (bankroll 100 → 72.37)
- Drawdown máximo (Quarter-Kelly): **51.3%**


## 3. Curva de calibración (modelo viejo)

Si el modelo estuviera bien calibrado, 'declarada' ≈ 'real'.


| Bucket prob | n | Prob declarada | Hit real | Gap |
|---|---|---|---|---|
| 0-50% | 3 | 48.1% | 33.3% | -14.7 pp |
| 50-60% | 6 | 57.0% | 66.7% | +9.7 pp |
| 60-70% | 20 | 64.9% | 55.0% | -9.9 pp |
| 70-75% | 8 | 72.6% | 37.5% | -35.1 pp |
| 75-80% | 9 | 77.0% | 55.6% | -21.5 pp |
| 80-90% | 3 | 85.5% | 66.7% | -18.8 pp |


## 4. Validación de la calibración (Platt scaling)

Validación cruzada 5-fold (out-of-fold, sin fuga de datos) sobre 49 picks:

- Brier modelo crudo (sin calibrar): **0.2786**
- Brier modelo calibrado (Platt, CV): **0.2568**
- Mejora por calibración: **+0.0218**
- Umbral objetivo: Brier < **0.24**

❌ **GATE NO SUPERADO** — Brier calibrado 0.2568 ≥ 0.24.

Platt scaling solo corrige la **calibración** (que los porcentajes declarados coincidan con la realidad). NO añade **poder de discriminación**: es una transformación monótona, no puede separar mejor aciertos de fallos de lo que ya los separa el modelo. Si el Brier calibrado ronda el baseline (p̄·(1−p̄) ≈ 0.2491), significa que el modelo subyacente casi no discrimina sobre esta muestra — y la muestra está contaminada por los bugs BUG-1/BUG-2 ya corregidos. La conclusión NO es 'Platt falló', sino que el gate < 0.24 no es alcanzable con este histórico: hay que rehacer la validación con datos limpios del modelo nuevo tras el shadow-testing.


## 5. Limitación importante

Este backtest mide el modelo **viejo** (las probabilidades guardadas en el log). NO puede simular el modelo logístico nuevo sobre partidos pasados porque el log no guarda las estadísticas crudas de cada equipo. El Brier Score de arriba es la **línea base a superar**.

Para validar el modelo nuevo:
1. Dejar el motor nuevo corriendo en modo shadow (loguear su predicción sin publicarla) por 2-4 semanas.
2. Volver a correr este script sobre el log nuevo.
3. Comparar Brier Score y ROI nuevo vs el de esta corrida.
