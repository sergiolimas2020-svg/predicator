# Calibración conservadora — propuesta SHADOW

Generado: 2026-08-25T05:23:29

**Artefacto shadow.** No toca publicación oficial. El motor sigue sin calibrar (o con el calibrador global válido si lo hubiera). Una propuesta solo se acepta si Platt es monótono (A<0) **y** mejora el Brier en validación cruzada leave-one-out. No reintroduce EV/cuotas.

- Muestra mínima por mercado: **20**
- Mercados con propuesta válida: **0**

## Por mercado

| Mercado | N | Acierto | Prob. media | Gap | A | B | Brier CV antes→después | Estado |
|---|---:|---:|---:|---:|---:|---:|---|---|
| over_1_5 | 47 | 78.7% | 79.7% | -1.0% | 1.80632 | -2.730202 | 0.1751 → 0.1747 | rejected_non_monotonic |
| winner | 43 | 65.1% | 64.6% | +0.5% | -5.290916 | 2.768144 | 0.2146 → 0.2307 | rejected_no_cv_improvement |
| double_chance | 30 | 56.7% | 78.7% | -22.0% | — | — | in-sample 0.2715 | disabled_market |
| draw_no_bet | 28 | 64.3% | 71.6% | -7.3% | — | — | in-sample 0.2337 | disabled_market |
| over_2_5 | 21 | 61.9% | 69.8% | -7.9% | — | — | in-sample 0.1817 | disabled_market |
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
