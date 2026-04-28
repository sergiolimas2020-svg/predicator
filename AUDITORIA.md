# AUDITORÍA TÉCNICA — PREDIKTOR

**Fecha de auditoría:** 2026-04-28
**Alcance:** scrapers, motor de predicciones, JSON outputs, frontend, value-bets, workflows, métricas de salud
**Objetivo:** diagnóstico completo del por qué la página queda sin picks muchos días

---

## 🚨 HALLAZGOS URGENTES

### 1. EL JSON DE PRODUCCIÓN ESTÁ DESACTUALIZADO 4 DÍAS

`static/predictions/daily_picks.json` tiene fecha `2026-04-24`. Hoy es `2026-04-28`. **El motor lleva 4 días sin generar contenido nuevo.**

### 2. WORKFLOW AUTOMÁTICO ROTO POR DEPENDENCIAS FALTANTES

`scripts/daily_update.log` muestra fallos consecutivos:

```
ModuleNotFoundError: No module named 'requests'
ModuleNotFoundError: No module named 'nba_api'
```

**TODOS los scrapers locales están fallando** porque el entorno Python no tiene `requests` instalado. El workflow tiene `continue-on-error: true` en cada step → falla silenciosamente sin alertar.

### 3. NBA NO SE ACTUALIZA HACE 11 DÍAS

`static/nba_stats.json` última modificación: `2026-04-17`. Sin stats NBA frescas, el motor no puede generar picks NBA con confianza.

### 4. STATS DE TURKEY DE HACE 29 DÍAS

`static/turkey_stats.json` no se modifica desde `2026-03-30`. Súper Lig genera picks con datos viejos hace casi un mes.

### 5. CHAMPIONS LEAGUE — ARCHIVO HUÉRFANO

Existen 2 archivos:
- `static/uefa-champions-league_stats.json` (10 KB, actualizado) ✅
- `static/uefa champions league_stats.json` (271 bytes, vacío, hace 1 mes) ❌

El segundo (con espacios) probablemente confunde al motor en algún path.

---

## 1. SCRAPERS

### 1.1 Scrapers activos (workflow diario)

| Scraper | Output | Última modificación | Estado |
|---|---|---|---|
| `colombia.py` | `colombia_stats.json` | 2026-04-24 | ⚠️ Falló localmente 28-abr |
| `argentina.py` | `argentina_stats.json` | 2026-04-24 | ⚠️ Falló localmente 28-abr |
| `premier.py` | `england_stats.json` | 2026-04-24 | ⚠️ Falló localmente 28-abr |
| `españa.py` | `spain_stats.json` | 2026-04-24 | ⚠️ Falló localmente 28-abr |
| `italia.py` | `italy_stats.json` | 2026-04-24 | ⚠️ Falló localmente 28-abr |
| `bundesliga.py` | `germany_stats.json` | 2026-04-24 | ⚠️ Falló localmente 28-abr |
| `francia.py` | `france_stats.json` | 2026-04-24 | ⚠️ Falló localmente 28-abr |
| `brazil.py` | `brazil_stats.json` | 2026-04-24 | ⚠️ Falló localmente 28-abr |
| `champions.py` | `uefa-champions-league_stats.json` | 2026-04-24 | ⚠️ Falló localmente 28-abr |
| `nba_scraper.py` | `nba_stats.json` | **2026-04-17** | 🚨 **11 días sin actualizar** |
| `fetch_odds.py` | `odds.json` | 2026-04-28 (reciente) | ✅ Funcionando |
| `update_results.py` | actualiza `predictions_log.json` | — | ⚠️ Falló localmente 28-abr |
| `stats_tracker.py` | `stats.json` | — | ⚠️ Falla silenciosa probable |

### 1.2 Scrapers obsoletos / experimentales (no usar)

40 archivos `.py` en `scrapers/`. Solo ~13 son activos. Los siguientes son legacy o experimentales:

- `colombia_fix_final.py`, `colombia_correccion_final.py`, `colombia_fixed.py`, `colombia_real_scraper.py`
- `fix_colombia.py`, `fix_colombia_complete.py`
- `update_colombia_*.py`, `update_footystats.py`
- `flashscore_scraper.py`, `flashscore_direct.py`, `inspect_espn.py`
- `advanced_scraper.py`, `universal_scraper.py`, `scraper_lite.py`, `multi_source_scraper.py`
- `generate_predictions_v2.py`, `generate_predictions_v3.py` ← **versiones viejas del motor**
- `auto_scraper.py` (vacío)
- `test_flashscore.py`, `test_dimayor.py`, `test_*.py`

**Recomendación:** mover a `scrapers/legacy/` o eliminar.

