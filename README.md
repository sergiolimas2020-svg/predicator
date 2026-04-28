# PREDIKTOR

Motor de predicciones deportivas basado en estadísticas reales, probabilidades y valor esperado (EV). Cubre fútbol (Colombia, Argentina, Brasil, Premier, La Liga, Serie A, Bundesliga, Ligue 1, Champions) y NBA. Publica diariamente en [prediktorcol.com](https://prediktorcol.com) y en el canal de Telegram [@prediktorcol](https://t.me/prediktorcol).

**Filosofía**: integridad analítica > contenido forzado. Si no hay valor, no se publica pick. El motor es conservador por diseño.

---

## 1. Arquitectura 3-tier

PREDIKTOR genera contenido en tres niveles, cada uno con propósito distinto:

```
┌──────────────────────────────────────────────────────────────┐
│  Nivel 1 — ANÁLISIS DEL DÍA          (siempre publicado)    │
│  Todos los partidos con probabilidades 1X2 + Over/Under.    │
│  Sin filtro de EV. Garantiza contenido mínimo diario.       │
│  → static/predictions/analysis_YYYY-MM-DD.json              │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│  Nivel 2 — VALUE PICKS               (cuando EV+ existe)    │
│  Solo partidos con valor esperado positivo verificado vs    │
│  cuotas de bookmakers. Cuota mínima 1.50, máx 4 picks/día.  │
│  → static/predictions/value_picks_YYYY-MM-DD.json           │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│  Nivel 3 — FEATURED PICK             (cuando prob ≥ 55%)    │
│  1 pick destacado en mercados estables (1X2 / NBA H2H,      │
│  no Over/Under). Si NO hay candidato ≥55%, NO se publica.   │
│  → static/predictions/featured_pick_YYYY-MM-DD.json         │
└──────────────────────────────────────────────────────────────┘
```

### Reglas y umbrales

| Nivel | Filtro | Cuota mínima | Mercados | Publicación |
|-------|--------|--------------|----------|-------------|
| 1 — Análisis | Ninguno | n/a | Todos | Siempre (si hay fixtures) |
| 2 — Value Picks | EV+ verificado | 1.50 | Todos | Solo si motor detecta valor |
| 3 — Featured Pick | prob ≥ 55% | n/a | h2h estables | Solo si hay candidato |

**Por qué Featured no usa Over/Under**: los mercados de goles son menos estables y el modelo no tiene la misma confianza que en mercados 1X2. Mejor no publicar que publicar mal calibrado.

---

## 2. Setup técnico

### Requisitos

- **Python 3.11+**
- **Node.js 20+** (solo para tests de paridad Python ↔ JavaScript)
- Git
- Una cuenta de bookmaker / API de cuotas (The Odds API)

### Instalación

```bash
git clone https://github.com/sergiolimas2020-svg/predicator.git
cd predicator
pip install -r requirements.txt
pip install pytest         # solo para tests
```

`requirements.txt` tiene versiones pineadas para reproducibilidad. No actualizar sin verificar paridad.

### Variables de entorno

Ver [SECRETS.md](SECRETS.md) para el detalle completo. Las críticas:

| Variable | Para qué |
|----------|----------|
| `ODDS_API_KEY` | Fetch de cuotas de bookmakers |
| `RAPIDAPI_KEY` | Scrapers premium (fallback) |
| `TELEGRAM_BOT_TOKEN` | Publicación en canal |
| `TELEGRAM_CHANNEL_ID` | Canal público (`@prediktorcol`) |
| `TELEGRAM_ADMIN_CHAT_ID` | Alertas de fallos del workflow |

En GitHub Actions se cargan como `secrets`. En local, vía `.env` o `export`.

### Correr localmente

```bash
./scripts/run_local.sh                   # pipeline completo
./scripts/run_local.sh --skip-telegram   # no publica en canal
./scripts/run_local.sh --dry-run         # solo lista los pasos
```

El script reproduce los pasos del workflow de GitHub Actions, útil para debuggear sin esperar al cron.

### Tests

```bash
pytest tests/test_consistency.py -v             # paridad Python ↔ JS (requiere Node)
python3 tests/simulate_scenarios.py             # render de los 3 mensajes Telegram
python3 tests/simulate_scenario_detection.py    # validación de selección de escenario
```

---

## 3. Workflow y automatización

### GitHub Actions — `prediktor-daily.yml`

Se ejecuta a las **05:00 UTC** (= 00:00 hora Colombia, al cambiar de día). Pasos:

1. **Setup** — Python 3.11 + Node 20 + dependencias pineadas
2. **Verify secrets** — falla rápido si falta alguna credencial
3. **Tests de paridad Python ↔ JS** — bloqueante: si rompe la coherencia entre `prob_futbol()` y `Calculator.predictWinner()`, el workflow se detiene
4. **Update results** de ayer (no crítico)
5. **Fetch odds** de bookmakers (crítico)
6. **Scrapers por liga** (10 ligas, no críticos individualmente)
7. **Generar predicciones** — produce los 4 JSON output
8. **Validar daily_picks.json** — verifica que la fecha es la de hoy
9. **Publicar en Telegram** (no crítico — el bot tiene fallback)
10. **Commit y push** a `main`
11. **Notificar admin** del resultado (éxito o fallo)

### Tests de paridad

Los más importantes: `tests/test_consistency.py` corre 30 casos comparando los outputs de `prob_futbol()` (Python) y `Calculator.predictWinner()` (JavaScript) contra el mismo input. Tolerancia 0.1%. Si alguien edita uno y olvida el otro, el workflow alerta vía Telegram.

### Observabilidad

- **Logs del workflow**: GitHub Actions
- **Notificación de éxito**: Telegram admin con número de picks generados
- **Notificación de fallo**: Telegram admin con paso que falló + URL al run
- **Log de publicaciones**: `bot/publish_log.json` (control de duplicados por estado)

---

## 4. Estructura de outputs

```
static/predictions/
├── analysis_YYYY-MM-DD.json        # Nivel 1 — todos los partidos analizados
├── value_picks_YYYY-MM-DD.json     # Nivel 2 — solo EV+ verificado
├── featured_pick_YYYY-MM-DD.json   # Nivel 3 — pick destacado (opcional)
└── daily_picks.json                # Derivado para compat. con bot y frontend
```

`daily_picks.json` es la fuente autoritativa para la fecha (`date` field) y mantiene compatibilidad con el resto del stack (web, bot, scripts viejos). Se deriva de los otros tres.

`featured_pick_YYYY-MM-DD.json` puede no existir un día determinado — significa que ningún partido alcanzó el umbral del 55% en mercado estable. El frontend muestra estado vacío elegante; el bot publica Escenario 3.

---

## 5. Escenarios de Telegram

El bot SIEMPRE comunica algo al canal — nunca queda mudo. Tiene **4 estados de sistema** y, dentro de los estados con datos, **3 escenarios de contenido**:

### Estados del sistema

| Estado | Cuándo | Mensaje |
|--------|--------|---------|
| `SUCCESS` | JSON actual con value pick | Escenario 1 (VALUE BET) |
| `NO_VALUE` | JSON actual sin value picks | Escenario 2 o 3 (Featured / No-pick) |
| `ODDS_FAILURE` | No se pudo traer cuotas | Mensaje de fallo de odds |
| `EXECUTION_FAILURE` | Motor no corrió o JSON viejo | Mensaje de inconveniente técnico |

### Escenarios de contenido

**Escenario 1 — VALUE BET** (motor detectó EV+)
```
🎯 VALUE BET DEL DÍA
🏆 Liga: …
⚽ Partido: …
🎯 Mercado: … @cuota
📊 Probabilidad: …%
💎 Valor detectado: positivo (EV+)
🌐 Análisis completo: prediktorcol.com
```
El número exacto de EV no se publica en canal (decisión de marca: la metodología detallada vive en la web).

**Escenario 2 — FEATURED PICK estadístico** (sin EV+ pero hay candidato ≥55%)
```
📊 PICK DEL DÍA — Estadística sólida
Hoy no detectamos value bets, pero compartimos nuestro pick
con mayor confianza estadística del día.
…
Nota: este pick NO tiene EV positivo verificado vs el mercado.
Es solo señal estadística.
```
Disclaimer explícito para no diluir la marca de "value betting".

**Escenario 3 — NO-PICK** (ni value ni featured)
```
📅 PREDIKTOR — fecha
Hoy el motor no detectó partidos con confianza estadística
suficiente para publicar pick.
No forzamos picks. Mañana volvemos.
📊 Mientras tanto, podés ver el Análisis del Día: prediktorcol.com
```
Redirige tráfico al sitio web (donde está el Nivel 1 + monetización futura).

### Control de duplicados

`bot/publish_log.json` registra `last_published` (fecha) + `last_state`. Si el mismo estado ya se publicó hoy, no se reenvía. Pero si el estado cambia (ej: `EXECUTION_FAILURE` → `SUCCESS` cuando el motor se arregla), se re-publica.

---

## 6. Estructura del repositorio

```
predicator/
├── scrapers/                   # 45 scripts: scrapers por liga + motor + odds
│   ├── generate_predictions.py # Motor principal (genera los 4 JSON)
│   ├── fetch_odds.py           # The Odds API
│   ├── colombia.py / argentina.py / premier.py / …
│   └── nba_scraper.py
├── bot/
│   ├── telegram_bot.py         # Lógica de publicación (3 escenarios + 4 estados)
│   ├── content_generator.py    # Contenido mínimo cuando NO_VALUE legacy
│   ├── publish.py              # Entry point (-m bot.publish)
│   └── config.py               # Lectura de env vars
├── js/
│   ├── calculator.js           # Mirror JS de prob_futbol() (paridad estricta)
│   ├── dashboard.js            # Render Nivel 1 + Nivel 3
│   ├── paywall.js              # Render Nivel 2
│   └── ui-renderer.js / data-loader.js / main.js
├── tests/
│   ├── test_consistency.py     # Paridad Python ↔ JS
│   ├── run_calculator.js       # Wrapper Node para tests
│   ├── test_cases.json         # 10 casos (incl. edge cases)
│   ├── simulate_scenarios.py            # Render de mensajes Telegram
│   └── simulate_scenario_detection.py   # Selección de escenario
├── scripts/
│   ├── run_local.sh            # Ejecuta el pipeline completo localmente
│   ├── verify_secrets.py       # Validación pre-flight
│   └── notify_telegram.py      # Alertas a admin
├── static/predictions/         # Outputs JSON + páginas SEO de previas
├── .github/workflows/
│   └── prediktor-daily.yml     # Cron diario
├── index.html                  # Dashboard 3-tier mobile-first
├── styles.css
├── requirements.txt            # Versiones pineadas
└── SECRETS.md                  # Documentación de variables
```

---

## 7. Principios de diseño

- **No forzamos picks**: si no hay valor, no publicamos. Mejor un día callado que un pick débil.
- **Mobile-first**: la mayoría del tráfico es móvil. Touch targets ≥44px, breakpoints 768/1024.
- **Paridad estricta Python ↔ JS**: lo que calcula el motor en backend coincide con lo que muestra el frontend, dentro de tolerancia 0.1%.
- **Honestidad metodológica**: cuando publicamos un pick estadístico (Escenario 2), aclaramos que NO es value bet. La marca se construye con consistencia, no con humo.
- **Idioma**: español rioplatense / colombiano. Liga por defecto en frontend: Colombia.

---

## 8. Contribuir

Este repo es operado por [@sergiolimas2020-svg](https://github.com/sergiolimas2020-svg). Para reportar bugs o sugerir features: issues en GitHub.

**Antes de cualquier PR**: correr `pytest tests/test_consistency.py -v` localmente. Si rompe paridad, el workflow va a alertar en producción.
