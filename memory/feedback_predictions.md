---
name: Reglas de predicciones fútbol
description: Cómo deben generarse las predicciones para fútbol — elegir mercado con mayor probabilidad
type: feedback
---

**REGLA PRINCIPAL:** Siempre elegir el mercado con mayor porcentaje de confianza disponible. Esa es la meta — maximizar el % de acierto, no predecir quién gana.

Para fútbol (especialmente Liga Colombiana), NO predecir ganador directo como predicción principal.

**Why:** Predecir ganador es ~33-50% de probabilidad. Predecir Over 1.5 goles suele ser 65-85% y es mucho más fácil de acertar. El usuario lo comprobó: América ganó pero los goles sí se dieron; Llaneros empató pero sí hubo Over 1.5.

**How to apply:**
- Calcular Over 1.5, Over 2.5, y probabilidad de ganador
- Elegir el mercado con **mayor porcentaje** como predicción principal
- Si hay empate de probabilidad entre dos equipos (diff < 10%), nunca elegir EMPATE si Over 1.5 > 33%
- La lógica ya está implementada en `scrapers/generate_predictions.py` función `article()`
- Para NBA se sigue prediciendo ganador (no hay stats de goles)

**Estructura de datos en colombia_stats.json:**
- `equipo.goals.over_1_5` = "69%" (porcentaje de partidos con +1.5 goles)
- `equipo.goals.over_2_5` = "23%"
- `equipo.position.ganados/empatados/perdidos/puntos` = posición en tabla