### 1.3 Patrones de fallo silencioso

**Capa workflow (CI):**
- Todos los steps usan `continue-on-error: true`
- Cuando un scraper falla, NO se notifica
- El siguiente step recibe datos viejos sin saberlo

**Capa scraper:**
- `fetch_odds.py:57-60` — captura toda excepción y retorna `[]`. Si la API key se agota, el motor recibe 0 partidos sin alerta.
- `colombia.py` (y similares) — `try/except` en cada bloque, logs warnings, continúa con datos parciales.

---

## 2. GENERATE_PREDICTIONS.PY

### 2.1 Constantes de filtros activas

**Filtros principales:**

```python
# Pre-filtro de candidatura
MIN_CONF_SUBSCRIPTION = 40.0  # prob mínima 3-way para entrar al pipeline

# Perfil PREMIUM (Pick del Día)
FILTERS_PREMIUM = {
    "MIN_PROB":              70.0,
    "MIN_EV":                15.0,
    "MAX_EV_H2H":            20.0,
    "MAX_EV_GOALS":          35.0,
    "MIN_CONF_FACTOR":        0.95,
    "MIN_VS":                 0.15,
    "REQUIRE_BOTH_TEAMS_STATS": True,
}

# Perfil SUBSCRIPTION (picks pagos)
FILTERS_SUBSCRIPTION = {
    "MIN_PROB":              50.0,
    "MIN_EV":                 8.0,
    "MAX_EV_H2H":            30.0,
    "MAX_EV_GOALS":          50.0,
    "MIN_CONF_FACTOR":        0.90,
    "MIN_VS":                 0.04,
    "REQUIRE_BOTH_TEAMS_STATS": False,
}

# EXPLORATORIO (fallback)
EXPLORATORY_MIN_PROB = 48.0
EXPLORATORY_MIN_EV   =  5.0

# ANÁLISIS DE GOLES (informativo, no es pick)
GOALS_ANALYSIS_MIN_PROB = 50.0
GOALS_ANALYSIS_MIN_EV   =  8.0
```

**Cuotas mínimas por mercado:**
```
MIN_CUOTA_WIN     = 1.60
MIN_CUOTA_DNB     = 1.30
MIN_CUOTA_DC      = 1.20
MIN_CUOTA_OVER25  = 1.60
MIN_CUOTA_OVER15  = 1.40
```

**Bounds del modelo:**
```
MODEL_MIN_PROB = 15.0
MODEL_MAX_PROB = 85.0
NBA_MIN_PROB   = 15.0
NBA_MAX_PROB   = 85.0
MODEL_DRAW_DIFF = 10.0
```

### 2.2 Comportamiento cuando NO hay picks que pasen filtros

**Salida JSON** (líneas 2587-2627):
```json
{
  "date": "2026-04-XX",
  "pick_dia": null,
  "picks_suscripcion": [],
  "pick_gratuito": null,
  "pick_exploratorio": null,
  "analisis_goles": []
}
```

**No se levanta excepción.** El JSON se escribe normalmente. El motor termina con `0 predicciones generadas!` en stdout.

### 2.3 Lógica de probabilidad — comparación con frontend

**`prob_futbol()` (Python) vs `predictWinner()` (calculator.js):**

| Componente | Python | JS | ¿1:1? |
|---|---|---|---|
| Peso posición | `0.40 × 5` | `0.4 × 5` | ✅ |
| Peso win rate | `0.30` | `0.3` | ✅ |
| Peso gol diff | `0.20` | `0.2` | ✅ |
| Home advantage | `+10%` del h_score | `+10%` del homeScore | ✅ |
| Cap de probabilidad | `[15%, 85%]` hard cap | **sin cap** | ❌ **DIFIERE** |
| Empate cuando diff < 10% | retorna `(50, 50)` | retorna `33%` empate | ❌ **DIFIERE** |

**Conclusión:** No son 1:1. La web puede mostrar predicciones distintas a las que genera el motor.

### 2.4 Puntos de falla silenciosa identificados

| Línea | Función | Issue |
|---|---|---|
| 772 | `parse_pct()` | `except: return 0.0` — devuelve 0 en cualquier error |
| 1213 | `article()` | `except:` sin mensaje |
| 2653 | log final | `except: pass` al parsear HTML |

---

## 3. JSON OUTPUTS

### 3.1 Histórico de generación (predictions_log.json)

