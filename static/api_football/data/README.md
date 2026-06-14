# API-Football — datos en paralelo

Esta carpeta almacena la salida de `scrapers/api_football/collect_daily.py`,
ejecutado **bajo demanda** (no desde el cron todavía).

## Formato

Un archivo por día: `YYYY-MM-DD.json` (lista de objetos, uno por partido).

Cada objeto:

```
{
  "key":        "Home|Away|YYYY-MM-DD",   // misma clave que static/odds.json
  "home":       "Boca Juniors",
  "away":       "River Plate",
  "league":     "Liga Argentina",
  "date":       "2026-05-12",
  "home_id":    451,                      // team_id en API-Football
  "away_id":    435,
  "league_id":  128,
  "season":     2026,
  "h2h":        [...],                    // /fixtures/headtohead?last=10
  "home_form":  [...],                    // /fixtures?team=...&last=5
  "away_form":  [...],
  "home_stats": {...},                    // /teams/statistics
  "away_stats": {...},
  "home_danger": {...},                    // tiros a puerta + córners equipo
  "away_danger": {...},
  "home_player_shots": {...},              // /fixtures/players: tiros jugador
  "away_player_shots": {...},
  "errors":     ["h2h: timeout", ...]     // endpoints que fallaron
}
```

## Uso

Estos archivos son **insumo** para el motor (`generate_predictions.py`):

- `home_danger` / `away_danger`: habilitan líneas de córners y tiros a puerta
  de equipo cuando hay muestra suficiente.
- `home_player_shots` / `away_player_shots`: habilitan props de jugador
  (`Over X tiros`, `Over X tiros a puerta`) solo si API-Football entrega
  `/fixtures/players` para la competición/plan.

Si una API no entrega cierto bloque, el campo queda `null` o vacío y el motor
no inventa picks para ese mercado.

## Refrescar mapeos

Si aparece un equipo nuevo en `static/odds.json` que no está en
`teams_map.json`, correr:

```
python scrapers/api_football/mapping.py
```

Esto regenera `leagues_map.json` y `teams_map.json` desde cero.
