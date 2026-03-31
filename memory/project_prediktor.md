---
name: Estado del proyecto PREDIKTOR
description: Arquitectura, archivos clave, problemas resueltos y estado actual del sitio
type: project
---

## Archivos clave
- `index.html` — Landing page principal con historial preview y pick del día
- `app.html` — App interactiva (fútbol colombiano, NBA, historial)
- `scrapers/generate_predictions.py` — Script que genera predicciones diarias
- `static/predictions_log.json` — Log de todas las predicciones con resultado y acierto
- `static/historial.json` — Resumen para mostrar en el historial (total, aciertos, %)
- `static/colombia_stats.json` — Estadísticas equipos Liga Colombiana (posición, goles, over stats)
- `static/nba_stats.json` — Estadísticas equipos NBA (wins, losses, avg_points, etc.)
- `static/argentina_stats.json` — Estadísticas equipos Liga Argentina
- `static/predictions/index.html` — Índice de predicciones del día (se regenera con script)

## Scrapers disponibles
- `scrapers/colombia.py` — Liga Colombiana (soccerstats.com)
- `scrapers/argentina.py` — Liga Argentina (soccerstats.com)
- `scrapers/premier.py`, `españa.py`, `italia.py`, `bundesliga.py`, `francia.py` — Ligas europeas
- `scrapers/brazil.py`, `champions.py` — Brasil y Champions League
- `scrapers/nba_scraper.py` — NBA via nba_api (oficial, lento por sleeps entre requests)
- Todos los scrapers de fútbol usan soccerstats.com y ESPN para fixtures

## Cómo correr scrapers
```bash
python3 scrapers/colombia.py       # actualiza colombia_stats.json
python3 scrapers/argentina.py      # actualiza argentina_stats.json
python3 scrapers/nba_scraper.py    # actualiza nba_stats.json (tarda ~2 min)
python3 scrapers/generate_predictions.py  # genera predicciones del día
```

## Lógica de predicciones (generate_predictions.py)
- **NBA fixtures**: vía ESPN (sin API key requerida)
- **Fútbol fixtures**: vía ESPN
- **Filtro de valor**: solo publica picks con cuota justa entre 1.40-2.00
  - <1.40 (>71% prob): favorito aplastante, bookmakers pagan ~1.05, descartado
  - >2.00 (<50% prob): demasiado incierto, descartado
  - Sweet spot: 1.45-1.75 (57-69%)
- **Máximo 4 picks por día**, ordenados por value_score
- Picks con score=0 no se publican aunque no haya otros

## Estructura análisis en cada predicción
1. Intro con contexto del partido y ligas
2. Análisis local: victorias, derrotas, promedios reales de goles/puntos
3. Análisis visitante: igual
4. Conclusión: texto específico con números reales (victorias, goles prom, probabilidad)
5. Sección "¿Por qué hay valor aquí?" con probabilidad, cuota mínima y nivel ALTO/MEDIO
6. Caja pick final
7. Sección de goles (solo fútbol)

## Problemas resueltos (sesión 2026-03-30 y 2026-03-31)
- `var(--gold)` no existía → cambiado a `var(--dorado)`
- Pantalla negra al entrar a historial por URL → CSS síncrono + data-skip-entry
- Pick del día UTC vs Colombia → usar fecha local del navegador
- Índice de predicciones mostraba slugs → reconstruir desde predictions_log.json
- NBA avg_points = 0 → _avg() descartaba valores >10, corregido
- Colombia stats tenían position:{} vacío → correr colombia.py regularmente
- Goles en contra mostraba total en vez de promedio → avg_g(contra=True) divide por partidos
- NBA fixtures requería API key → ahora usa ESPN directamente
- Análisis genérico → textos concretos con datos reales de cada equipo
- Charlotte Hornets 79.9% aparecía como pick → filtro cuota justa <1.40 la descarta

## Deploy
- Push a main → Vercel redespliega automáticamente (~1 min)
- Siempre hacer Cmd+Shift+R tras deploy para limpiar caché

## Historial acumulado (2026-03-30)
- 11 predicciones: 10 aciertos, 1 fallo (Hawks ganaron, predicción era Celtics)
- Porcentaje: 91%
