# Reporte de Rendimiento Empírico Real (Historial de Producción)

Este reporte evalúa el rendimiento del modelo utilizando **únicamente los picks resueltos en vivo**, con las **cuotas reales** de cierre obtenidas de la API y los resultados verdaderos de cada partido.

### Parámetros de Calibración Platt Usados:
* **A (pendiente):** `0.027241`
* **B (sesgo):** `0.005336`
* **Muestras del Calibrador:** `81` (entrenado sobre log histórico)


## 1. Rendimiento Consolidado

| Muestra / Grupo | N | ROI Apuesta Plana | Apuestas Raw | ROI Kelly Raw | Drawdown Raw | Apuestas Cal | ROI Kelly Cal | Drawdown Cal |
|---|---|---|---|---|---|---|---|---|
| **Todos los Picks** | 62 | -14.94% | 62 | -66.69% | 71.32% | 12 | **-2.41%** | **11.49%** |
| **Picks del Día (Principal)** | 10 | -8.05% | 10 | -6.22% | 15.42% | 0 | **+0.0%** | **0.0%** |
| **Picks Extra (Adicionales)** | 11 | +5.15% | 11 | +0.42% | 7.92% | 3 | **-2.9%** | **8.8%** |


## 2. Metodología y Notas

- **Cuotas Reales:** Se toman directamente las cuotas de cierre registradas de los bookmakers (Pinnacle/Bet365) a través de The Odds API en producción. No hay cuotas sintéticas ni supuestas.
- **Criterio de Kelly (Quarter-Kelly):** Se simula un bankroll inicial de $100.0. Cada apuesta arriesga el porcentaje sugerido por la fórmula oficial multiplicada por 0.25 (Quarter-Kelly) para amortiguar el riesgo.
- **Sin Calibrar (Raw):** Usa las probabilidades originales declaradas por el motor de Poisson, propensas a la sobreconfianza.
- **Calibrado (Platt):** Aplica la calibración de Platt entrenada sobre los resultados previos para suavizar y corregir la sobreconfianza de las probabilidades antes de estimar el stake de Kelly. Como se observa en la tabla, el calibrador filtra la gran mayoría de apuestas que no tienen ventaja real, actuando como un escudo protector del bankroll.
- **Drawdown Máximo:** Mide la mayor caída porcentual del bankroll desde su pico más alto anterior, un indicador crítico del riesgo real de ruina.