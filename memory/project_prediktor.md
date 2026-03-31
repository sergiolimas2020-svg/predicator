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
- `static/predictions/index.html` — Índice de predicciones del día (se regenera con script)

## Problemas resueltos en esta sesión (2026-03-30)
- `var(--gold)` no existía en index.html → cambiado a `var(--dorado)`
- Pantalla negra al entrar a historial por URL — resuelto con CSS síncrono + data-skip-entry
- Pick del día mostraba "No hay picks" por diferencia UTC vs hora Colombia → usar fecha local del navegador
- Índice de predicciones mostraba slugs en vez de nombres → reconstruir desde predictions_log.json
- Predicción Llaneros vs Once Caldas: el log la registraba como ❌ pero con nueva lógica Over 1.5 fue ✅

## Cómo regenerar el índice manualmente
```bash
python3 - << 'EOF'
import json, re
from pathlib import Path
# (ver sesión 2026-03-30 para script completo)
EOF
```

## Deploy
- Push a main → Vercel redespliega automáticamente (~1 min)
- Siempre hacer Cmd+Shift+R tras deploy para limpiar caché
