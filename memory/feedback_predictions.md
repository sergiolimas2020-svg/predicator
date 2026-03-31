---
name: Reglas de predicciones y value bets
description: Cómo generar picks — siempre basados en estadística, zona de valor real 1.40-2.00
type: feedback
---

## REGLA PRINCIPAL: Value bets, no favoritos obvios

El objetivo de PREDIKTOR es encontrar **apuestas de valor**, no predecir al favorito. Una cuota de 1.05-1.20 no tiene valor aunque sea "segura". La meta es encontrar picks donde nuestra probabilidad estadística supera la probabilidad implícita del bookmaker.

**Why:** Los Spurs al 85% pagaban 1.05 — correcto pero sin valor. Charlotte Hornets al 79.9% = cuota justa 1.25, el mercado real la pagaba 1.06. Publicar esos picks daña la credibilidad porque el apostador siente que son obvios.

**How to apply:**
- Zona de valor: cuota justa **1.40–2.00** (probabilidad 50–71%)
- Sweet spot máximo valor: cuota **1.45–1.75** (57–69%)
- Por debajo de 1.40 (>71%): descartado aunque la probabilidad sea alta
- Por encima de 2.00 (<50%): demasiado incierto, no publicar
- Máximo **4 picks por día** — mejor pocos y buenos que muchos mediocres

## REGLA: Elegir siempre el mercado de mayor probabilidad (fútbol)

Para fútbol NO predecir ganador si Over 1.5 o Over 2.5 tiene mayor probabilidad.

**Why:** Predecir ganador es ~33-50%. Over 1.5 suele ser 65-85% y es más fácil de acertar.

**How to apply:**
- Calcular Over 1.5, Over 2.5 y probabilidad de ganador
- Elegir el mercado con **mayor porcentaje** como predicción principal
- Si EMPATE y Over 1.5 > 33%, elegir Over 1.5
- Para NBA se predice ganador (no hay stats de goles)

## REGLA: Análisis concreto con datos reales

El texto de cada predicción debe usar los números reales del equipo, no frases genéricas.

**Why:** El apostador necesita entender POR QUÉ hay valor, no solo "X es favorito". La confianza se gana con datos concretos.

**How to apply:**
- Mencionar victorias, derrotas y promedios de goles/puntos reales de cada equipo
- En la sección "¿Por qué hay valor aquí?" explicar: probabilidad del modelo, cuota justa mínima, y que los mercados 60-71% son donde los bookmakers sub-valoran
- Cerrar con: "si encuentras este partido por encima de cuota X, matemáticamente hay valor"
- Última línea: recordar apostar con responsabilidad y comparar cuotas

## Estructura stats en colombia_stats.json
- `equipo.goals.over_1_5` = "69%" (% de partidos con +1.5 goles)
- `equipo.goals.over_2_5` = "23%"
- `equipo.position.ganados/empatados/perdidos/puntos` = posición en tabla
- Si `position: {}` vacío → correr `python3 scrapers/colombia.py`
