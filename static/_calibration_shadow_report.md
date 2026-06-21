# Calibración conservadora — propuesta SHADOW

Generado: 2026-06-21T08:53:46

**Artefacto shadow.** No toca publicación oficial. El motor sigue sin calibrar (o con el calibrador global válido si lo hubiera). Una propuesta solo se acepta si Platt es monótono (A<0) **y** mejora el Brier en validación cruzada leave-one-out. No reintroduce EV/cuotas.

- Muestra mínima por mercado: **20**
- Mercados con propuesta válida: **0**

## Por mercado

| Mercado | N | Acierto | Prob. media | Gap | A | B | Brier CV antes→después | Estado |
|---|---:|---:|---:|---:|---:|---:|---|---|
| winner | 39 | 64.1% | 64.8% | -0.7% | -4.077565 | 2.049185 | 0.2215 → 0.2408 | rejected_no_cv_improvement |
| double_chance | 30 | 56.7% | 78.7% | -22.0% | — | — | in-sample 0.2715 | disabled_market |
| over_1_5 | 27 | 81.5% | 78.5% | +3.0% | 1.134226 | -2.319393 | 0.1583 → 0.1641 | rejected_non_monotonic |
| draw_no_bet | 20 | 55.0% | 71.2% | -16.2% | — | — | in-sample 0.2678 | disabled_market |
| over_2_5 | 8 | 62.5% | 62.1% | +0.4% | — | — | in-sample 0.1558 | disabled_market |
| corners | 6 | 0% | 77.2% | -77.2% | — | — | in-sample 0.5969 | disabled_market |

## Estados

- `proposed`: Platt válido (A<0) y mejora Brier CV. Candidato a shadow.
- `rejected_non_monotonic`: A≥0, no se acepta (mismo guard que producción).
- `rejected_no_cv_improvement`: no mejora fuera de muestra; sería mejora ficticia.
- `insufficient_sample`: n < mínimo; se mantiene fallback SIN calibrar.
- `disabled_market`: mercado fuera de picks oficiales; diagnóstico, sin propuesta.

## Reglas mantenidas

- Corners, Over 2.5, DNB y doble oportunidad siguen deshabilitados como picks oficiales, con o sin calibración.
- Ningún calibrador se activa en producción desde aquí. Para activar uno habría que: (1) entrenar con más muestra del modelo actual, (2) confirmar A<0, (3) confirmar mejora en validación cruzada, (4) correr en shadow.
- Mientras no haya propuesta válida, el motor publica SIN calibrar.
