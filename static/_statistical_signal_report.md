# Auditoría estadística del motor

Generado: 2026-10-19T10:24:08

Este reporte NO usa cuotas, EV ni ROI. Evalúa únicamente si la probabilidad del modelo se corresponde con los aciertos reales.

## Resumen

- Picks resueltos evaluables: **197**
- Acierto total: **65.0%**
- Probabilidad media publicada: **72.3%**
- Gap calibración (acierto - prob): **-7.4%**
- Brier score: **0.2219**

## Por banda de probabilidad

| Grupo | N | Acierto | Prob. media | Gap | Brier |
|---|---:|---:|---:|---:|---:|
| 40-49% | 4 | 25.0% | 47.8% | -22.8% | 0.2413 |
| 50-59% | 25 | 52.0% | 54.8% | -2.8% | 0.2487 |
| 60-69% | 44 | 59.1% | 66.0% | -6.9% | 0.2445 |
| 70-79% | 75 | 65.3% | 75.4% | -10.1% | 0.2392 |
| 80-89% | 46 | 78.3% | 83.8% | -5.5% | 0.1699 |
| 90-99% | 3 | 100% | 93.3% | +6.7% | 0.0047 |

## Por tipo de mercado

| Grupo | N | Acierto | Prob. media | Gap | Brier |
|---|---:|---:|---:|---:|---:|
| winner | 54 | 68.5% | 66.4% | +2.1% | 0.2033 |
| over_1_5 | 49 | 79.6% | 79.5% | +0.0% | 0.1704 |
| draw_no_bet | 37 | 59.5% | 66.9% | -7.5% | 0.2392 |
| double_chance | 30 | 56.7% | 78.7% | -22.1% | 0.2715 |
| over_2_5 | 21 | 61.9% | 69.8% | -7.9% | 0.1817 |
| corners | 6 | 0% | 77.2% | -77.2% | 0.5969 |

## Por liga

| Grupo | N | Acierto | Prob. media | Gap | Brier |
|---|---:|---:|---:|---:|---:|
| Mundial 2026 | 40 | 77.5% | 79.4% | -1.9% | 0.1786 |
| Brasileirao | 36 | 61.1% | 74.6% | -13.5% | 0.2334 |
| NBA | 31 | 80.6% | 67.7% | +12.9% | 0.1709 |
| Serie A | 21 | 61.9% | 63.2% | -1.3% | 0.2211 |
| La Liga | 13 | 30.8% | 69.4% | -38.6% | 0.3691 |
| Copa Sudamericana | 9 | 66.7% | 74.4% | -7.7% | 0.2129 |
| Liga Colombiana | 9 | 77.8% | 75.5% | +2.3% | 0.1625 |
| Premier League | 8 | 37.5% | 69.8% | -32.3% | 0.3585 |
| Super Lig | 7 | 28.6% | 71.4% | -42.8% | 0.4089 |
| Amistoso Selección | 6 | 100% | 75.0% | +25.0% | 0.0713 |
| Copa Libertadores | 6 | 66.7% | 76.6% | -9.9% | 0.2528 |
| Liga Argentina | 4 | 50.0% | 68.0% | -18.0% | 0.1804 |
| Bundesliga | 3 | 33.3% | 62.3% | -29.0% | 0.2213 |
| Champions League | 2 | 100% | 75.5% | +24.5% | 0.06 |
| Ligue 1 | 2 | 0% | 65.8% | -65.8% | 0.4341 |

## Lectura rápida

- Gap positivo: el motor fue conservador en esa muestra.
- Gap negativo: el motor sobreestimó su probabilidad.
- Brier más bajo es mejor; penaliza confianza alta cuando falla.
- Grupos con muestra pequeña no deben usarse para cambiar umbrales solos.

## Reglas operativas derivadas

- Córners queda fuera de picks oficiales hasta nueva muestra: histórico actual 0/6.
- Doble oportunidad y apuesta sin empate quedan fuera de Featured/Pick oficial: gap negativo alto.
- Over 1.5 se mantiene como mercado estadístico viable: 88.9% de acierto en la muestra actual.
- Winner/1X2 se mantiene con cautela: gap cercano a calibración neutral.
