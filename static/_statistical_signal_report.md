# Auditoría estadística del motor

Generado: 2026-08-08T05:35:30

Este reporte NO usa cuotas, EV ni ROI. Evalúa únicamente si la probabilidad del modelo se corresponde con los aciertos reales.

## Resumen

- Picks resueltos evaluables: **164**
- Acierto total: **64.0%**
- Probabilidad media publicada: **73.2%**
- Gap calibración (acierto - prob): **-9.1%**
- Brier score: **0.2274**

## Por banda de probabilidad

| Grupo | N | Acierto | Prob. media | Gap | Brier |
|---|---:|---:|---:|---:|---:|
| 40-49% | 4 | 25.0% | 47.8% | -22.8% | 0.2413 |
| 50-59% | 14 | 57.1% | 56.2% | +0.9% | 0.2388 |
| 60-69% | 41 | 58.5% | 65.8% | -7.3% | 0.2457 |
| 70-79% | 62 | 59.7% | 75.5% | -15.8% | 0.267 |
| 80-89% | 40 | 80.0% | 84.1% | -4.1% | 0.1587 |
| 90-99% | 3 | 100% | 93.3% | +6.7% | 0.0047 |

## Por tipo de mercado

| Grupo | N | Acierto | Prob. media | Gap | Brier |
|---|---:|---:|---:|---:|---:|
| winner | 42 | 64.3% | 64.5% | -0.2% | 0.2174 |
| over_1_5 | 39 | 79.5% | 79.6% | -0.1% | 0.1705 |
| double_chance | 30 | 56.7% | 78.7% | -22.1% | 0.2715 |
| draw_no_bet | 27 | 63.0% | 72.3% | -9.4% | 0.234 |
| over_2_5 | 20 | 65.0% | 70.3% | -5.3% | 0.1736 |
| corners | 6 | 0% | 77.2% | -77.2% | 0.5969 |

## Por liga

| Grupo | N | Acierto | Prob. media | Gap | Brier |
|---|---:|---:|---:|---:|---:|
| Mundial 2026 | 40 | 77.5% | 79.4% | -1.9% | 0.1786 |
| Brasileirao | 27 | 59.3% | 75.7% | -16.4% | 0.2478 |
| NBA | 20 | 80.0% | 64.6% | +15.4% | 0.1776 |
| La Liga | 13 | 30.8% | 69.4% | -38.6% | 0.3691 |
| Serie A | 12 | 66.7% | 70.1% | -3.4% | 0.209 |
| Liga Colombiana | 9 | 77.8% | 75.5% | +2.3% | 0.1625 |
| Premier League | 8 | 37.5% | 69.8% | -32.3% | 0.3585 |
| Copa Sudamericana | 7 | 71.4% | 72.4% | -1.0% | 0.1733 |
| Super Lig | 7 | 28.6% | 71.4% | -42.8% | 0.4089 |
| Amistoso Selección | 6 | 100% | 75.0% | +25.0% | 0.0713 |
| Copa Libertadores | 6 | 66.7% | 76.6% | -9.9% | 0.2528 |
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
