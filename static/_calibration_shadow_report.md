# Calibración conservadora — propuesta SHADOW

Generado: 2026-08-09T05:41:07

**Artefacto shadow.** No toca publicación oficial. El motor sigue sin calibrar (o con el calibrador global válido si lo hubiera). Una propuesta solo se acepta si Platt es monótono (A<0) **y** mejora el Brier en validación cruzada leave-one-out. No reintroduce EV/cuotas.

- Muestra mínima por mercado: **20**
- Mercados con propuesta válida: **0**

## Por mercado

| Mercado | N | Acierto | Prob. media | Gap | A | B | Brier CV antes→después | Estado |
|---|---:|---:|---:|---:|---:|---:|---|---|
| winner | 42 | 64.3% | 64.5% | -0.2% | -5.12741 | 2.69662 | 0.2174 → 0.2343 | rejected_no_cv_improvement |
| over_1_5 | 40 | 80.0% | 79.6% | +0.4% | 1.460224 | -2.523876 | 0.1671 → 0.1689 | rejected_non_monotonic |
| double_chance | 30 | 56.7% | 78.7% | -22.0% | — | — | in-sample 0.2715 | disabled_market |
| draw_no_bet | 27 | 63.0% | 72.3% | -9.3% | — | — | in-sample 0.234 | disabled_market |
| over_2_5 | 20 | 65.0% | 70.3% | -5.3% | — | — | in-sample 0.1736 | disabled_market |
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
