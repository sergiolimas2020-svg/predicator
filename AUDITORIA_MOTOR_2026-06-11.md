# Auditoria del motor PREDIKTOR — 2026-06-11

## Resumen ejecutivo

El motor actual no esta realmente calibrado en produccion. El repo contiene
`USE_CALIBRATION = True`, pero el calibrador guardado en
`static/calibrator.json` tiene `A=0.027241`, lo que hace que Platt sea no
monotonico para la formula usada (`P = 1 / (1 + exp(A*f+B))`). El ultimo commit
local (`1304020 Fix calibrator guard and DNB probabilities`) lo marca como
invalido y el loader del motor lo desactiva.

Lectura: hoy el motor debe tratarse como **sin calibracion activa**. Cualquier
reporte que mostrara Kelly calibrado con ROI cercano a cero estaba usando un
calibrador que produccion no deberia aceptar.

## Lo que trajo Claude Code / estado recibido

- Branch actual: `codex/fix-calibrator-dnb-teaser`.
- Ultimo commit local: `1304020 Fix calibrator guard and DNB probabilities`.
- Cambios principales de ese commit:
  - Rechaza calibradores Platt con `A >= 0`.
  - Marca `static/calibrator.json` como `valid: false`.
  - Corrige DNB para condicionar sobre resultados no empate:
    `win / (win + lose)`.
  - Agrega tests de calibrador y DNB.
  - Cambia el teaser de paywall de "Cuota" a "Confianza".

## Hallazgos criticos

1. `daily_picks.json` local esta en `2026-06-02`, no en `2026-06-11`.
   Si esto refleja produccion, el pipeline diario esta detenido o no se ha
   sincronizado el repo local con los ultimos commits.

2. El calibrador Platt entrenado sobre el log actual queda rechazado:
   `A=0.027241`, `B=0.005336`, `n=81`, `valid=false`.
   Esto significa que la muestra no sostiene que mayor probabilidad del motor
   implique mayor tasa real de acierto.

3. El backtest historico sigue mal:
   - 62 picks cuantificables.
   - Hit rate: 29/62 = 46.8%.
   - ROI apuesta plana: -14.94%.
   - Brier del modelo viejo: 0.3059.
   - Ultimos 30 dias desde 2026-05-12: 13 picks, 3/13 = 23.1%,
     ROI -54.42%.

4. Por liga, el edge aparece concentrado y fragil:
   - NBA: n=9, hit 77.8%, ROI +59.7%.
   - Serie A: n=10, hit 70.0%, ROI +22.1%.
   - Copa Sudamericana / Libertadores positivas, pero con n muy bajo.
   - La Liga, Premier, Super Lig, Bundesliga, Ligue 1 y Liga Argentina son
     negativas en el log resuelto.

5. El backtest de Poisson + Elo no valida nada aun:
   `static/_backtest_poisson_report.md` reporta 0 partidos evaluados.
   Ese reporte no puede usarse como evidencia de mejora.

## Cambio aplicado en esta auditoria

Se corrigio `scripts/backtest_log_real.py` para que solo use un calibrador que
produccion aceptaria. Si el calibrador es invalido, las columnas calibradas se
muestran equivalentes a Raw y el reporte avisa explicitamente que no hay Platt
valido. Esto evita una mejora ficticia en los reportes.

## Recomendacion de calibracion

No activar ningun Platt con `A >= 0`. La ruta segura es:

1. Mantener el guard de calibrador invalido.
2. Correr el motor en shadow hasta acumular datos limpios del modelo actual,
   no del modelo viejo.
3. No confiar en el historico mezclado para calibrar publicacion.
4. Mientras no haya calibrador valido, restringir picks oficiales a ligas con
   evidencia positiva y bajar exposicion/stake real.
5. Revisar por separado los picks de confianza sin cuota (`reason=confianza`),
   porque no son value bets aunque puedan servir como contenido.

## Validacion local

Comando ejecutado con `.venv`:

```bash
.venv/bin/python -m pytest tests/test_calibration.py tests/test_recent_form_filter.py tests/test_danger_signals.py tests/test_api_football.py tests/test_consistency.py -q
```

Resultado: `96 passed, 1 warning`.

