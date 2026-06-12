# Handoff para Claude Code — PREDIKTOR

Fecha: 2026-06-11

## Objetivo

Calibrar PREDIKTOR como motor estadístico confiable.

Regla central: los picks oficiales deben estar basados en datos, forma reciente,
probabilidad del modelo y API-Football. No se debe inventar EV, cuotas ni valor
de mercado.

## Contrato actual del motor

- `STATISTICAL_ONLY_MODE = True`
- `REQUIRE_API_FOOTBALL_FOR_FOOTBALL_PICKS = True`
- API-Football es la fuente principal para fútbol.
- ESPN solo es fallback de calendario/cobertura.
- Odds/cuotas son opcionales y no deciden publicación.
- Sin `static/api_football/data/YYYY-MM-DD.json`, no deben publicarse picks
  oficiales de fútbol.
- NBA queda separado porque usa fuentes NBA propias.

## Cambios ya aplicados

- `scrapers/generate_predictions.py`
  - API-Football se procesa antes que ESPN.
  - ESPN solo completa partidos que API-Football no haya traído.
  - Picks oficiales de fútbol requieren respaldo API-Football.
  - Córners desactivado como pick oficial.
  - Over 2.5 desactivado como pick oficial.
  - DNB y Doble Oportunidad fuera de Featured/Pick oficial.
  - Winner/1X2 y Over 1.5 quedan como mercados estadísticos viables.

- `scripts/statistical_signal_audit.py`
  - Nuevo reporte sin EV/cuotas.
  - Mide hit rate, probabilidad media, gap de calibración y Brier.

- `scripts/pipeline_health.py`
  - Reporta estado de API-Football diaria.
  - Si falta API-Football y hay picks, debe fallar.

- `README.md`
  - Documenta API-Football como fuente principal.

## Último reporte estadístico

Archivo: `static/_statistical_signal_report.md`

Resumen:

- Picks resueltos evaluables: 109
- Acierto total: 57.8%
- Probabilidad media publicada: 71.0%
- Gap calibración: -13.2%
- Brier score: 0.2554

Lectura:

- El motor estaba sobreconfiado.
- Córners: 0/6, fuera.
- DNB y Doble Oportunidad: gap negativo alto, fuera.
- Over 1.5: 88.9%, se mantiene.
- Winner/1X2: calibración cercana, se mantiene con cautela.

## Pruebas actuales

Comando:

```bash
.venv/bin/python -m pytest -q
```

Resultado actual:

```text
104 passed, 1 warning
```

Health check:

```bash
.venv/bin/python scripts/pipeline_health.py
```

Resultado actual:

```text
status=OK
```

Advertencia esperada local:

```text
static/api_football/data/2026-06-11.json missing
```

Motivo: en este entorno local no está `API_FOOTBALL_KEY`.

## Tareas recomendadas para Claude Code

1. Revisar que ninguna ruta de publicación oficial de fútbol pueda saltarse
   `REQUIRE_API_FOOTBALL_FOR_FOOTBALL_PICKS`.

2. Revisar que `collect_daily.py` corra antes de `generate_predictions.py` en
   GitHub Actions y que `API_FOOTBALL_KEY` sea un secret real.

3. Crear backtest estadístico por mercado usando solo:
   - fecha
   - liga
   - mercado
   - probabilidad publicada
   - acierto
   - fuente de datos

4. Proponer calibración conservadora para probabilidad:
   - por mercado
   - por liga
   - por banda de probabilidad
   - sin usar EV/cuotas

5. Mantener o ampliar tests:
   - API-Football primero
   - ESPN fallback
   - sin API-Football no hay pick oficial fútbol
   - no EV/cuotas inventadas

## No hacer

- No reactivar EV como requisito.
- No usar cuotas estimadas.
- No publicar picks de fútbol sin API-Football diaria.
- No confiar en ESPN como fuente principal.
- No reactivar córners, Over 2.5, DNB o Doble Oportunidad como picks oficiales
  sin una nueva muestra estadística que lo justifique.

