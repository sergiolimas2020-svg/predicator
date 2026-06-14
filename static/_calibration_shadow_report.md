# Calibración conservadora — propuesta SHADOW

Generado: 2026-06-14T19:17:31

**Artefacto shadow.** No toca publicación oficial. El motor sigue sin calibrar (o con el calibrador global válido si lo hubiera). Una propuesta solo se acepta si Platt es monótono (A<0) **y** mejora el Brier en validación cruzada leave-one-out. No reintroduce EV/cuotas.

- Muestra mínima por mercado: **20**
- Mercados con propuesta válida: **0**

## Por mercado

| Mercado | N | Acierto | Prob. media | Gap | A | B | Brier CV antes→después | Estado |
|---|---:|---:|---:|---:|---:|---:|---|---|
| winner | 34 | 61.8% | 64.1% | -2.3% | -4.10616 | 2.14238 | 0.2273 → 0.2491 | rejected_no_cv_improvement |
| double_chance | 28 | 53.6% | 78.1% | -24.5% | — | — | in-sample 0.2898 | disabled_market |
| over_1_5 | 20 | 85.0% | 77.1% | +7.9% | -1.233921 | -0.673694 | in-sample 0.1339 | cv_unavailable |
| draw_no_bet | 18 | 50.0% | 70.4% | -20.4% | — | — | in-sample 0.2925 | disabled_market |
| corners | 6 | 0% | 77.2% | -77.2% | — | — | in-sample 0.5969 | disabled_market |
| over_2_5 | 5 | 40.0% | 50.5% | -10.5% | — | — | in-sample 0.2231 | disabled_market |

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