| Día | Picks publicados |
|---|---|
| 2026-03-31 | 3 |
| 2026-04-01 | 5 |
| 2026-04-02 | 4 |
| 2026-04-03 | 4 |
| 2026-04-04 | 2 |
| 2026-04-05 | 4 |
| 2026-04-06 | 2 |
| 2026-04-07 | 1 |
| 2026-04-08 | 1 |
| 2026-04-09 | **0** ❌ |
| 2026-04-10 | **0** ❌ |
| 2026-04-11 | 4 |
| 2026-04-12 | 3 |
| 2026-04-13 | **0** ❌ |
| 2026-04-14 | **0** ❌ |
| 2026-04-15 | **0** ❌ |
| 2026-04-16 | **0** ❌ |
| 2026-04-17 | 1 |
| 2026-04-18 | 5 |
| 2026-04-19 | **0** ❌ |
| 2026-04-20 | **0** ❌ (en log) — pero hubo picks ese día |
| 2026-04-21 | **0** ❌ |
| 2026-04-22 | **0** ❌ |
| 2026-04-23 | **0** ❌ |
| 2026-04-24 | 1 |
| 2026-04-25 | **0** ❌ |
| 2026-04-26 | **0** ❌ |
| 2026-04-27 | **0** ❌ |
| 2026-04-28 | **0** ❌ |

### 3.2 Estructura actual del daily_picks.json

```json
{
  "date": "YYYY-MM-DD",
  "pick_dia":           {…} | null,
  "picks_suscripcion": [{…}],
  "pick_gratuito":      {…} | null,
  "pick_exploratorio":  {…} | null,
  "analisis_goles":    [{…}]
}
```

Cada `pick` tiene: `slug`, `matchup`, `league`, `tipo`, `market`, `prob_adjusted`, `value_score`, `confidence_factor`, `ev_adjusted`, `bk_odds`.

---

## 4. FRONTEND

### 4.1 index.html — comportamiento sin picks

`js/paywall.js:21-51` (`initPaywall`):

1. Carga `static/predictions/daily_picks.json`
2. Detecta si NO hay ningún pick → carga `daily_content.json`
3. Llama `renderPaywall(data)`

`renderPaywall()` líneas 132-138:
```js
if (!pick_gratuito && (!picks_suscripcion || picks_suscripcion.length === 0) && !pick_dia) {
  html = renderMinimalContent(data._minimal_content, dateStr);
}
```

`renderMinimalContent()` (fallback final):
- Si existe `daily_content.json`: renderiza contenido tipo A/B/C
- Si no: muestra `"Hoy el motor no encontró picks con valor suficiente. No forzamos apuestas — a veces el mejor pick es no apostar."`

### 4.2 Manejo de errores

✅ Página NUNCA queda en blanco
✅ Fetch errors capturados (`try/catch`)
⚠️ `daily_content.json` solo se genera cuando bot detecta estado NO_VALUE — si motor no corre, no existe

---

## 5. VALUE-BETS.HTML

**No existe un archivo `value-bets.html`.** El proyecto NO tiene un módulo separado de value bets.

**APIs de odds en uso:**
- ✅ The Odds API (`api.the-odds-api.com/v4/sports`) — única fuente de cuotas
- ❌ No hay `odds-api.io` configurada

**Estado de The Odds API actualmente:**
- Última actualización exitosa de `odds.json`: hoy (28-abril)
- 183 partidos cacheados
- Funcional ✅

---

## 6. MÉTRICAS DE SALUD DEL MOTOR

### 6.1 Cobertura últimos 30 días (30-marzo a 28-abril)

| Métrica | Valor |
|---|---|
| Días con picks publicados | 14 / 30 |
| **% de días con contenido** | **47%** |
| Días sin picks consecutivos máx. | **5 días** (13-17 abril, 25-28 abril) |
| Promedio de picks/día (días con picks) | 2.8 |
| Promedio de picks/día (todos los días) | 1.3 |

### 6.2 Cobertura últimos 14 días (15 - 28 abril)

| Métrica | Valor |
|---|---|
| Días con picks | 3 / 14 |
| **% de días con contenido** | **21%** ⚠️ |
| Días en blanco | 11 |

### 6.3 Patrones de fallo identificados

1. **Días entre semana con calendario corto**: Lunes/martes/miércoles sin partidos top 5 europeos → 0 picks
2. **Después de fallos del workflow**: cuando un día falla, los días siguientes pueden tener stats viejas y no generar
3. **Liga Colombiana**: nunca aparece en picks de valor (no tiene odds en The Odds API)
4. **CONMEBOL**: pocos picks por falta de stats bilaterales

### 6.4 Distribución por liga (histórico)

| Liga | Picks históricos |
|---|---|
| NBA | 13 (36%) |
| Liga Colombiana | 8 (22%) — solo modo estadístico |
| Brasileirao | 7 (19%) |
| Liga Argentina | 2 (6%) |
| Serie A | 2 (6%) |
| La Liga | 2 (6%) |
| Super Lig | 1 (3%) |
| Bundesliga | 1 (3%) |

