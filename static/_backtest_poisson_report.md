# Reporte de Backtesting Científico — Poisson vs Poisson + Elo

Generado: 2026-06-02 14:21:34

Este reporte evalúa de forma retrospectiva e imparcial (Point-In-Time) la ganancia en precisión del modelo con el nuevo peso de Elo Rating.

## 1. Resumen Global Consolidador

Evaluados **0 partidos** en las ligas core de Europa y Colombia.

| Métrica | Poisson Puro (Tabla) | Poisson + Elo Rating | Ganancia Relativa |
|---|---|---|---|
| **Tasa de Acierto (Hit Rate)** | 0.0% | **0.0%** | +0.0% |
| **Brier Score** _(bajo=mejor)_ | 0.0 | **0.0** | +0.0 (calibración) |
| **ROI Apuesta Plana** | +0.0% | **+0.0%** | +0.0% |
| **ROI Quarter-Kelly** | +0.0% | **+0.0%** | +0.0% |

⚠ **VERDICTO:** El modelo de Elo y el modelo puro están parejos en esta muestra.

## 2. Desglose Detallado por Ligas


## 3. Metodología de la Simulación
- **Point-in-Time:** Se reconstruye el estado de la tabla de posiciones y el Elo Rating de forma acumulada antes de cada partido evaluado, eliminando cualquier sesgo de mirar al futuro.
- **Cuotas Dinámicas con Margen:** Las cuotas del favorito se estiman dinámicamente según su probabilidad del modelo aplicando un overround (comisión del bookmaker) del 6% (bk_odds = 0.94 / p_fav). Esto elimina cualquier edge ficticio derivado de asumir cuotas altas fijas en favoritos evidentes.
- **Muestra Balanceada:** Para evitar que una liga con muchos partidos monopolice el consolidado, se evalúa una ventana uniforme de los últimos partidos válidos de cada competición.