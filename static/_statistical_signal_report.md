# Auditoría estadística del motor

Generado: 2026-06-29T09:21:50

Este reporte NO usa cuotas, EV ni ROI. Evalúa únicamente si la probabilidad del modelo se corresponde con los aciertos reales.

## Resumen

- Picks resueltos evaluables: **148**
- Acierto total: **62.8%**
- Probabilidad media publicada: **73.0%**
- Gap calibración (acierto - prob): **-10.2%**
- Brier score: **0.2361**

## Por banda de probabilidad

| Grupo | N | Acierto | Prob. media | Gap | Brier |
|---|---:|---:|---:|---:|---:|
| 40-49% | 4 | 25.0% | 47.8% | -22.8% | 0.2413 |
| 50-59% | 12 | 66.7% | 56.4% | +10.3% | 0.2273 |
| 60-69% | 39 | 59.0% | 66.0% | -7.0% | 0.2451 |
| 70-79% | 55 | 54.5% | 75.6% | -21.1% | 0.2924 |
| 80-89% | 36 | 80.6% | 84.1% | -3.5% | 0.1554 |
| 90-99% | 2 | 100% | 92.4% | +7.6% | 0.0058 |

## Por tipo de mercado

| Grupo | N | Acierto | Prob. media | Gap | Brier |
|---|---:|---:|---:|---:|---:|
| winner | 41 | 65.9% | 64.8% | +1.0% | 0.2163 |
| over_1_5 | 34 | 79.4% | 79.3% | +0.1% | 0.1707 |
| double_chance | 30 | 56.7% | 78.7% | -22.1% | 0.2715 |
| draw_no_bet | 23 | 56.5% | 72.0% | -15.5% | 0.2629 |
| over_2_5 | 14 | 64.3% | 69.4% | -5.2% | 0.1781 |
| corners | 6 | 0% | 77.2% | -77.2% | 0.5969 |

## Por liga

| Grupo | N | Acierto | Prob. media | Gap | Brier |
|---|---:|---:|---:|---:|---:|
| Mundial 2026 | 31 | 74.2% | 79.6% | -5.4% | 0.1946 |
| Brasileirao | 21 | 57.1% | 76.9% | -19.7% | 0.2718 |
| NBA | 20 | 80.0% | 64.6% | +15.4% | 0.1776 |
| La Liga | 13 | 30.8% | 69.4% | -38.6% | 0.3691 |
| Serie A | 12 | 66.7% | 70.1% | -3.4% | 0.209 |
| Liga Colombiana | 9 | 77.8% | 75.5% | +2.3% | 0.1625 |
| Premier League | 8 | 37.5% | 69.8% | -32.3% | 0.3585 |
| Super Lig | 7 | 28.6% | 71.4% | -42.8% | 0.4089 |
| Amistoso Selección | 6 | 100% | 75.0% | +25.0% | 0.0713 |
| Copa Libertadores | 6 | 66.7% | 76.6% | -9.9% | 0.2528 |
| Copa Sudamericana | 6 | 83.3% | 76.0% | +7.3% | 0.1588 |
| Liga Argentina | 4 | 50.0% | 68.0% | -18.0% | 0.1804 |
| Bundesliga | 3 | 33.3% | 62.3% | -29.0% | 0.2213 |
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