---

## 7. WORKFLOWS DE GITHUB ACTIONS

### 7.1 Workflow único activo

**Archivo:** `.github/workflows/prediktor-daily.yml`
**Cron:** `0 5 * * *` = 00:00 hora Colombia

### 7.2 Steps y su robustez

| # | Step | continue-on-error | Estado |
|---|---|---|---|
| 1 | Registrar resultados | ✅ TRUE | Falla silenciosa posible |
| 2 | Fetch cuotas bookmakers | ✅ TRUE | Falla silenciosa posible |
| 3 | Stats Tracker | ✅ TRUE | Falla silenciosa posible |
| 4-13 | Stats por liga (10 ligas) | ✅ TRUE (todas) | Falla silenciosa posible |
| 14 | Generar predicciones | ✅ TRUE | **Crítico** — si falla, daily_picks no se actualiza |
| 15 | Publicar Telegram | ✅ TRUE | Falla silenciosa posible |
| 16 | Commit y push | ❌ FALSE | Sí falla, alerta |

### 7.3 Frecuencia y ratio de éxito

**Commits automáticos diarios encontrados:**
- 12-abr: `chore: update diario 2026-04-12` ✅
- 13-16 abr: `chore: update diario 2026-04-XX` ✅ (4 días)
- 17-19 abr: `chore: update diario` ✅ (3 días)
- 20-23 abr: `chore: update diario` ✅ (4 días)
- 24-abr: `chore: update diario` ✅
- **25-28 abr: NO HAY COMMITS DIARIOS** 🚨

**Conclusión:** El workflow lleva 4 días sin correr o sin generar commit. Necesita revisión inmediata en GitHub Actions.

---

## CONCLUSIONES ACCIONABLES

### Inmediato (próximas 24h)

1. **Revisar logs del workflow en GitHub Actions** — confirmar si está corriendo y por qué no commitea
2. **Verificar el secret `ODDS_API_KEY`** — si está vencido, el workflow no puede traer odds
3. **Regenerar picks de hoy localmente** — para destrabar la web mientras se diagnostica el workflow
4. **Eliminar archivo huérfano** `static/uefa champions league_stats.json` (con espacios)

### Corto plazo (próxima semana)

5. **Limpiar scrapers/ folder** — mover los 25+ scrapers obsoletos a `scrapers/legacy/`
6. **Reactivar nba_scraper.py** — instalar `nba_api` correctamente o cambiar fuente
7. **Reactivar Turkey scraper** — 29 días sin update
8. **Sincronizar `calculator.js` con `prob_futbol()`** — eliminar divergencia en el manejo de empate y caps

### Mediano plazo (cambios de producto)

9. **Añadir alerting** cuando el workflow falla — reemplazar `continue-on-error: true` por notificación
10. **Logear razones de rechazo** cada día — saber por qué no hubo picks (filtros, sin odds, sin stats)
11. **Considerar bajar `MIN_EV` de suscripción** de 8% a 5-6% — el cuello de botella histórico
12. **Considerar un modo "informativo"** — días sin picks de valor podrían publicar análisis textual igualmente

### Decisión estratégica de producto

13. **El motor está optimizado para "tener razón estadística", no para "generar contenido diario"**. Con 47% de cobertura mensual y 21% en últimos 14 días, **es comercialmente inviable como producto de suscripción** en su forma actual.

14. **Los días sin valor no deberían quedar en blanco** — el sistema necesita una capa de contenido garantizado (que ya empezamos a construir con el `content_generator`, pero falla porque depende del motor que no corre).

15. **Single point of failure**: todo depende del workflow diario. Si falla, todo el producto se cae. Necesita redundancia.

---

## ANEXO — Archivos clave para revisión

| Archivo | Propósito |
|---|---|
| `scrapers/generate_predictions.py` | Motor principal (2698 líneas) |
| `scrapers/fetch_odds.py` | Cliente The Odds API |
| `bot/telegram_bot.py` | Bot con 4 estados |
| `bot/content_generator.py` | Contenido mínimo diario |
| `js/paywall.js` | Renderer frontend |
| `js/calculator.js` | Probabilidades en frontend (DIVERGE del Python) |
| `static/predictions/daily_picks.json` | Output principal |
| `static/odds.json` | Cuotas bookmakers |
| `.github/workflows/prediktor-daily.yml` | Workflow CI |
| `scripts/daily_update.log` | Log local de ejecuciones |

---

*Auditoría completada el 2026-04-28. Sin cambios al código realizados durante esta auditoría — solo documentación.*
