# VERSION DE PRUEBA - NO PRODUCCION
from __future__ import annotations
import json, math, os, requests, unicodedata
from datetime import date, timedelta
from pathlib import Path

OUTPUT_DIR = Path("static/predictions")
OUTPUT_DIR.mkdir(exist_ok=True)
from datetime import datetime, timezone
_now_col = datetime.now(timezone.utc) - timedelta(hours=5)
today    = _now_col.strftime("%Y-%m-%d")
tomorrow = (_now_col + timedelta(days=1)).strftime("%Y-%m-%d")

MESES = {"January":"enero","February":"febrero","March":"marzo","April":"abril","May":"mayo","June":"junio","July":"julio","August":"agosto","September":"septiembre","October":"octubre","November":"noviembre","December":"diciembre"}
today_display = date.today().strftime("%d de %B de %Y")
for en, es in MESES.items():
    today_display = today_display.replace(en, es)

BALLDONTLIE_KEY = os.environ.get("BALLDONTLIE_KEY", "")
ODDS_API_KEY    = os.environ.get("ODDS_API_KEY", "")

# ── API externa (contexto, no decisor) ──
try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from data_sources.external_api import enrich_match_context, format_context_for_copy, is_api_active
    _HAS_EXTERNAL_API = True
except ImportError:
    _HAS_EXTERNAL_API = False
    def enrich_match_context(*a, **kw): return {}
    def format_context_for_copy(*a, **kw): return ""
    def is_api_active(): return False

# ── API externa NBA Games (contexto partido/equipo, no decisor) ──
try:
    from data_sources.nba_games_api import (
        enrich_nba_game_context, format_nba_game_context_for_copy, is_nba_games_api_active,
    )
    _HAS_NBA_GAMES_API = True
except ImportError:
    _HAS_NBA_GAMES_API = False
    def enrich_nba_game_context(*a, **kw): return {}
    def format_nba_game_context_for_copy(*a, **kw): return ""
    def is_nba_games_api_active(): return False

# ── API externa NBA Players (contexto props jugador, no decisor) ──
try:
    from data_sources.nba_players_api import (
        enrich_nba_player_prop, format_nba_player_context_for_copy, is_nba_players_api_active,
    )
    _HAS_NBA_PLAYERS_API = True
except ImportError:
    _HAS_NBA_PLAYERS_API = False
    def enrich_nba_player_prop(*a, **kw): return {}
    def format_nba_player_context_for_copy(*a, **kw): return ""
    def is_nba_players_api_active(): return False

# ── API externa TechCorner (contexto corners, no decisor) ──
try:
    from data_sources.techcorner_api import (
        enrich_corners_context, format_corners_context_for_copy, is_techcorner_active,
    )
    _HAS_TECHCORNER_API = True
except ImportError:
    _HAS_TECHCORNER_API = False
    def enrich_corners_context(*a, **kw): return {}
    def format_corners_context_for_copy(*a, **kw): return ""
    def is_techcorner_active(): return False

# ── API de ODDS reales de PROPS NBA (The Odds API) ──
try:
    from data_sources.nba_props_odds_api import (
        get_player_prop_odds, is_nba_props_odds_active,
    )
    _HAS_NBA_PROPS_ODDS = True
except ImportError:
    _HAS_NBA_PROPS_ODDS = False
    def get_player_prop_odds(*a, **kw): return {}
    def is_nba_props_odds_active(): return False

# ── Coincidencia difusa de nombres de equipo (corrige BUG-2) ──
# Antes, find() devolvía las stats de OTRO equipo cuando no encontraba el
# correcto. Ahora usa fuzzy matching: si nada supera el umbral, devuelve {}
# y el fixture se trata como "sin datos" (degradación segura a 50/50).
try:
    from rapidfuzz import process as _rf_process, fuzz as _rf_fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False
    from difflib import SequenceMatcher as _SeqMatcher
FUZZY_MATCH_THRESHOLD = 85  # score mínimo (0-100) para aceptar un match difuso

# ── Límite de picks diarios y umbral mínimo de confianza ──
MAX_PICKS         = 4    # cap total legacy (no usado en selección dual)
MAX_PREMIUM_PICKS = 3    # DEPRECATED — reemplazado por MAX_EXTRA_PICKS
MAX_EXTRA_PICKS   = 3    # picks extra (entretenimiento) publicados junto al pick_dia vendible
MIN_CONF          = 45.0 # prob mínima 3-way para ser candidato

# ── Pick del día VENDIBLE — reglas de negocio (capa de producto, no del modelo) ──
# Estas reglas son independientes del pipeline estadístico.
# Cambian la presentación del pick, no su cálculo.
PICK_DIA_MIN_PROB  = 65.0  # prob_adjusted mínima (%) — umbral de certeza comercial
PICK_DIA_MIN_CUOTA = 1.40  # cuota mínima bookmaker — por debajo no hay valor perceptible
PICK_DIA_MAX_CUOTA = 1.85  # cuota máxima bookmaker — por encima pierde la narrativa de certeza
PICK_DIA_MIN_EV    = 5.0   # ev_adjusted mínimo (%) — evitar picks sin ningún valor esperado

# ── Perfiles de filtros — capa de PRODUCTO (no tocan fórmulas) ────
# Cada perfil define umbrales de elegibilidad. evaluate_value() calcula
# los valores; estos diccionarios solo deciden qué se PUBLICA.

FILTERS_PREMIUM = {
    "MIN_PROB":       70.0,   # prob_adjusted mínima (%)
    "MIN_EV":         15.0,   # EV ajustado mínimo (%) — consistente con all_evals
    "MAX_EV_H2H":     20.0,   # EV máximo para h2h (%) — anti-overfit
    "MAX_EV_GOALS":   35.0,   # EV máximo para goles (%)
    "MIN_CONF_FACTOR": 0.95,  # confidence_factor mínimo
    "MIN_VS":          0.15,  # value_score mínimo
    "REQUIRE_BOTH_TEAMS_STATS": True,
}

FILTERS_SUBSCRIPTION = {
    "MIN_PROB":       50.0,   # acepta señal parcial del modelo (%)
    "MIN_EV":          8.0,   # absorbe vig Bet365/Pinnacle (~5-7%) (%)
    "MAX_EV_H2H":     30.0,   # rango 20-30% = desacuerdo leve (%)
    "MAX_EV_GOALS":   50.0,   # goles varianza alta; 50% conservador (%)
    "MIN_CONF_FACTOR": 0.90,  # permite ligas MID + mercado goles
    "MIN_VS":          0.04,  # umbral bajo; EV y prob ya filtran calidad
    "REQUIRE_BOTH_TEAMS_STATS": False,
}

# ── Reglas de selección ──
TIER_SUSCRIPCION_MIN = 2      # mínimo de picks suscripción para publicar pick_dia
TIER_SUSCRIPCION_MAX = 4      # máximo de picks suscripción

# ── Ligas CORE — núcleo del producto ──
# Usado solo por la regla de PICK EXPLORATORIO (capa de publicación).
# No afecta filtros estadísticos ni pipeline de EV.
CORE_LEAGUES = {
    "Serie A",
    "Brasileirao",
    "Liga Colombiana",
    "Liga Argentina",
    "NBA",
}

# ── Ligas EXCLUIDAS de value picks y featured pick ──
# Recalibración 23-may sobre track record acumulado (n=106 picks resueltos
# en static/predictions_log.json). El hit rate global cayó 92% (mar) → 57%
# (abr) → 31% (may) por expansión a ligas europeas grandes sin ventaja.
# Hit rate real por liga (acumulado):
#   Premier League  20%  (n=15)  ← excluida
#   La Liga         23%  (n=17)  ← excluida
#   Super Lig       22%  (n=9)   ← excluida (la rehabilitación del 11-may falló)
#   Bundesliga      33%  (n=3)   ← excluida (muestra chica + yield negativo)
#   Ligue 1          0%  (n=2)   ← excluida
# vs. las ligas con ventaja real que SÍ se publican:
#   NBA             80%  (n=20)
#   Liga Colombiana 75%  (n=8)
#   Brasileirao     66%  (n=12)  ← RE-INCLUIDA (la exclusión del 9-may con n=6
#                                  estaba equivocada; con más datos gana)
#   Serie A         53%  (n=13)  ← borde, se mantiene con monitoreo
# Los partidos de las ligas excluidas siguen apareciendo en Análisis del Día
# (Nivel 1, informativo) pero NO se publican como recomendación de apuesta
# (Nivel 2 / Nivel 3). Reversible con git revert.
# EXPERIMENTO SHADOW (2026-05-24) terminado. Con base en el análisis de ROI histórico:
#   La Liga (-47.5% ROI), Premier League (-34.3% ROI), Super Lig (-48.2% ROI),
#   Bundesliga (-49.1% ROI), Ligue 1 (-100.0% ROI), Liga Argentina (-100.0% ROI).
# Estas ligas altamente eficientes se excluyen de picks oficiales (Nivel 2/3) para proteger el bankroll.
EXCLUDED_LEAGUES = {
    "Premier League",
    "La Liga",
    "Super Lig",
    "Bundesliga",
    "Ligue 1",
    "Liga Argentina",
}

# ── Regla de PICK EXPLORATORIO ──
# Fallback de publicación para evitar días en blanco cuando hay
# ligas CORE activas pero ningún pick pasa suscripción.
# NO es premium, NO es suscripción oficial — es una capa honesta
# de "hoy no hay valor claro pero esto es lo mejor que encontramos".
EXPLORATORY_MIN_PROB = 48.0   # prob_adjusted mínima (%)
EXPLORATORY_MIN_EV   = 5.0    # ev_adjusted mínimo (%)

# ── CAPA DE CONFIANZA (fallback sin cuotas reales) ──────────────
# Recalibración 23-may: el pipeline de EV requiere cuotas reales
# (odds.json), pero esa fuente está casi siempre vacía → días sin picks.
# Esta capa publica picks por PROBABILIDAD del modelo (confianza), sin
# exigir cuota ni EV, cuando el pipeline de valor no produce nada.
# Solo se activa si `top` quedó vacío (ver _select_confidence_picks).
# Mercados: favorito a ganar y Over 1.5 (mejor mercado histórico: 5/5).
# Umbrales respaldados por el track record (Over 1.5 ganadores en 69-77%).
CONF_PICK_ENABLED    = True   # toggle reversible — bajar a False para desactivar
CONF_WIN_MIN_PROB    = 66.0   # prob mínima del favorito a ganar (%)
CONF_OVER15_MIN_PROB = 72.0   # prob mínima de Over 1.5 goles (%)
CONF_MAX_PROB        = 80.0   # tope para "favorito a ganar": por encima la
                              # cuota es impagable (riesgo/recompensa malo).
                              # NO aplica a Over 1.5 (su cuota no colapsa igual).
CONF_MAX_PICKS       = 2      # cuántos picks de confianza publicar por día

# ── Línea de CÓRNERS (confianza, sin cuotas) ──
# Usa corners_avg de las danger signals (API-Football, vía _danger_load_data):
# expected = córners_avg(local) + córners_avg(visitante), modelado como Poisson.
# Elige la línea MÁS ALTA cuya P(Over) ≥ CONF_CORNERS_MIN_PROB. Pick aditivo
# (se publica además de los picks de goles/ganador). Requiere datos de córners
# del partido (n≥3 fixtures por equipo).
CONF_CORNERS_ENABLED   = True
CONF_CORNERS_LINES     = [7.5, 8.5, 9.5, 10.5, 11.5]  # líneas candidatas
CONF_CORNERS_MIN_PROB  = 70.0   # prob mínima (Poisson) para publicar
CONF_CORNERS_MAX_PICKS = 1      # cuántas líneas de córners por día

# ── Línea de OVER 2.5 GOLES con datos reales de API-Football ──
# Análisis INDEPENDIENTE. Usa los promedios de goles POR LOCALÍA de la API
# (goals.for/against.average.home/away) en vez de la fórmula con stats por
# país: λ = goles esperados del local (de local) + del visitante (de visita),
# modelado Poisson → P(Over 2.5) = P(total ≥ 3).
CONF_OVER25_ENABLED   = True
CONF_OVER25_MIN_PROB  = 60.0    # prob mínima para publicar (Over 2.5 es más difícil)
CONF_OVER25_MAX_PICKS = 1       # cuántos Over 2.5 por día

# ── ESCALERA DE PUBLICACIÓN — selección final entre todos los mercados ──
# Un partido cerrado es "under" en goles Y córners a la vez (correlación).
# Para no publicar varios picks correlacionados que pierden juntos:
#   1) se juntan TODOS los candidatos de confianza (goles, córners, Over 2.5),
#   2) se deja como máximo 1 mercado POR PARTIDO,
#   3) se publican los CONF_PUBLISH_MAX más confiables (la "escalera"),
#   4) el ranking pondera por confiabilidad del mercado, para que un córners
#      de muestra chica no le gane a un Over 1.5 sólido.
CONF_PUBLISH_MAX = 3            # cuántos picks totales se publican por día.
                               # 3 durante el shadow (validar goles + córners +
                               # Over 2.5); evaluar bajar a 2 al salir a público.
CONF_MIN_SAMPLE_CORNERS = 4    # mín. partidos por localía para confiar en córners
                               # (subido de 3 a 4 al pedir 20 fixtures de historial)
CONF_MARKET_RELIABILITY = {
    "over15":  1.00,   # Over 1.5 — histórico 100%, stats de temporada
    "win":     1.00,   # favorito a ganar
    "over25":  0.95,   # Over 2.5 (API por localía)
    "corners": 0.90,   # córners (Poisson, muestra chica) — más castigo
}

# ── ANÁLISIS DE GOLES (display complementario, NO pick) ──
# Mercados Over que no ganan el value_score del partido pero tienen
# valor moderado se exponen como "insight" sin ser publicados como pick.
GOALS_ANALYSIS_MIN_PROB = 50.0   # prob_adjusted mínima (%)
GOALS_ANALYSIS_MIN_EV   = 8.0    # ev_adjusted mínimo (%)
GOALS_ANALYSIS_MIN_CF   = 0.90   # confidence_factor mínimo
GOALS_ANALYSIS_MAX      = 3      # máximo de análisis de goles por día
# Ligas elegibles: top 5 europeas + Champions + CORE_LEAGUES
GOALS_ANALYSIS_LEAGUES = {
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
    "Champions League", "Liga Argentina", "Brasileirao",
}

# ── MIN_CONF para candidatura al pipeline (pre-filtro) ──
# Se baja de 45 a 40 para capturar señal parcial en CONMEBOL.
# 35% (empate técnico sin datos) sigue descartado.
MIN_CONF_SUBSCRIPTION = 40.0  # pre-filtro para candidatos de suscripción

# ── CONFIGURACIÓN CENTRAL — único lugar para cambiar umbrales de valor ──
MIN_EV            = 0.15   # EV mínimo para publicar (absorbe descuento BetPlay ~15%)
MAX_EV_H2H        = 0.20   # EV máximo para victoria directa, DNB y DC

# ── Transparencia de cuotas BetPlay (NO toca filtros del motor) ──
# Solo se usa para enriquecer el output con campos informativos
# (cuota_betplay_estimada, ev_betplay_estimado). El filtro real sigue
# siendo MIN_EV=0.15 sobre cuota europea — ver README sección Filosofía.
BETPLAY_DISCOUNT  = 0.90   # Betplay paga ~10% menos que mercado europeo (validado con 3+ samples)
MERCADO_REFERENCIA = "Pinnacle/Bet365 (europeo)"
BETPLAY_DISCLAIMER = "Cuota Betplay estimada con descuento del 10% promedio. Verifica antes de apostar."
MAX_EV_GOALS      = 0.35   # EV máximo para Over (más varianza)
MIN_CUOTA_WIN     = 1.60   # cuota mínima para victoria directa
MIN_CUOTA_DNB     = 1.30   # cuota mínima para DNB (apuesta sin empate)
MIN_CUOTA_DC      = 1.50   # cuota mínima para DC (doble oportunidad)
                           # Bug auditoría retrospectiva (9-may): DC con cuota
                           # 1.20-1.50 generaba yield -25.1% (n=17). A cuota
                           # 1.50 el break-even teórico baja a 67% hit rate
                           # (vs 47% real actual). Subido de 1.20 → 1.50 para
                           # eliminar el peor bucket. Reversible con git revert.
MIN_CUOTA_OVER25  = 1.60   # cuota mínima para Over 2.5 goles
MIN_CUOTA_OVER15  = 1.40   # cuota mínima para Over 1.5 goles
COLOMBIA_MIN_CONF       = 70.0  # prob mínima para picks estadísticos (Liga Colombiana)
MIN_VALID_ODDS          = 1.0   # cuota mínima válida del bookmaker (< 1.0 = dato inválido)
GOALS_FALLBACK_REGRESS  = 0.70  # factor de regresión al centro para fallback histórico de goles
CUOTA_INFINITA          = 99.0  # cuota centinela cuando la probabilidad es 0

# ── Parámetros del modelo de fútbol ──────────────────────────
MODEL_MAX_PROB      = 85.0  # cap superior de probabilidad
MODEL_MIN_PROB      = 15.0  # cap inferior de probabilidad
MODEL_DRAW_DIFF     = 10.0  # diferencia mínima hp-ap para no declarar empate técnico
WEIGHT_POSITION     = 0.40  # peso de la posición en tabla
WEIGHT_WIN_RATE     = 0.30  # peso del porcentaje de victorias
WEIGHT_GOAL_DIFF    = 0.20  # peso de la diferencia de goles
# ── Modelo logístico (corrige BUG-1/BUG-6 del diagnóstico 11-may) ──
# prob = 1 / (1 + e^(-k·Δscore)). Reemplaza la división proporcional
# h_score/total, que se invertía cuando los scores eran negativos.
# k y HOME_ADVANTAGE_SCORE son CALIBRABLES — barrer con backtest_model.py.
MODEL_LOGISTIC_K     = 0.10  # pendiente de la sigmoide
HOME_ADVANTAGE_SCORE = 3.0   # ventaja de local ADITIVA sobre Δscore (en puntos
                             # de score). Reemplaza el viejo HOME_ADVANTAGE_PCT
                             # multiplicativo. ~3.0 ≈ +7-8 pp para un partido parejo.
HOME_ADVANTAGE_PCT   = 0.10  # DEPRECATED — ya no se usa (era multiplicativo).
POSITION_RANGE      = 21    # max_posicion + 1 (para invertir el ranking)
DEFAULT_POSITION    = 10    # posición por defecto si no hay datos
DRAW_PCT_MIN        = 20.0  # % mínimo de empate en modelo 3-way
DRAW_PCT_MAX        = 30.0  # % máximo de empate en modelo 3-way (partidos 50/50)
DRAW_DIFF_FACTOR    = 0.20  # pendiente de reducción del % empate por diferencia

# ── Parámetros del modelo NBA ─────────────────────────────────
NBA_DEFAULT_PPG     = 110.0  # puntos por partido por defecto si no hay datos
NBA_HOME_ADVANTAGE  =   3.0  # ajuste de ventaja de local en puntos
NBA_SCORING_WEIGHT  =   0.5  # peso del diferencial de puntos sobre la probabilidad
NBA_MAX_PROB        =  85.0  # cap superior de probabilidad NBA
NBA_MIN_PROB        =  15.0  # cap inferior de probabilidad NBA

# ── Display ───────────────────────────────────────────────────
GOALS_HIGH_PCT       = 65    # umbral "alta probabilidad" en sección goles
GOALS_MID_PCT        = 45    # umbral "media probabilidad" en sección goles
VALUE_ALTO_THRESHOLD = 60.0  # EV% mínimo para nivel de valor "alto"

# ── Confidence adjuster del modelo ───────────────────────────
# Factor multiplicativo en [CONF_FLOOR, 1.0]. Solo reduce la probabilidad del modelo,
# nunca la aumenta. Depende del contexto (liga, mercado, EV bruto), no del partido.
CONF_FLOOR              = 0.85   # ajuste máximo absoluto

# Tier de liga: cuantos más datos y más eficiente el mercado, mayor confianza
CONF_LEAGUE_TOP         = 1.00   # top 5 europeo + Champions + NBA
CONF_LEAGUE_MID         = 0.97   # ligas con buen histórico pero menor eficiencia
CONF_LEAGUE_MINOR       = 0.95   # ligas menores (histórico corto o datos incompletos)

CONF_LEAGUE_TIERS = {
    # Bug #3 auditoría (p=0.021 vs benchmark 62.5%): subset conservador.
    # Solo Premier (40%, n=5) y Ligue 1 (0%, n=2) movidas a MID.
    # La Liga (40%, n=5) y Bundesliga (33%, n=3) quedan en TOP: la simulación
    # mostraba pérdida de 1 acierto en Bundes y datos no contundentes en La Liga.
    "Premier League":   CONF_LEAGUE_MID,   # 1.00 → 0.97 (40% histórico, n=5)
    "La Liga":          CONF_LEAGUE_TOP,   # 40% histórico (n=5) — datos no contundentes, mantiene
    "Serie A":          CONF_LEAGUE_TOP,   # 83% histórico (n=6) — mantiene
    "Bundesliga":       CONF_LEAGUE_TOP,   # 33% histórico (n=3) — pierde 1 acierto en sim, mantiene
    "Ligue 1":          CONF_LEAGUE_MID,   # 1.00 → 0.97 (0% histórico, n=2)
    "Champions League": CONF_LEAGUE_TOP,   # sin data verificada (n=0) — asunción
    "NBA":              CONF_LEAGUE_TOP,   # 76% histórico (n=17) — mantiene
    "Liga Argentina":      CONF_LEAGUE_MID,
    "Brasileirao":         CONF_LEAGUE_MID,
    # Super Lig: bajado de 0.97 → 0.92 tras simulación retrospectiva del 11-may.
    # Yield -37% incluso con Filtro 1 aplicado (3/6 publicados después de filtro).
    # Necesita más conservadurismo hasta investigar causa raíz específica de la liga.
    "Super Lig":           0.92,
    "Copa Libertadores":   CONF_LEAGUE_MID,
    "Copa Sudamericana":   CONF_LEAGUE_MID,
    # Liga Colombiana y demás → CONF_LEAGUE_MINOR (default)
}

# ── Filtro 1: forma reciente del favorito (motor v2 — fase 1) ────
# Rechaza picks cuyo equipo favorito tiene <RECENT_FORM_MIN_WINS victorias
# en sus últimos RECENT_FORM_LOOKBACK partidos en su liga doméstica antes
# del partido. Validado en simulación retrospectiva del 11-may sobre 38
# picks: yield -16.19% → +2.66% (Δ +18.85 pp), precisión rechazo 75%.
#
# Datos: static/api_football/data/{today}.json (poblado por collect_daily.py
# antes del motor en el cron). Si no hay datos → modo conservador (no filtra).
# NO aplica a NBA ni a picks Over/Under (sin equipo favorito).
USE_RECENT_FORM_FILTER  = True       # toggle reversible — bajar a False para desactivar
RECENT_FORM_MIN_WINS    = 2          # mínimo de victorias para no rechazar
RECENT_FORM_LOOKBACK    = 5          # ventana de partidos previos en doméstica
RECENT_FORM_DATA_DIR    = "static/api_football/data"
# IDs de torneos NO domésticos en API-Football (la forma se calcula solo
# en liga doméstica para evitar contaminación con copas continentales).
RECENT_FORM_INTL_LEAGUE_IDS = {
    2, 3, 848,        # UEFA Champions / Europa / Conference
    13, 11,           # CONMEBOL Libertadores / Sudamericana
    9, 1, 4, 32,      # Copa America / WC / Euro / WC qualifiers
    34, 15, 22, 480,  # CONCACAF / FIFA Club WC / otros
}

# ── Motor v1.2 — shadow mode, señal limpia y gestión de capital ──
MODEL_VERSION       = "v1.2-clean-signal"   # etiqueta en predictions_log.json

# Shadow mode: activo (hoy es 2026-05-28, modo shadow activo para pruebas)
SHADOW_MODE_UNTIL   = "2026-06-15"       # ISO date — En shadow mode hasta mediados de junio

# Gestión de capital: en modo "activo" el stake sugerido se muestra completo.
STAKE_MODE          = "activo"           # "lectura" | "activo"

# ── Platt scaling — DESACTIVADO durante el shadow v1.2 ───────────
# El calibrador entrenado sobre el histórico viejo está contaminado por
# BUG-1/BUG-2 (predicciones con el modelo invertido / equipo equivocado) y
# salió degenerado (comprime todo a ~50%). Durante los 14 días de shadow el
# motor corre SIN calibrar para que el log refleje la señal pura del modelo
# corregido. Al día 14 se reentrena el calibrador sobre datos v1.2 limpios.
# Reactivar: USE_CALIBRATION = True (y reentrenar con scripts/train_calibrator.py).
USE_CALIBRATION         = False
CALIBRATOR_PATH         = "static/calibrator.json"
MIN_CALIBRATION_SAMPLES = 20             # mínimo de picks verificados para entrenar

# Factor por frecuencia del mercado (muestra pequeña → calibración menos fiable)
CONF_FREQ_MID_THRESHOLD = 0.30   # freq < 0.30 → muestra reducida
CONF_FREQ_LOW_THRESHOLD = 0.10   # freq < 0.10 → muestra muy pequeña
CONF_FREQ_MID_FACTOR    = 0.98   # factor de confianza para frecuencia media
CONF_FREQ_LOW_FACTOR    = 0.95   # factor de confianza para frecuencia baja

# Factor por tipo de mercado (goles: varianza intrínsecamente mayor que el resultado)
CONF_GOALS_FACTOR       = 0.97   # aplica a Over 2.5 y Over 1.5

# Nota: la señal de overfit por EV bruto fue eliminada porque requería
# calcular EV con prob_modelo (sin ajustar), violando la invariante del pipeline.
# La protección equivalente la proveen MAX_EV_H2H y MAX_EV_GOALS (ev_excesivo).

# ── Penalización por liquidez de mercado ──────────────────────
# Mercados poco líquidos (Over 1.5, Alt Totals) tienen:
#   a) spread real más alto → cuota efectiva menor que la publicada
#   b) muestra estadística pequeña → mayor varianza en el modelo
# La penalización aumenta el EV mínimo requerido según qué tan raro es el mercado.
PENALTY_FREQ_HIGH = 0.30   # freq >= 0.30 → mercado líquido, sin penalización
PENALTY_FREQ_MID  = 0.10   # 0.10 <= freq < 0.30 → liquidez media
PENALTY_MID       = 0.03   # penalización para liquidez media (+3 pp al EV requerido)
PENALTY_LOW       = 0.06   # penalización para liquidez baja (+6 pp al EV requerido)

# ── Cuotas reales ──
_ODDS_CACHE        = None
_MARKET_FREQS_CACHE = None

def _load_odds():
    global _ODDS_CACHE
    if _ODDS_CACHE is None:
        p = Path("static/odds.json")
        _ODDS_CACHE = json.loads(p.read_text()) if p.exists() else {}
    return _ODDS_CACHE

def _compute_market_freqs():
    """
    Calcula la frecuencia de aparición de cada mercado en odds.json:
        freq = partidos_con_ese_mercado / partidos_totales
    DNB y DC se derivan del mercado draw → heredan su frecuencia.
    Resultado cacheado: se computa una sola vez por ejecución.
    """
    global _MARKET_FREQS_CACHE
    if _MARKET_FREQS_CACHE is not None:
        return _MARKET_FREQS_CACHE
    odds = _load_odds()
    total = len(odds)
    if total == 0:
        _MARKET_FREQS_CACHE = {}
        return _MARKET_FREQS_CACHE
    freqs = {}
    for key in ("win_home", "win_away", "draw", "over_2_5", "over_1_5"):
        count = sum(1 for v in odds.values() if v.get(key) is not None)
        freqs[key] = round(count / total, 4)
    draw_freq = freqs.get("draw", 0.0)
    for key in ("dnb_home", "dnb_away", "dc_home", "dc_away"):
        freqs[key] = draw_freq
    _MARKET_FREQS_CACHE = freqs
    return freqs

def compute_market_penalty(freq_market):
    """
    Penalización de EV según la frecuencia del mercado en el universo de partidos.
    Protege el ROI ante mercados poco líquidos: un mercado raro implica
    mayor spread real en la casas y muestra estadística pequeña en el modelo.
    Todos los umbrales y valores de penalización están en la configuración central.
    """
    if freq_market >= PENALTY_FREQ_HIGH:
        return 0.0
    if freq_market >= PENALTY_FREQ_MID:
        return PENALTY_MID
    return PENALTY_LOW

def compute_model_confidence(context):
    """
    Devuelve un factor multiplicativo en [CONF_FLOOR, 1.0] para ajustar la
    probabilidad del modelo según el contexto del mercado.

    context debe contener:
      league       — nombre de la liga
      freq_market  — frecuencia del mercado en odds.json (0.0–1.0)
      market_type  — "h2h" | "goals"

    Reglas (factores acumulativos, mínimo CONF_FLOOR):
      1. Liga: ligas menores → factor menor (menos datos, mercado menos eficiente)
      2. Frecuencia: mercados raros → calibración menos fiable
      3. Tipo: mercados de goles → más varianza que resultado
    """
    factor = 1.0

    factor *= CONF_LEAGUE_TIERS.get(context["league"], CONF_LEAGUE_MINOR)

    freq = context["freq_market"]
    if freq < CONF_FREQ_LOW_THRESHOLD:
        factor *= CONF_FREQ_LOW_FACTOR
    elif freq < CONF_FREQ_MID_THRESHOLD:
        factor *= CONF_FREQ_MID_FACTOR

    if context["market_type"] == "goals":
        factor *= CONF_GOALS_FACTOR

    return max(CONF_FLOOR, round(factor, 4))

def _norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii','ignore').decode().lower()
    for suf in (' fc',' cf',' sc',' ac',' sd',' ud',' cd',' af'):
        s = s.replace(suf,'')
    return s.strip()

def _teams_match(a, b):
    na, nb = _norm(a), _norm(b)
    if na in nb or nb in na: return True
    wa, wb = set(na.split()), set(nb.split())
    return len(wa & wb) >= max(1, min(len(wa), len(wb)) - 1)

def find_bk_odds(home, away, league, match_date):
    """Devuelve {win_home, draw, win_away} del mejor bookmaker disponible, o None."""
    odds = _load_odds()
    for data in odds.values():
        if data.get('league') != league: continue
        if data.get('date') != match_date: continue
        if _teams_match(home, data['home']) and _teams_match(away, data['away']):
            return data
    return None

def cuota_justa(wp):
    """Devuelve la cuota decimal justa para una probabilidad wp (%)."""
    if wp <= 0: return CUOTA_INFINITA
    return round(100 / wp, 2)


def _betplay_fields(bk_odds, prob_pct, ev_adjusted_pct):
    """
    Calcula los campos de transparencia BetPlay (aditivos, no afectan filtros).

    Args:
      bk_odds:           cuota europea de referencia (decimal, ej. 1.85). Puede ser None.
      prob_pct:          probabilidad ajustada en porcentaje 0-100 (ej. 62.5). Puede ser None.
      ev_adjusted_pct:   EV ajustado en porcentaje (ej. 8.5). Puede ser None.

    Returns:
      Dict con 6 campos: cuota_referencia, cuota_betplay_estimada,
      ev_referencia, ev_betplay_estimado, mercado_referencia, disclaimer.
      Cuota/EV BetPlay son None si bk_odds o prob_pct son None.
    """
    cuota_bp = None
    ev_bp    = None
    if bk_odds and bk_odds > 1.0:
        cuota_bp = round(bk_odds * BETPLAY_DISCOUNT, 2)
        if prob_pct is not None:
            ev_bp = round((prob_pct / 100.0) * cuota_bp - 1, 4) * 100
            ev_bp = round(ev_bp, 1)
    return {
        "cuota_referencia":        bk_odds,
        "cuota_betplay_estimada":  cuota_bp,
        "ev_referencia":           ev_adjusted_pct,
        "ev_betplay_estimado":     ev_bp,
        "mercado_referencia":      MERCADO_REFERENCIA,
        "disclaimer":              BETPLAY_DISCLAIMER,
    }


def value_level(vs):
    if vs >= VALUE_ALTO_THRESHOLD: return "alto"
    if vs > 0:                     return "medio"
    return "bajo"


# ── Gestión de capital — Kelly fraccionario (Quarter-Kelly) ──────
# Sugerencia de tamaño de apuesta como % del bankroll. NO decide qué picks
# se publican; solo enriquece el output. Quarter-Kelly (×0.25) reduce la
# volatilidad y protege el capital ante el error de estimación del modelo.
QUARTER_KELLY = 0.25

def kelly_stake(prob_pct, bk_odds, fraction=QUARTER_KELLY):
    """Fracción del bankroll a apostar según el criterio de Kelly.

      f = (b·p − q) / b      con  b = cuota_decimal − 1,  q = 1 − p

    Devuelve el % del bankroll ya multiplicado por `fraction` (Quarter-Kelly
    por defecto). Devuelve 0.0 si no hay cuota válida o si f ≤ 0 (sin ventaja).
    Se usa prob_adjusted (conservadora) para no sobre-apostar.
    """
    if not bk_odds or bk_odds <= 1.0 or prob_pct is None:
        return 0.0
    p = max(0.0, min(1.0, prob_pct / 100.0))
    b = bk_odds - 1.0
    q = 1.0 - p
    f = (b * p - q) / b
    if f <= 0:
        return 0.0
    return round(f * fraction * 100, 2)


# ─────────────────────── Calibración — Platt Scaling ───────────────────────
# El modelo sufre sobreconfianza (diagnóstico 11-may: bucket 70-75% declaraba
# 72.6% y la realidad fue 37.5%). Platt scaling remapea las probabilidades
# del modelo a probabilidades calibradas:  P_cal = 1 / (1 + exp(A·f + B)).

def platt_probability(f, A, B):
    """Aplica Platt scaling. `f` es la probabilidad del modelo en [0,1].
    Devuelve la probabilidad calibrada en [0,1]."""
    if A is None or B is None:
        return f
    z = A * f + B
    # 1/(1+e^z) con guarda de overflow
    if z >= 0:
        ez = math.exp(-z)
        return ez / (1.0 + ez)
    return 1.0 / (1.0 + math.exp(z))


def fit_platt_calibrator(pairs, iters=6000, lr=0.3):
    """Entrena Platt scaling por descenso de gradiente sobre la log-loss.

    Args:
      pairs: lista de (f, y) — f∈[0,1] prob del modelo, y∈{0,1} resultado real.
    Returns:
      (A, B) o (None, None) si no hay datos suficientes.

    Usa la regularización de targets de Platt (t+ = (N+ +1)/(N+ +2),
    t- = 1/(N- +2)) — clave con pocas muestras para no sobreajustar.
    """
    clean = [(float(f), int(y)) for f, y in pairs
             if f is not None and y is not None]
    n = len(clean)
    if n < MIN_CALIBRATION_SAMPLES:
        return None, None
    n_pos = sum(y for _, y in clean)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return None, None

    t_pos = (n_pos + 1.0) / (n_pos + 2.0)
    t_neg = 1.0 / (n_neg + 2.0)
    samples = [(f, t_pos if y == 1 else t_neg) for f, y in clean]

    A, B = 0.0, 0.0
    for _ in range(iters):
        gA = gB = 0.0
        for f, t in samples:
            z = A * f + B
            if z >= 0:
                ez = math.exp(-z)
                p = ez / (1.0 + ez)
            else:
                p = 1.0 / (1.0 + math.exp(z))
            # dL/dz = (t - p)  →  dL/dA = (t-p)·f ,  dL/dB = (t-p)
            gA += (t - p) * f
            gB += (t - p)
        A -= lr * gA / n
        B -= lr * gB / n
    return round(A, 6), round(B, 6)


def _load_calibrator():
    """Lee CALIBRATOR_PATH. Devuelve dict {A,B,...} o None si no existe/inválido."""
    p = Path(CALIBRATOR_PATH)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("A") is None or data.get("B") is None:
            return None
        return data
    except Exception as e:
        print(f"  ⚠ calibrator load error: {e}")
        return None


def train_and_save_calibrator(log_path="static/predictions_log.json",
                              out_path=CALIBRATOR_PATH):
    """Lee el log, extrae pares (prob_original, acerto) de picks verificados,
    entrena Platt y guarda los parámetros en out_path. Devuelve el dict o None.
    """
    from datetime import datetime as _dt
    lp = Path(log_path)
    if not lp.exists():
        print(f"  ⚠ {log_path} no existe — no se entrena calibrador")
        return None
    log = json.loads(lp.read_text(encoding="utf-8"))
    pairs = []
    for e in log:
        if e.get("acerto") is None:
            continue
        if e.get("tipo_pick") == "rejected_recent_form":
            continue
        prob = e.get("prob_original")
        if prob is None:
            continue
        pairs.append((prob / 100.0, 1 if e.get("acerto") else 0))

    A, B = fit_platt_calibrator(pairs)
    if A is None:
        print(f"  ⚠ datos insuficientes para calibrar (n={len(pairs)}, "
              f"mínimo {MIN_CALIBRATION_SAMPLES})")
        return None

    # Brier in-sample antes/después (referencia — el backtest hace CV honesto)
    def _brier(get_p):
        return sum((get_p(f) - y) ** 2 for f, y in pairs) / len(pairs)
    brier_before = _brier(lambda f: f)
    brier_after  = _brier(lambda f: platt_probability(f, A, B))

    out = {
        "A": A, "B": B,
        "n_samples": len(pairs),
        "trained_at": _dt.now().isoformat(timespec="seconds"),
        "model_version": MODEL_VERSION,
        "brier_in_sample_before": round(brier_before, 4),
        "brier_in_sample_after":  round(brier_after, 4),
    }
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"  ✓ calibrador entrenado: A={A} B={B} n={len(pairs)} "
          f"Brier {brier_before:.4f} → {brier_after:.4f}")
    return out


# Calibrador cargado una vez al importar el módulo.
# USE_CALIBRATION=False (shadow v1.2) → None: el motor no calibra.
_CALIBRATOR = _load_calibrator() if USE_CALIBRATION else None


# ─────────────────────────── Filtro 1 (forma reciente) ───────────────────────────

def _rf_load_data(today_str):
    """Carga static/api_football/data/{today}.json y retorna dict por (home, away)
    normalizado. Si no existe o falla, retorna {} (modo conservador → no filtra)."""
    p = Path(RECENT_FORM_DATA_DIR) / f"{today_str}.json"
    if not p.exists():
        return {}
    try:
        records = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠ recent_form load error: {e}")
        return {}
    out = {}
    for r in records:
        if not isinstance(r, dict):
            continue
        key = (_norm(r.get("home", "")), _norm(r.get("away", "")))
        out[key] = r
    return out


def _rf_favored_team(label, base_pick):
    """Extrae el equipo favorito del pick. None si es Over/Under (no aplica filtro)."""
    p = (label or "").strip()
    if "Over" in p or "Under" in p:
        return None
    if base_pick:
        return base_pick
    for pref in ("Doble oportunidad:", "Apuesta sin empate:"):
        if p.startswith(pref):
            return p.replace(pref, "").strip()
    return p or None


def _rf_count_wins_domestic(form_list, team_id, lookback=RECENT_FORM_LOOKBACK):
    """Cuenta victorias en los últimos N partidos en liga doméstica.

    Args:
      form_list: lista de fixtures de API-Football (last=N por equipo).
      team_id:   ID del equipo en API-Football.
      lookback:  N partidos a considerar.

    Returns:
      (wins, n_evaluated, form_string) si hay datos suficientes (≥lookback domésticos).
      None si no hay form_list o no se llegan a `lookback` partidos en doméstica
      (modo conservador: no se filtra).
    """
    if not form_list or not team_id:
        return None
    # Filtrar solo doméstica (excluir copas internacionales)
    domestic = []
    for f in form_list:
        league_id = ((f.get("league") or {}).get("id"))
        if league_id in RECENT_FORM_INTL_LEAGUE_IDS:
            continue
        # Solo partidos terminados
        status = ((f.get("fixture") or {}).get("status") or {}).get("short")
        if status not in ("FT", "AET", "PEN"):
            continue
        domestic.append(f)
    domestic.sort(
        key=lambda f: (f.get("fixture") or {}).get("date") or "",
        reverse=True,
    )
    last_n = domestic[:lookback]
    if len(last_n) < lookback:
        return None  # datos insuficientes → no filtrar (modo conservador)
    wins = 0
    form_chars = []
    for f in last_n:
        teams = f.get("teams") or {}
        home_id = (teams.get("home") or {}).get("id")
        away_id = (teams.get("away") or {}).get("id")
        home_w = (teams.get("home") or {}).get("winner")
        away_w = (teams.get("away") or {}).get("winner")
        if team_id == home_id:
            r = "W" if home_w is True else ("L" if home_w is False else "D")
        elif team_id == away_id:
            r = "W" if away_w is True else ("L" if away_w is False else "D")
        else:
            r = "?"
        form_chars.append(r)
        if r == "W":
            wins += 1
    return (wins, len(last_n), "".join(form_chars))


def _rf_apply_filter(evaluated_picks, today_str):
    """Aplica el filtro de forma reciente in-place. Marca cada evaluated_pick con:
        ep['_rf_rejected']  : bool — True si no pasa el filtro
        ep['_rf_form']      : str — string W/D/L de los últimos N (None si sin datos)
        ep['_rf_wins']      : int — victorias en la ventana (None si sin datos)
        ep['_rf_team']      : str — nombre del equipo evaluado (None si no aplica)

    Retorna lista de dicts (uno por rechazo) lista para loggear en predictions_log.
    """
    if not USE_RECENT_FORM_FILTER:
        return []
    data = _rf_load_data(today_str)
    if not data:
        print("  · Filtro 1 (forma reciente): sin datos de API-Football → modo conservador (no filtra)")
        return []
    rejected_log = []
    for ep in evaluated_picks:
        ep["_rf_rejected"] = False
        ep["_rf_form"] = None
        ep["_rf_wins"] = None
        ep["_rf_team"] = None
        if ep.get("nba"):
            continue
        label = (ep.get("label") or "")
        base_pick = ep["raw"][12]  # tupla raw, índice 12 = base_pick
        team = _rf_favored_team(label, base_pick)
        if not team:
            continue
        ep["_rf_team"] = team
        key = (_norm(ep.get("home", "")), _norm(ep.get("away", "")))
        match_data = data.get(key)
        if not match_data:
            continue
        # Identificar si el favorito es home o away del partido
        team_norm = _norm(team)
        home_norm = _norm(ep.get("home", ""))
        away_norm = _norm(ep.get("away", ""))
        if team_norm == home_norm or team_norm in home_norm or home_norm in team_norm:
            team_id = match_data.get("home_id")
            form_list = match_data.get("home_form")
        elif team_norm == away_norm or team_norm in away_norm or away_norm in team_norm:
            team_id = match_data.get("away_id")
            form_list = match_data.get("away_form")
        else:
            continue
        result = _rf_count_wins_domestic(form_list, team_id, RECENT_FORM_LOOKBACK)
        if result is None:
            continue  # datos insuficientes → no filtrar
        wins, _, form_str = result
        ep["_rf_form"] = form_str
        ep["_rf_wins"] = wins
        if wins < RECENT_FORM_MIN_WINS:
            ep["_rf_rejected"] = True
            be = ep.get("raw")[15] or {}
            rejected_log.append({
                "fecha":          today_str,
                "league":         ep.get("league"),
                "home":           ep.get("home"),
                "away":           ep.get("away"),
                "team":           team,
                "label":          label,
                "wins5":          wins,
                "forma":          form_str,
                "bk_odds":        ep.get("bk_odds"),
                "ev_adjusted":    ep.get("ev_adjusted"),
                "prob_adjusted": ep.get("prob_adjusted"),
                "confidence_factor": ep.get("confidence_factor"),
                "best_eval":      be,
            })
            print(f"  · [Filtro 1] rechazado: {ep.get('home')} vs {ep.get('away')} "
                  f"({ep.get('league')}) | favorito={team} | forma={form_str} "
                  f"W={wins}/{RECENT_FORM_LOOKBACK}")
    return rejected_log


# ───────────── Indicadores de peligro — PREPARACIÓN (motor v1.2) ─────────────
# Tiros a puerta y corners de los últimos 5 partidos domésticos. La idea
# (Acción 4): si tras el shadow mode el Brier no baja de 0.24, integrar estos
# indicadores en _team_score() — son mejores predictores que el resultado.
#
# ESTADO: PREPARACIÓN. La data se recolecta (collect_daily.py guarda
# home_danger / away_danger en static/api_football/data/{fecha}.json) y este
# lector la expone, pero NO alimenta el modelo todavía. Activación en Acción 4:
#   1) DANGER_SIGNALS_ENABLED = True
#   2) sumar  danger_index(...) * WEIGHT_DANGER  dentro de _team_score().

DANGER_SIGNALS_ENABLED = False   # Acción 4 — flip a True para integrar en h_score
WEIGHT_DANGER          = 0.0     # peso del índice de peligro en _team_score (calibrar)

def _danger_load_data(today_str):
    """Carga home_danger / away_danger desde el JSON diario de API-Football.
    Devuelve dict {(home_norm, away_norm): record} o {} si no hay datos."""
    p = Path(RECENT_FORM_DATA_DIR) / f"{today_str}.json"
    if not p.exists():
        return {}
    try:
        records = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠ danger_signals load error: {e}")
        return {}
    out = {}
    for r in records:
        if isinstance(r, dict):
            out[(_norm(r.get("home", "")), _norm(r.get("away", "")))] = r
    return out

def danger_index(danger):
    """Combina tiros a puerta y corners en un índice escalar.
    `danger` es el dict {shots_on_target_avg, corners_avg, ...}.
    Devuelve None si no hay datos. Fórmula provisional (calibrar en Acción 4):
       índice = shots_on_target_avg + 0.5 · corners_avg
    """
    if not danger:
        return None
    sot = danger.get("shots_on_target_avg")
    cor = danger.get("corners_avg")
    if sot is None and cor is None:
        return None
    return round((sot or 0.0) + 0.5 * (cor or 0.0), 2)


ADSENSE = '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5953880132871590" crossorigin="anonymous"></script>'
GA = '<script async src="https://www.googletagmanager.com/gtag/js?id=G-K3JES4SQS9"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag("js",new Date());gtag("config","G-K3JES4SQS9");</script>'

# ── URL base del sitio en produccion ──
SITE_URL = "https://prediktorcol.com"

ESPN_LEAGUES = {
    "soccer/eng.1":          ("Premier League",    "england_stats.json"),
    "soccer/esp.1":          ("La Liga",            "spain_stats.json"),
    "soccer/ita.1":          ("Serie A",            "italy_stats.json"),
    "soccer/ger.1":          ("Bundesliga",         "germany_stats.json"),
    "soccer/fra.1":          ("Ligue 1",            "france_stats.json"),
    "soccer/col.1":          ("Liga Colombiana",    "colombia_stats.json"),
    "soccer/arg.1":          ("Liga Argentina",     "argentina_stats.json"),
    "soccer/bra.1":          ("Brasileirao",        "brazil_stats.json"),
    "soccer/tur.1":          ("Super Lig",          "turkey_stats.json"),
    "soccer/uefa.champions": ("Champions League",   "uefa_champions_league_stats.json"),
    "soccer/conmebol.libertadores":  ("Copa Libertadores",  "conmebol_libertadores_stats.json"),
    "soccer/conmebol.sudamericana":  ("Copa Sudamericana",  "conmebol_sudamericana_stats.json"),
}

HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - PREDIKTOR</title>
<meta name="description" content="{desc}">
<meta name="keywords" content="{kw}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canonical}">
<!-- Open Graph -->
<meta property="og:type" content="article">
<meta property="og:title" content="{title} - PREDIKTOR">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="PREDIKTOR">
<meta property="og:locale" content="es_CO">
<!-- Twitter Card -->
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{title} - PREDIKTOR">
<meta name="twitter:description" content="{desc}">
<!-- Schema.org -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{title}",
  "description": "{desc}",
  "url": "{canonical}",
  "datePublished": "{date_iso}",
  "dateModified": "{date_iso}",
  "publisher": {{
    "@type": "Organization",
    "name": "PREDIKTOR",
    "url": "{site_url}"
  }},
  "mainEntityOfPage": {{
    "@type": "WebPage",
    "@id": "{canonical}"
  }}
}}
</script>
{adsense}
{ga}
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--navy-900:#0a0a0f;--navy-800:#13131a;--navy-700:#1a1a24;--gold-600:#c9a84c;--gold-500:#d4b865;--white:#fff;--gray-100:#e8edf5;--gray-400:#8896ae;--gray-600:#4a5568;--success:#22c55e;--danger:#ef4444;--font-display:'Barlow Condensed',sans-serif;--font-body:'Barlow',sans-serif;}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--font-body);background:var(--navy-900);color:var(--gray-100);min-height:100vh}}
.hdr{{background:rgba(5,13,26,.97);border-bottom:1px solid rgba(240,180,41,.15);padding:.9rem 2rem;display:flex;align-items:center;gap:1.5rem;position:sticky;top:0;z-index:100}}
.back{{background:none;border:1px solid rgba(240,180,41,.2);border-radius:4px;color:var(--gray-400);padding:.35rem .8rem;font-size:.85rem;text-decoration:none}}
.back:hover{{color:var(--gold-500)}}
.logo{{font-family:var(--font-display);font-size:1.6rem;font-weight:800;letter-spacing:.1em;color:var(--white);text-decoration:none}}
.logo span{{color:var(--gold-600)}}
.wrap{{max-width:860px;margin:3rem auto;padding:0 2rem 5rem}}
.badge{{display:inline-block;padding:.3rem 1rem;border-radius:2px;font-size:.62rem;letter-spacing:.25em;text-transform:uppercase;font-weight:600;background:rgba(240,180,41,.12);color:var(--gold-500);border:1px solid rgba(240,180,41,.25);margin-bottom:1rem}}
h1{{font-family:var(--font-display);font-size:clamp(1.8rem,4vw,2.8rem);font-weight:800;color:var(--white);line-height:1.2;margin-bottom:.8rem}}
.div{{width:60px;height:2px;background:linear-gradient(90deg,transparent,var(--gold-600),transparent);margin:1rem 0 1.5rem}}
.meta{{font-size:.75rem;letter-spacing:.2em;text-transform:uppercase;color:var(--gray-400);margin-bottom:2.5rem}}
.body p{{font-size:1rem;line-height:1.9;color:var(--gray-100);margin-bottom:1.2rem}}
.body h2{{font-family:var(--font-display);font-size:1.5rem;font-weight:700;color:var(--gold-500);margin:2.5rem 0 1rem;letter-spacing:.08em}}
.body strong{{color:var(--gold-500)}}
.sbox{{background:var(--navy-800);border:1px solid rgba(240,180,41,.15);border-left:3px solid var(--gold-600);border-radius:0 6px 6px 0;padding:1.5rem 2rem;margin:2rem 0}}
.srow{{display:flex;justify-content:space-between;padding:.5rem 0;border-bottom:1px solid rgba(255,255,255,.04)}}
.srow:last-child{{border-bottom:none}}
.slbl{{font-size:.85rem;color:var(--gray-400)}}
.sval{{font-size:.9rem;font-weight:600}}
.pbox{{background:var(--navy-800);border:1px solid rgba(240,180,41,.2);border-top:3px solid var(--gold-600);border-radius:8px;padding:2rem;margin:2.5rem 0;text-align:center}}
.plbl{{font-size:.65rem;letter-spacing:.25em;text-transform:uppercase;color:var(--gray-400);margin-bottom:.5rem}}
.pres{{font-family:var(--font-display);font-size:2.2rem;font-weight:800;color:var(--gold-500)}}
.pconf{{font-size:.85rem;color:var(--gray-400);margin-top:.3rem}}
.goals-section{{margin:2.5rem 0 0}}
.goals-grid{{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1rem}}
.goal-card{{background:var(--navy-800);border:1px solid rgba(240,180,41,.12);border-radius:8px;padding:1.4rem 1.6rem;position:relative;overflow:hidden}}
.goal-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--gold-600),transparent)}}
.goal-label{{font-size:.6rem;letter-spacing:.25em;text-transform:uppercase;color:var(--gray-400);font-weight:600;margin-bottom:.6rem}}
.goal-value{{font-family:var(--font-display);font-size:2rem;font-weight:800;line-height:1;margin-bottom:.4rem}}
.goal-value.high{{color:var(--success)}}
.goal-value.mid{{color:var(--gold-500)}}
.goal-value.low{{color:var(--danger)}}
.goal-bar-wrap{{height:4px;background:rgba(255,255,255,.08);border-radius:2px;margin:.6rem 0}}
.goal-bar{{height:100%;border-radius:2px}}
.goal-bar.high{{background:linear-gradient(90deg,#16a34a,var(--success))}}
.goal-bar.mid{{background:linear-gradient(90deg,var(--gold-700),var(--gold-500))}}
.goal-bar.low{{background:linear-gradient(90deg,#b91c1c,var(--danger))}}
.goal-rec{{font-size:.72rem;color:var(--gray-400);margin-top:.3rem}}
.goal-rec strong{{color:var(--gold-500)}}
.cta{{background:linear-gradient(135deg,var(--navy-800),var(--navy-700));border:1px solid rgba(240,180,41,.2);border-radius:8px;padding:2rem;text-align:center;margin-top:3rem}}
.cta p{{margin-bottom:1rem;color:var(--gray-400)}}
.cta a{{display:inline-block;background:linear-gradient(135deg,#b88e30,var(--gold-500));color:#050d1a;padding:.9rem 2rem;border-radius:4px;font-family:var(--font-display);font-size:1.1rem;font-weight:700;letter-spacing:.1em;text-decoration:none}}
.ftr{{border-top:1px solid rgba(240,180,41,.1);padding:1.5rem 2rem;text-align:center;font-size:.68rem;color:var(--gray-600);letter-spacing:.1em}}
</style>
</head>
<body>
<header class="hdr"><a href="/index.html" class="back">← Volver</a><a href="/index.html" class="logo">PREDI<span>KTOR</span></a></header>
<main class="wrap">
<span class="badge">{league} · {date}</span>
<h1>Prediccion: {home} vs {away}</h1>
<div class="div"></div>
<p class="meta">Analisis · PREDIKTOR · {date}</p>
<div class="body">{article}</div>
<div class="cta"><p>Usa nuestro analizador interactivo para ver estadisticas detalladas</p><a href="/index.html">Analizar partido en vivo</a></div>
</main>
<footer class="ftr">PREDIKTOR 2026 · <a href="/privacy.html" style="color:var(--gray-600);text-decoration:none;">Privacidad</a></footer>
</body></html>"""

INDEX = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Predicciones deportivas hoy {date} - PREDIKTOR</title>
<meta name="description" content="Predicciones y pronosticos deportivos para hoy {date}. Partidos reales de futbol y NBA con estadisticas.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{site_url}/static/predictions/index.html">
<meta property="og:type" content="website">
<meta property="og:title" content="Predicciones deportivas hoy {date} - PREDIKTOR">
<meta property="og:description" content="Predicciones y pronosticos deportivos para hoy {date}. Partidos reales de futbol y NBA con estadisticas.">
<meta property="og:url" content="{site_url}/static/predictions/index.html">
<meta property="og:site_name" content="PREDIKTOR">
{adsense}
{ga}
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--navy-900:#0a0a0f;--navy-800:#13131a;--gold-600:#c9a84c;--gold-500:#d4b865;--white:#fff;--gray-100:#e8edf5;--gray-400:#8896ae;--gray-600:#4a5568;--font-display:'Barlow Condensed',sans-serif;--font-body:'Barlow',sans-serif;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--font-body);background:var(--navy-900);color:var(--gray-100);min-height:100vh}}
.hdr{{background:rgba(5,13,26,.97);border-bottom:1px solid rgba(240,180,41,.15);padding:.9rem 2rem;display:flex;align-items:center;gap:1.5rem;position:sticky;top:0;z-index:100}}
.back{{background:none;border:1px solid rgba(240,180,41,.2);border-radius:4px;color:var(--gray-400);padding:.35rem .8rem;font-size:.85rem;text-decoration:none}}
.logo{{font-family:var(--font-display);font-size:1.6rem;font-weight:800;letter-spacing:.1em;color:var(--white);text-decoration:none}}
.logo span{{color:var(--gold-600)}}
.wrap{{max-width:1000px;margin:3rem auto;padding:0 2rem 5rem}}
h1{{font-family:var(--font-display);font-size:2.5rem;font-weight:800;color:var(--white);margin-bottom:.5rem}}
.sub{{color:var(--gray-400);font-size:.85rem;letter-spacing:.2em;text-transform:uppercase;margin-bottom:3rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1.5rem}}
.card{{background:var(--navy-800);border:1px solid rgba(240,180,41,.1);border-radius:8px;padding:1.5rem;text-decoration:none;display:block;transition:transform .3s,border-color .3s}}
.card:hover{{transform:translateY(-4px);border-color:rgba(240,180,41,.3)}}
.lg{{font-size:.6rem;letter-spacing:.25em;text-transform:uppercase;color:var(--gold-500);font-weight:600}}
.card h3{{font-family:var(--font-display);font-size:1.2rem;font-weight:700;color:var(--white);margin:.5rem 0 1rem;line-height:1.3}}
.lnk{{font-size:.8rem;color:var(--gold-500)}}
.empty{{text-align:center;padding:4rem;color:var(--gray-400)}}
.ftr{{border-top:1px solid rgba(240,180,41,.1);padding:1.5rem 2rem;text-align:center;font-size:.68rem;color:var(--gray-600);letter-spacing:.1em}}
</style>
</head>
<body>
<header class="hdr"><a href="/index.html" class="back">← Volver</a><a href="/index.html" class="logo">PREDI<span>KTOR</span></a></header>
<main class="wrap">
<h1>Predicciones de hoy</h1>
<p class="sub">{date} · Solo partidos programados para hoy</p>
<div class="grid">{cards}</div>
</main>
<footer class="ftr">
  <div style="margin-bottom:0.8rem;font-size:0.75rem;color:var(--gray-400);line-height:1.6;text-transform:none;letter-spacing:normal;">
    🔞 <strong>JUEGO RESPONSABLE:</strong> Las apuestas deportivas son exclusivamente para mayores de 18 años (+18). El juego puede ser adictivo, juegue con moderación y responsabilidad. En Colombia, use únicamente operadores autorizados por <strong>Coljuegos</strong>.
  </div>
  PREDIKTOR 2026 · <a href="/privacy.html" style="color:var(--gray-600);text-decoration:none;">Privacidad</a> · <a href="/apuestas-legales.html" style="color:var(--gold-500);text-decoration:none;margin-left:1rem;font-weight:600;">Casas Autorizadas 🇨🇴</a>
</footer>
</body></html>"""

def norm(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s.lower())
        if unicodedata.category(c) != 'Mn'
    )

TEAM_ALIASES = {
    # Colombia - aliases ESPN -> JSON
    "Internacional de Bogota": "La Equidad", "Internacional de Bogota FC": "La Equidad",
    "Internacional de Bogotá": "La Equidad", "Internacional de Bogotá FC": "La Equidad",
    "internacional de bogotá": "La Equidad", "internacional de bogota": "La Equidad",
    "Atletico Junior": "Junior",
    "Atletico Nacional": "A. Nacional",
    "Athletico-PR": "Athletico PR",
    "Atletico Bucaramanga": "A. Bucaramanga",
    "Atletico Petrolera": "A. Petrolera",
    "Deportivo Pereira": "D. Pereira",
    "Jaguares de Cordoba": "Jaguares de C.",
    "Rionegro Aguilas": "R. Aguilas",
    "Fortaleza CEIF FC": "Fortaleza CEIF",
    "deportivo pereira":          "D. Pereira",
    "atletico nacional":          "A. Nacional",
    "atletico bucaramanga":       "A. Bucaramanga",
    "atletico petrolera":         "A. Petrolera",
    "independiente medellin":     "I. Medelin",
    "rionegro aguilas":           "R. Aguilas",
    "aguilas doradas rionegro":   "R. Aguilas",
    "jaguares de cordoba":        "Jaguares de C.",
    "jaguares":                   "Jaguares de C.",
    "deportivo cali":             "Deportivo Cali",
    "america de cali":            "America de Cali",
    "boyaca chico":               "Boyaca Chico",
    "once caldas":                "Once Caldas",
    "deportes tolima":            "Deportes Tolima",
    "deportivo pasto":            "Deportivo Pasto",
    "la equidad":                 "La Equidad",
    "millonarios":                "Millonarios",
    "junior":                     "Junior",
    "junior fc":                  "Junior",
    "santa fe":                   "Santa Fe",
    "independiente santa fe":     "Santa Fe",
    "fortaleza ceif":             "Fortaleza CEIF",
    "llaneros":                   "Llaneros",
    "cucuta deportivo":           "Cucuta",
    "cucuta":                     "Cucuta",
    # Ligue 1
    "Paris Saint-Germain":        "Paris SG",
    "paris saint-germain":        "Paris SG",
    "psg":                        "Paris SG",
    # Premier League
    "Nottingham Forest":          "Nott'm Forest",
    "nottingham forest":          "Nott'm Forest",
    "Newcastle Utd":              "Newcastle",
    "newcastle utd":              "Newcastle",
    # Serie A
    "Inter Milan":                "Inter",
    "inter milan":                "Inter",
    "AC Milan":                   "Milan",
    "ac milan":                   "Milan",
    "Hellas Verona":              "Verona",
    "hellas verona":              "Verona",
    # La Liga
    "Atletico Madrid":            "Atlético Madrid",
    "atletico madrid":            "Atlético Madrid",
    "Real Betis":                 "Betis",
    "real betis":                 "Betis",
    # Bundesliga
    "Eintracht Frankfurt":        "E. Frankfurt",
    "eintracht frankfurt":        "E. Frankfurt",
    "Bayer Leverkusen":           "B. Leverkusen",
    "bayer leverkusen":           "B. Leverkusen",
    # Liga Argentina
    "Gimnasia (Mendoza)":         "G. Mendoza",
    "gimnasia (mendoza)":         "G. Mendoza",
    "gimnasia mendoza":           "G. Mendoza",
    "Talleres (Córdoba)":         "T. de Cordoba",
    "talleres (córdoba)":         "T. de Cordoba",
    "talleres cordoba":           "T. de Cordoba",
    "Independiente Rivadavia":    "I. Rivadavia",
    "independiente rivadavia":    "I. Rivadavia",
    "Atletico Tucuman":           "A. Tucuman",
    "atletico tucuman":           "A. Tucuman",
    "Deportivo Riestra":          "D. Riestra",
    "deportivo riestra":          "D. Riestra",
    "Defensa y Justicia":         "Defensa y J.",
    "defensa y justicia":         "Defensa y J.",
    # Brasileirao
    "Atletico-MG":                "Atlético-MG",
    "atletico-mg":                "Atlético-MG",
    "atletico mineiro":           "Atlético-MG",
    "Red Bull Bragantino":        "Bragantino",
    "red bull bragantino":        "Bragantino",
}

def espn_fixtures(code):
    """Obtiene partidos de hoy (hora Colombia) que aún no han terminado."""
    matches = []
    seen = set()
    # Consultar hoy y mañana en UTC para capturar todos los partidos del día Colombia
    dates_to_check = [today.replace("-",""), tomorrow.replace("-","")]
    for d in dates_to_check:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{code}/scoreboard?dates={d}"
            r = requests.get(url, timeout=10)
            for e in r.json().get("events", []):
                event_date_utc = e.get("date", "")
                event_date = event_date_utc[:10]
                event_hour = int(event_date_utc[11:13]) if len(event_date_utc) > 12 else 0
                status = e.get("status", {}).get("type", {}).get("description", "")
                if status in ("Full Time", "Final", "FT", "Finalizado"):
                    continue
                # Hora Colombia = UTC-5. Acepta partidos del día Colombia:
                # hoy UTC o mañana UTC antes de las 06:00 UTC
                event_col_date = (
                    datetime.strptime(event_date_utc[:16], "%Y-%m-%dT%H:%M")
                    .replace(tzinfo=timezone.utc) - timedelta(hours=5)
                ).strftime("%Y-%m-%d")
                if event_col_date != today:
                    continue
                cs = e.get("competitions", [{}])[0].get("competitors", [])
                if len(cs) >= 2:
                    h = next((c["team"]["displayName"] for c in cs if c.get("homeAway") == "home"), None)
                    a = next((c["team"]["displayName"] for c in cs if c.get("homeAway") == "away"), None)
                    if h and a and (h, a) not in seen:
                        seen.add((h, a))
                        matches.append((h, a))
        except Exception as ex:
            print(f"   ESPN error ({code} {d}): {ex}")
    return matches

def nba_fixtures():
    return espn_fixtures("basketball/nba")

def load(f):
    p = Path(f"static/{f}")
    return json.load(open(p)) if p.exists() else {}

# ── Fallback CONMEBOL: buscar equipo en stats de ligas locales ──
# Equipos de Libertadores/Sudamericana ya tienen datos en sus ligas
# domésticas. Si el JSON de la competición CONMEBOL está vacío,
# se busca en los stats de Argentina, Brasil, Colombia, etc.
_CONMEBOL_FALLBACK_FILES = [
    "argentina_stats.json",
    "brazil_stats.json",
    "colombia_stats.json",
    "uruguay_stats.json",
    "ecuador_stats.json",
    "chile_stats.json",
    "paraguay_stats.json",
]

def _find_in_local_leagues(name):
    """Busca un equipo en los stats de ligas locales sudamericanas."""
    nl = norm(name)
    resolved = TEAM_ALIASES.get(name) or TEAM_ALIASES.get(nl)
    for f in _CONMEBOL_FALLBACK_FILES:
        local_stats = load(f)
        if not local_stats:
            continue
        search_name = resolved or name
        # Búsqueda exacta
        if search_name in local_stats:
            return local_stats[search_name]
        # Búsqueda normalizada
        for k in local_stats:
            if norm(k) == nl:
                return local_stats[k]
        for k in local_stats:
            nk = norm(k)
            if nk in nl or nl in nk:
                return local_stats[k]
    return {}

def _fuzzy_best(target_norm, keys, norm_keys):
    """Mejor match difuso. Devuelve (key_original, score 0-100) o (None, 0.0).
    Usa RapidFuzz si está disponible; si no, difflib (stdlib) como fallback."""
    if not keys:
        return None, 0.0
    if _HAS_RAPIDFUZZ:
        m = _rf_process.extractOne(target_norm, norm_keys, scorer=_rf_fuzz.WRatio)
        return (keys[m[2]], m[1]) if m else (None, 0.0)
    best_i, best_r = None, 0.0
    for i, nk in enumerate(norm_keys):
        r = _SeqMatcher(None, target_norm, nk).ratio() * 100
        if r > best_r:
            best_r, best_i = r, i
    return (keys[best_i], best_r) if best_i is not None else (None, 0.0)

def find(stats, name):
    if not stats:
        # Stats vacío (típico en CONMEBOL) → buscar en ligas locales
        fallback = _find_in_local_leagues(name)
        if fallback:
            print(f"      [CONMEBOL fallback] '{name}' encontrado en liga local")
            return fallback
        return {}
    nl = norm(name)
    # 1) Alias explícito
    if name in TEAM_ALIASES:
        alias = TEAM_ALIASES[name]
        if alias in stats:
            print(f"      [alias] '{name}' → '{alias}'")
            return stats[alias]
    elif nl in TEAM_ALIASES:
        alias = TEAM_ALIASES[nl]
        if alias in stats:
            print(f"      [alias] '{name}' → '{alias}'")
            return stats[alias]
    # 2) Match exacto normalizado
    for k in stats:
        if norm(k) == nl:
            return stats[k]
    # 3) Match difuso — corrige BUG-2. Si nada supera FUZZY_MATCH_THRESHOLD
    #    NO se devuelven las stats de otro equipo: se devuelve {}.
    keys = list(stats.keys())
    norm_keys = [norm(k) for k in keys]
    best_key, best_score = _fuzzy_best(nl, keys, norm_keys)
    if best_key is not None and best_score >= FUZZY_MATCH_THRESHOLD:
        return stats[best_key]
    # 4) Sin match confiable → ligas locales (CONMEBOL), luego rendirse con {}
    fallback = _find_in_local_leagues(name)
    if fallback:
        print(f"      [CONMEBOL fallback] '{name}' encontrado en liga local")
        return fallback
    print(f"      [WARN] '{name}' sin match confiable "
          f"(mejor score={best_score:.0f} < {FUZZY_MATCH_THRESHOLD}) — fixture SIN datos")
    return {}

def gs(d, *ks):
    pos = d.get("position", {})
    aliases = {
        "wins":              ["ganados", "won"],
        "won":               ["ganados", "wins"],
        "losses":            ["perdidos", "lost"],
        "lost":              ["perdidos", "losses"],
        "goals_for":          ["goles_favor"],
        "goals_against":      ["goles_contra"],
        "avg_points":         ["promedio"],
        "avg_points_allowed": ["goles_contra"],
    }
    for k in ks:
        if d.get(k) is not None: return d[k]
        if pos.get(k) is not None: return pos[k]
        for a in aliases.get(k, []):
            if d.get(a) is not None: return d[a]
        for a in aliases.get(k, []):
            if pos.get(a) is not None: return pos[a]
    return "N/A"

def safe_float(v, default=0.0):
    try:
        return float(v or default)
    except (ValueError, TypeError):
        return default

def parse_pct(s):
    if not s or s == "N/A": return 0.0
    try:
        return float(str(s).replace('%', '').strip())
    except:
        return 0.0

# ══════════════════════════════════════════════════════════════
#  FUTBOL — replica calculator.js predictWinner()
#  Puede retornar EMPATE (hp == ap == 50.0)
# ══════════════════════════════════════════════════════════════
def _team_score(pos):
    """Score compuesto de un equipo: posición (40%) + win rate (30%) + dif. goles (20%).
    Puede ser negativo (equipo de mala campaña con diferencia de goles negativa)."""
    s  = (POSITION_RANGE - safe_float(pos.get("posicion"), DEFAULT_POSITION)) * WEIGHT_POSITION * 5
    games = safe_float(pos.get("partidos"), 1) or 1
    s += (safe_float(pos.get("ganados")) / games * 100) * WEIGHT_WIN_RATE
    s += safe_float(pos.get("diferencia")) * WEIGHT_GOAL_DIFF
    return s

def prob_futbol(hd, ad, danger=None):
    """Calcula la probabilidad de victoria/derrota 2-way usando el modelo de Poisson
    con ajuste opcional por Danger Signals (tiros a puerta/córners).
    """
    p_win, p_draw, p_lose = prob_futbol_3way_raw(hd, ad, danger)
    
    sum_wl = p_win + p_lose
    if sum_wl > 0:
        hp = (p_win / sum_wl) * 100
        ap = (p_lose / sum_wl) * 100
    else:
        hp, ap = 50.0, 50.0
        
    # Aplicar caps de probabilidad del modelo
    hp = min(MODEL_MAX_PROB, max(MODEL_MIN_PROB, hp))
    ap = round(100.0 - hp, 1)
    hp = round(hp, 1)
    
    # Empate técnico
    if abs(hp - ap) < MODEL_DRAW_DIFF:
        return 50.0, 50.0
        
    return hp, ap

def prob_futbol_3way_raw(hd, ad, danger=None):
    # Extracción de estadísticas desde el dict de posición
    h_pos = hd.get("position", {}) if isinstance(hd, dict) else {}
    a_pos = ad.get("position", {}) if isinstance(ad, dict) else {}
    
    h_gf = safe_float(h_pos.get("goles_favor"), 0)
    h_gc = safe_float(h_pos.get("goles_contra"), 0)
    h_games = safe_float(h_pos.get("partidos"), 0)
    
    a_gf = safe_float(a_pos.get("goles_favor"), 0)
    a_gc = safe_float(a_pos.get("goles_contra"), 0)
    a_games = safe_float(a_pos.get("partidos"), 0)
    
    # Valores por defecto para el modelo de goles
    AVG_LEAGUE_GOALS = 1.35
    HOME_ADVANTAGE_FACTOR = 1.15
    
    h_att = h_gf / h_games if h_games > 0 else AVG_LEAGUE_GOALS
    h_def = h_gc / h_games if h_games > 0 else AVG_LEAGUE_GOALS
    a_att = a_gf / a_games if a_games > 0 else AVG_LEAGUE_GOALS
    a_def = a_gc / a_games if a_games > 0 else AVG_LEAGUE_GOALS
    
    # Forzar límites realistas de ataque y defensa
    h_att = max(0.3, min(3.0, h_att))
    h_def = max(0.3, min(3.0, h_def))
    a_att = max(0.3, min(3.0, a_att))
    a_def = max(0.3, min(3.0, a_def))
    
    # Expectativa base de goles (lambda)
    lambda_h = (h_att * a_def / AVG_LEAGUE_GOALS) * HOME_ADVANTAGE_FACTOR
    lambda_a = (a_att * h_def / AVG_LEAGUE_GOALS) / HOME_ADVANTAGE_FACTOR
    
    # Ajuste por Danger Signals (Tiros a Puerta)
    if danger and isinstance(danger, dict):
        home_sot = danger.get("home_sot")
        away_sot = danger.get("away_sot")
        SOT_AVG = 4.5
        
        if home_sot is not None:
            # Factor de ajuste proporcional: 15% de peso sobre la desviación del promedio
            adj_h = 1.0 + 0.15 * ((safe_float(home_sot) - SOT_AVG) / SOT_AVG)
            lambda_h *= max(0.7, min(1.3, adj_h))
            
        if away_sot is not None:
            adj_a = 1.0 + 0.15 * ((safe_float(away_sot) - SOT_AVG) / SOT_AVG)
            lambda_a *= max(0.7, min(1.3, adj_a))
            
    # Ajuste por Elo Rating
    elo_home = hd.get("elo") if isinstance(hd, dict) else None
    elo_away = ad.get("elo") if isinstance(ad, dict) else None
    if elo_home is not None and elo_away is not None:
        elo_diff = elo_home - elo_away
        adj_h = 1.0 + 0.0005 * elo_diff
        adj_a = 1.0 - 0.0005 * elo_diff
        lambda_h *= max(0.8, min(1.2, adj_h))
        lambda_a *= max(0.8, min(1.2, adj_a))
            
    # Límites para lambdas
    lambda_h = max(0.1, min(6.0, lambda_h))
    lambda_a = max(0.1, min(6.0, lambda_a))
    
    # Distribución Poisson
    p_win = 0.0
    p_draw = 0.0
    p_lose = 0.0
    
    poisson_h = [ (lambda_h**x * math.exp(-lambda_h)) / math.factorial(x) for x in range(11) ]
    poisson_a = [ (lambda_a**y * math.exp(-lambda_a)) / math.factorial(y) for y in range(11) ]
    
    for x in range(11):
        for y in range(11):
            p_xy = poisson_h[x] * poisson_a[y]
            if x > y:
                p_win += p_xy
            elif x == y:
                p_draw += p_xy
            else:
                p_lose += p_xy
                
    # Renormalización
    total = p_win + p_draw + p_lose
    if total > 0:
        p_win /= total
        p_draw /= total
        p_lose /= total
    else:
        p_win, p_draw, p_lose = 0.37, 0.26, 0.37
        
    return p_win, p_draw, p_lose

# ══════════════════════════════════════════════════════════════
#  NBA — replica index.html bkWinProb()
#  NUNCA retorna empate
# ══════════════════════════════════════════════════════════════
def prob_nba(hd, ad):
    h_win_pct = safe_float(hd.get("win_pct"), 50)
    a_win_pct = safe_float(ad.get("win_pct"), 50)
    h_avg_pts = safe_float(hd.get("avg_points"), NBA_DEFAULT_PPG)
    a_avg_pts = safe_float(ad.get("avg_points"), NBA_DEFAULT_PPG)
    
    diff = (h_win_pct - a_win_pct) + (h_avg_pts - a_avg_pts) * NBA_SCORING_WEIGHT + NBA_HOME_ADVANTAGE
    hp = min(NBA_MAX_PROB, max(NBA_MIN_PROB, 50 + diff))
    ap = round(100 - hp, 1)
    hp = round(hp, 1)
    return hp, ap

def prob_futbol_3way(hd, ad, danger=None):
    """Modelo de 3 resultados (win%, draw%, lose%) para fútbol basado en Poisson."""
    p_win, p_draw, p_lose = prob_futbol_3way_raw(hd, ad, danger)
    win = round(p_win * 100, 1)
    lose = round(p_lose * 100, 1)
    draw = round(100.0 - win - lose, 1)
    return win, draw, lose

def get_probabilities(hd, ad, nba=False, danger=None):
    """Devuelve dict con todas las probabilidades del modelo (valores 0.0–1.0)."""
    if nba:
        hp, ap = prob_nba(hd, ad)
        favorite = "home" if hp >= ap else "away"
        return {
            "win_home": hp / 100, "draw": 0.0, "win_away": ap / 100,
            "dnb_home": hp / 100, "dnb_away": ap / 100,
            "dc_home":  hp / 100, "dc_away":  ap / 100,
            "over_2_5": 0.0, "over_1_5": 0.0,
            "favorite": favorite, "hp_raw": hp, "ap_raw": ap, "nba": True,
        }

    # Fútbol: obtener probabilidades 3-way reales de Poisson
    p_win, p_draw, p_lose = prob_futbol_3way_raw(hd, ad, danger)
    hp, ap = prob_futbol(hd, ad, danger)

    # Calcular Over 2.5 y Over 1.5 de forma coherente usando las lambdas del modelo
    h_pos = hd.get("position", {}) if isinstance(hd, dict) else {}
    a_pos = ad.get("position", {}) if isinstance(ad, dict) else {}
    
    h_gf = safe_float(h_pos.get("goles_favor"), 0)
    h_gc = safe_float(h_pos.get("goles_contra"), 0)
    h_games = safe_float(h_pos.get("partidos"), 0)
    
    a_gf = safe_float(a_pos.get("goles_favor"), 0)
    a_gc = safe_float(a_pos.get("goles_contra"), 0)
    a_games = safe_float(a_pos.get("partidos"), 0)
    
    AVG_LEAGUE_GOALS = 1.35
    HOME_ADVANTAGE_FACTOR = 1.15
    
    h_att = h_gf / h_games if h_games > 0 else AVG_LEAGUE_GOALS
    h_def = h_gc / h_games if h_games > 0 else AVG_LEAGUE_GOALS
    a_att = a_gf / a_games if a_games > 0 else AVG_LEAGUE_GOALS
    a_def = a_gc / a_games if a_games > 0 else AVG_LEAGUE_GOALS
    
    h_att = max(0.3, min(3.0, h_att))
    h_def = max(0.3, min(3.0, h_def))
    a_att = max(0.3, min(3.0, a_att))
    a_def = max(0.3, min(3.0, a_def))
    
    lambda_h = (h_att * a_def / AVG_LEAGUE_GOALS) * HOME_ADVANTAGE_FACTOR
    lambda_a = (a_att * h_def / AVG_LEAGUE_GOALS) / HOME_ADVANTAGE_FACTOR
    
    # Ajuste por Danger Signals (Tiros a Puerta)
    if danger and isinstance(danger, dict):
        home_sot = danger.get("home_sot")
        away_sot = danger.get("away_sot")
        SOT_AVG = 4.5
        
        if home_sot is not None:
            adj_h = 1.0 + 0.15 * ((safe_float(home_sot) - SOT_AVG) / SOT_AVG)
            lambda_h *= max(0.7, min(1.3, adj_h))
            
        if away_sot is not None:
            adj_a = 1.0 + 0.15 * ((safe_float(away_sot) - SOT_AVG) / SOT_AVG)
            lambda_a *= max(0.7, min(1.3, adj_a))
            
    # Ajuste por Elo Rating
    elo_home = hd.get("elo") if isinstance(hd, dict) else None
    elo_away = ad.get("elo") if isinstance(ad, dict) else None
    if elo_home is not None and elo_away is not None:
        elo_diff = elo_home - elo_away
        adj_h = 1.0 + 0.0005 * elo_diff
        adj_a = 1.0 - 0.0005 * elo_diff
        lambda_h *= max(0.8, min(1.2, adj_h))
        lambda_a *= max(0.8, min(1.2, adj_a))
            
    lambda_h = max(0.1, min(6.0, lambda_h))
    lambda_a = max(0.1, min(6.0, lambda_a))
    
    # λ total es la suma de ambos
    lambda_total = lambda_h + lambda_a
    
    def poisson_over(lam, threshold):
        if lam <= 0: return 0.0
        p_under = sum((lam**k * math.exp(-lam)) / math.factorial(k) for k in range(int(threshold) + 1))
        return round(1 - p_under, 4)
        
    o25 = poisson_over(lambda_total, 2)
    o15 = poisson_over(lambda_total, 1)

    favorite = "home" if p_win >= p_lose else "away"
    p_dnb_home = p_win  / (p_win  + p_draw) if (p_win  + p_draw) > 0 else 0.0
    p_dnb_away = p_lose / (p_lose + p_draw) if (p_lose + p_draw) > 0 else 0.0

    return {
        "win_home": p_win,  "draw": p_draw, "win_away": p_lose,
        "dnb_home": p_dnb_home, "dnb_away": p_dnb_away,
        "dc_home":  p_win + p_draw, "dc_away":  p_lose + p_draw,
        "over_2_5": o25, "over_1_5": o15,
        "favorite": favorite, "hp_raw": hp, "ap_raw": ap, "nba": False,
        "lambda_home": round(lambda_h, 2), "lambda_away": round(lambda_a, 2),
    }


# ══════════════════════════════════════════════════════════════
#  CAPA 2 — Cuotas reales del mercado
# ══════════════════════════════════════════════════════════════
def get_market_odds(home, away, league):
    """Devuelve dict con cuotas del mejor bookmaker disponible, o {} si no hay datos."""
    bk = find_bk_odds(home, away, league, today)
    if not bk:
        return {}

    bk_home = bk.get('win_home')
    bk_away = bk.get('win_away')
    bk_draw = bk.get('draw')

    def _valid(v):
        return v is not None and v > MIN_VALID_ODDS

    def derive_dnb(bk_win, bk_d):
        if not _valid(bk_win) or not _valid(bk_d): return None
        p_win_mkt  = 1 / bk_win
        p_draw_mkt = 1 / bk_d
        denom = p_win_mkt + p_draw_mkt
        return round(1 / (p_win_mkt / denom), 3) if denom > 0 else None

    def derive_dc(bk_win, bk_d):
        if not _valid(bk_win) or not _valid(bk_d): return None
        return round((bk_win * bk_d) / (bk_win + bk_d), 3)

    return {
        "win_home": bk_home, "win_away": bk_away, "draw": bk_draw,
        "dnb_home": derive_dnb(bk_home, bk_draw),
        "dnb_away": derive_dnb(bk_away, bk_draw),
        "dc_home":  derive_dc(bk_home, bk_draw),
        "dc_away":  derive_dc(bk_away, bk_draw),
        "over_2_5": bk.get('over_2_5'),
        "over_1_5": bk.get('over_1_5'),
    }


# ══════════════════════════════════════════════════════════════
#  CAPA 3 — Evaluación de valor
# ══════════════════════════════════════════════════════════════
def evaluate_value(probs, odds, home, away, market_freqs=None, league=None):
    """
    Cruza probabilidades del modelo con cuotas reales del mercado.

    Pipeline de ajuste por mercado:
      1. compute_model_confidence(context) → confidence_factor ∈ [CONF_FLOOR, 1.0]
      2. prob_adjusted = prob_original × confidence_factor
      3. ev_raw    = prob_original × bk_odds − 1   (referencia sin ajuste)
      4. ev_model  = prob_adjusted × bk_odds − 1   (tras confidence)
      5. ev_adjusted = ev_model − penalty            (tras liquidez)

    Devuelve lista de dicts para TODOS los mercados evaluados:
      prob_original    — probabilidad del modelo sin ajustar (0–100)
      prob_adjusted    — probabilidad tras confidence_factor (0–100)
      confidence_factor — factor aplicado [CONF_FLOOR, 1.0]
      ev               — EV bruto con prob_original (%)
      ev_model         — EV tras confidence_factor (%)
      penalty          — penalización por liquidez (%)
      ev_adjusted      — EV final de decisión (%)
      label            — nombre del mercado
      bk_odds          — cuota del bookmaker (None si no disponible)
      valid            — True si ev_adjusted pasa MIN_EV y max_ev
      reason           — "ok" | "cuota_baja" | "ev_insuficiente" | "ev_negativo"
                          | "ev_excesivo" | "mercado_no_disponible"

    Orden: válidos primero (Over > DNB > DC > win, luego ev_adjusted desc), luego rechazados.
    """
    if market_freqs is None:
        market_freqs = _compute_market_freqs()

    fav      = probs["favorite"]
    fav_team = home if fav == "home" else away

    # Corrige BUG-4: se evalúan los mercados de AMBOS lados (favorito y
    # underdog), no solo el favorito del modelo. El valor en apuestas suele
    # estar en el underdog cuando el mercado sobrevalúa al favorito.
    def _side_markets(side, team):
        return [
            (probs[f"win_{side}"], team,
             f"win_{side}", MIN_CUOTA_WIN, MAX_EV_H2H),
            (probs[f"dnb_{side}"], f"Apuesta sin empate: {team}",
             f"dnb_{side}", MIN_CUOTA_DNB, MAX_EV_H2H),
            (probs[f"dc_{side}"], f"Doble oportunidad: {team}",
             f"dc_{side}", MIN_CUOTA_DC, MAX_EV_H2H),
        ]

    markets = (
        _side_markets("home", home)
        + _side_markets("away", away)
        + [
            (probs["over_2_5"], "Over 2.5 goles", "over_2_5", MIN_CUOTA_OVER25, MAX_EV_GOALS),
            (probs["over_1_5"], "Over 1.5 goles", "over_1_5", MIN_CUOTA_OVER15, MAX_EV_GOALS),
        ]
    )

    def market_priority(label):
        if "Over" in label:               return 0
        if "sin empate" in label:         return 1
        if "Doble oportunidad" in label:  return 2
        return 3

    def _entry(prob_orig, prob_adj, cf, ev_raw, ev_model, ev_adj, pen, label, bk_o, valid, reason):
        # value_score: métrica de RANKING, no de decisión. Solo se computa para picks "ok".
        # Fórmula: ev_adjusted × confidence_factor × log(bk_odds)
        #  - ev_adjusted: EV principal tras penalties (factor dominante)
        #  - confidence_factor: calidad del modelo para esta liga/mercado
        #  - log(bk_odds): modera cuotas extremas sin ignorar el upside de cuotas altas
        vs = (round(ev_adj * cf * math.log(bk_o), 4)
              if reason == "ok" and bk_o and bk_o > 1 else None)
        return {
            "prob_original":     prob_orig,
            "prob_adjusted":     prob_adj,
            "confidence_factor": cf,
            "ev":                ev_raw,
            "ev_model":          ev_model,
            "penalty":           pen,
            "ev_adjusted":       ev_adj,
            "value_score":       vs,
            "label":             label,
            "bk_odds":           bk_o,
            "valid":             valid,
            "reason":            reason,
        }

    results = []
    for our_p, label, odds_key, min_cuota, max_ev in markets:
        bk_o     = odds.get(odds_key) if odds else None
        freq     = market_freqs.get(odds_key, 1.0)
        penalty  = compute_market_penalty(freq)
        pen_pct  = round(penalty * 100, 1)
        is_goals = odds_key in ("over_2_5", "over_1_5")

        context = {
            "league":      league,
            "freq_market": freq,
            "market_type": "goals" if is_goals else "h2h",
        }
        cf            = compute_model_confidence(context)
        # Probabilidad ajustada: si hay calibrador Platt entrenado, se usa la
        # probabilidad CALIBRADA (corrige la sobreconfianza del modelo). Si no,
        # se degrada al ajuste por confidence_factor (comportamiento anterior).
        if _CALIBRATOR:
            prob_adj = platt_probability(our_p, _CALIBRATOR["A"], _CALIBRATOR["B"])
        else:
            prob_adj = our_p * cf
        prob_orig_pct = round(our_p    * 100, 1)
        prob_adj_pct  = round(prob_adj * 100, 1)

        if bk_o is None:
            results.append(_entry(prob_orig_pct, prob_adj_pct, cf,
                                  None, None, None, None,
                                  label, None, False, "mercado_no_disponible"))
            continue

        if bk_o < min_cuota:
            results.append(_entry(prob_orig_pct, prob_adj_pct, cf,
                                  None, None, None, pen_pct,
                                  label, bk_o, False, "cuota_baja"))
            continue

        ev_raw   = round(our_p    * bk_o - 1, 4)
        ev_model = round(prob_adj * bk_o - 1, 4)
        ev_final = round(ev_model - penalty,   4)

        ev_raw_pct   = round(ev_raw   * 100, 1)
        ev_model_pct = round(ev_model * 100, 1)
        ev_final_pct = round(ev_final * 100, 1)

        # reason deriva exclusivamente de ev_final (pipeline completo).
        # Corrige BUG-3: se eliminó el rechazo "ev_excesivo" (EV > max_ev).
        # Descartar los picks de mayor EV no tenía sustento; si hay overfit se
        # ataca con calibración, no con un techo arbitrario. `max_ev` ya no se
        # usa para rechazar aquí.
        if ev_final < 0:
            reason = "ev_negativo"
        elif ev_final < MIN_EV:
            reason = "ev_insuficiente"
        else:
            reason = "ok"

        results.append(_entry(prob_orig_pct, prob_adj_pct, cf,
                              ev_raw_pct, ev_model_pct, ev_final_pct, pen_pct,
                              label, bk_o, reason == "ok", reason))

    valid_picks   = [r for r in results if r["valid"]]
    invalid_picks = [r for r in results if not r["valid"]]
    valid_picks.sort(key=lambda r: -(r["value_score"] or 0))
    return valid_picks + invalid_picks


# ══════════════════════════════════════════════════════════════
#  ORQUESTADOR — llama las 3 capas y devuelve el formato interno
# ══════════════════════════════════════════════════════════════
def calc_wp(league, home, hd, away, ad, nba=False, danger=None):
    """Orquesta las 3 capas. Retorna 11-tupla:
    (base_pick, base_prob, display_pick, display_prob, vs, cj, vl, bk_odds,
     confidence_factor, best_eval, all_evals)
    - best_eval: dict completo de evaluate_value() para el pick ganador (None si no hay valor)
    - all_evals: lista completa de todos los mercados evaluados (aceptados y rechazados)
    vs y display_prob usan valores ajustados por confidence + liquidez.
    """
    probs = get_probabilities(hd, ad, nba=nba, danger=danger)
    fav       = probs["favorite"]
    fav_team  = home if fav == "home" else away
    p_win_key = "win_home" if fav == "home" else "win_away"
    base_prob = round(probs[p_win_key] * 100, 1)
    win_key   = p_win_key
    mkt_freqs = _compute_market_freqs()

    if nba:
        odds = get_market_odds(home, away, "NBA")
        if not odds:
            return fav_team, base_prob, fav_team, base_prob, 0, cuota_justa(base_prob), "bajo", None, 1.0, None, []
        bk_win    = odds.get(win_key)
        all_evals = evaluate_value(probs, odds, home, away, mkt_freqs, league="NBA")
        valid     = [p for p in all_evals if p["valid"]]
        if not valid:
            return fav_team, base_prob, fav_team, base_prob, 0, bk_win, "bajo", None, 1.0, None, all_evals
        best   = valid[0]
        ev_out = best["value_score"]
        # base_pick refleja el equipo del pick ELEGIDO (puede ser el underdog
        # tras BUG-4), no siempre el favorito del modelo.
        chosen_team = _rf_favored_team(best["label"], None) or fav_team
        return (chosen_team, base_prob, best["label"], best["prob_adjusted"],
                ev_out, best["bk_odds"], value_level(ev_out), best["bk_odds"],
                best["confidence_factor"], best, all_evals)

    # Fútbol
    odds = get_market_odds(home, away, league)
    if not odds:
        if league == "Liga Colombiana" and base_prob >= COLOMBIA_MIN_CONF:
            return fav_team, base_prob, fav_team, base_prob, 1, None, "estadistico", None, 1.0, None, []
        return fav_team, base_prob, fav_team, base_prob, 0, None, "bajo", None, 1.0, None, []

    bk_win    = odds.get(win_key)
    all_evals = evaluate_value(probs, odds, home, away, mkt_freqs, league=league)
    valid     = [p for p in all_evals if p["valid"]]
    if not valid:
        return fav_team, base_prob, fav_team, base_prob, 0, bk_win, "bajo", None, 1.0, None, all_evals
    best   = valid[0]
    ev_out = best["ev_adjusted"]
    # base_pick refleja el equipo del pick ELEGIDO (puede ser el underdog
    # tras BUG-4), no siempre el favorito del modelo.
    chosen_team = _rf_favored_team(best["label"], None) or fav_team
    return (chosen_team, base_prob, best["label"], best["prob_adjusted"],
            ev_out, best["bk_odds"], value_level(ev_out), best["bk_odds"],
            best["confidence_factor"], best, all_evals)

def article(league, home, hd, away, ad, nba=False, _win=None, _wp=None, _valor=None, _cuota=None, _base_prob=None, _bk_odds=None, _tipo_pick=None, _pick_data=None):
    # Usar valores pre-calculados por calc_wp() para consistencia
    win, wp = _win, _wp
    valor, cuota = _valor, _cuota
    bk_odds = _bk_odds  # cuota real del bookmaker (None si no hay datos)
    # base_prob: probabilidad de la victoria directa — usada en el bloque de valor
    base_prob = _base_prob if _base_prob is not None else wp

    if nba:
        hp, ap = prob_nba(hd, ad)
    else:
        hp, ap = prob_futbol(hd, ad)

    sp = "puntos" if nba else "goles"

    hw   = gs(hd, 'wins', 'won')
    hl   = gs(hd, 'losses', 'lost')
    def avg_g(d, contra=False):
        try:
            pos = d.get('position', {}) if isinstance(d, dict) else {}
            mp = float(pos.get('partidos') or pos.get('gp') or 1)
            if contra:
                gc = float(pos.get('goles_contra') or pos.get('goals_against') or 0)
                return round(gc / mp, 2) if mp > 1 and gc >= 0 else 0
            gf = float(pos.get('goles_favor') or pos.get('goals_for') or 0)
            return round(gf / mp, 2) if mp > 1 and gf > 0 else 0
        except: return 0
    def _avg(d, key):
        if nba:
            v = gs(d, key)
            try: return float(v)
            except: return 0
        # Para fútbol, siempre calcular promedio desde totales
        contra = key in ('avg_points_allowed', 'goals_against')
        return avg_g(d, contra=contra)
    hpts = _avg(hd, 'avg_points')
    hpta = _avg(hd, 'avg_points_allowed')
    aw2  = gs(ad, 'wins', 'won')
    al2  = gs(ad, 'losses', 'lost')
    apts = _avg(ad, 'avg_points')
    apta = _avg(ad, 'avg_points_allowed')

    try:
        tot_txt = round(float(hpts) + float(apts), 1)
    except:
        tot_txt = None

    conf_txt = f"Probabilidad: {wp}%"
    goles_html = goals_section(hd, ad) if not nba else ""

    # ── Textos de análisis concretos con datos reales ──
    if nba:
        # Contexto NBA
        h_rec = f"{hw}-{hl}" if hw != 'N/A' and hl != 'N/A' else "N/A"
        a_rec = f"{aw2}-{al2}" if aw2 != 'N/A' and al2 != 'N/A' else "N/A"
        intro = f"Analizamos el choque de <strong>{league}</strong> entre <strong>{home}</strong> ({h_rec}) y <strong>{away}</strong> ({a_rec}). Nuestro modelo cruza rendimiento ofensivo, defensivo y porcentaje de victorias para identificar si existe valor apostable."
        if win == home:
            analisis_pick = (
                f"<strong>{home}</strong> promedia <strong>{hpts} puntos</strong> anotados y solo "
                f"<strong>{hpta}</strong> recibidos por partido, frente a un <strong>{away}</strong> que anota "
                f"{apts} y recibe {apta}. La diferencia de rendimiento respalda a <strong>{home}</strong> "
                f"con un <strong>{wp}%</strong> de probabilidad estadistica."
            )
        else:
            analisis_pick = (
                f"<strong>{away}</strong> llega como visitante con <strong>{apts} puntos</strong> anotados "
                f"y {apta} recibidos por partido, superando en eficiencia a <strong>{home}</strong> "
                f"({hpts} anotados, {hpta} recibidos). El modelo asigna <strong>{wp}%</strong> de probabilidad "
                f"al triunfo visitante."
            )
        if tot_txt:
            analisis_pick += f" El total proyectado de puntos entre ambos equipos es <strong>{tot_txt}</strong>."
    else:
        # Contexto fútbol
        intro = (
            f"Nuestro motor analiza el partido de <strong>{league}</strong> entre "
            f"<strong>{home}</strong> y <strong>{away}</strong> cruzando posicion en tabla, "
            f"promedio de goles y estadisticas Over/Under de la temporada actual."
        )
        if win in ("Over 1.5 goles", "Over 2.5 goles"):
            hg = hd.get("goals", {})
            ag = ad.get("goals", {})
            key = "over_1_5" if "1.5" in win else "over_2_5"
            h_pct = hg.get(key, "N/A")
            a_pct = ag.get(key, "N/A")
            analisis_pick = (
                f"El mercado de <strong>{win}</strong> es el de mayor respaldo estadistico en este partido. "
                f"<strong>{home}</strong> supera esa barrera en el <strong>{h_pct}</strong> de sus partidos esta temporada, "
                f"mientras que <strong>{away}</strong> lo hace en el <strong>{a_pct}</strong>. "
                f"Combinando ambos historiales, la probabilidad de que el partido tenga mas de "
                f"{'1.5' if '1.5' in win else '2.5'} goles es del <strong>{wp}%</strong> — "
                f"significativamente mas alta que predecir un ganador directo."
            )
        elif win.startswith("Apuesta sin empate:"):
            team = win.replace("Apuesta sin empate:", "").strip()
            direct_prob = round(hp if team == home else ap, 1)
            opp_team = away if team == home else home
            analisis_pick = (
                f"El modelo asigna a <strong>{team}</strong> un <strong>{direct_prob}%</strong> de probabilidad de victoria directa. "
                f"La <strong>apuesta sin empate</strong> elimina el riesgo del empate: si el partido termina igualado, recuperas tu apuesta integra. "
                f"Descontando ese escenario, la probabilidad efectiva a tu favor sube al <strong>{wp}%</strong>. "
                f"Esta linea ofrece mejor cuota que la doble oportunidad con la misma proteccion frente al empate — "
                f"aqui esta la ventaja sobre el bookmaker."
            )
        elif win.startswith("Doble oportunidad:"):
            team = win.replace("Doble oportunidad:", "").strip()
            direct_prob = round(hp if team == home else ap, 1)
            opp_team = away if team == home else home
            opp_wins = aw2 if team == home else hw
            analisis_pick = (
                f"El partido entre <strong>{home}</strong> y <strong>{away}</strong> es disputado — "
                f"la victoria directa de <strong>{team}</strong> tiene un <strong>{direct_prob}%</strong> de probabilidad, "
                f"pero en un enfrentamiento competitivo apostarlo solo seria regalar el escenario del empate. "
                f"La <strong>Doble oportunidad</strong> cubre tanto la victoria de <strong>{team}</strong> "
                f"como el empate, elevando la probabilidad total al <strong>{wp}%</strong>. "
                f"<strong>{opp_team}</strong> registra {opp_wins} victorias esta temporada — rival real, "
                f"pero los datos favorecen a <strong>{team}</strong> sin necesidad de jugarse todo a la victoria directa."
            )
        elif win == home:
            analisis_pick = (
                f"<strong>{home}</strong> acumula <strong>{hw} victorias</strong> en lo que va de temporada "
                f"con un promedio de <strong>{hpts} goles</strong> a favor y solo <strong>{hpta}</strong> en contra por partido. "
                f"Frente a <strong>{away}</strong> ({aw2} victorias, {apts} goles a favor), "
                f"el modelo le asigna una probabilidad de victoria del <strong>{wp}%</strong>."
            )
        else:
            analisis_pick = (
                f"<strong>{away}</strong> llega como visitante con <strong>{aw2} victorias</strong> esta temporada, "
                f"promediando <strong>{apts} goles</strong> anotados y {apta} recibidos por partido. "
                f"Frente a <strong>{home}</strong> ({hw} victorias, {hpts} goles a favor), "
                f"el modelo detecta ventaja visitante con un <strong>{wp}%</strong> de probabilidad."
            )

    # ── Bloque de análisis ──
    if cuota is None:
        # Colombia: solo estadístico, sin referencia de mercado
        valor_html = f"""
<h2>Analisis estadistico</h2>
<p>Nuestro modelo asigna a <strong>{win}</strong> una probabilidad de victoria del <strong>{base_prob}%</strong> basado en estadísticas de la temporada actual. Este pick se publica por confianza estadística — no disponemos de cuotas de mercado verificadas para esta liga.</p>
<div class="sbox">
<div class="srow"><span class="slbl">Probabilidad estimada (modelo)</span><span class="sval" style="color:var(--gold-500)">{base_prob}%</span></div>
<div class="srow"><span class="slbl">Confianza</span><span class="sval" style="color:var(--success)">ALTA (≥70%)</span></div>
</div>"""
    else:
        if valor >= VALUE_ALTO_THRESHOLD:
            valor_label, valor_color = "ALTO", "var(--success)"
            valor_why = (
                f"Nuestro modelo asigna a este resultado una probabilidad del <strong>{base_prob}%</strong>. "
                f"La cuota real de mercado es <strong>{cuota}</strong>, lo que genera una ventaja matematica real sobre el bookmaker."
            )
        else:
            valor_label, valor_color = "MEDIO", "var(--gold-500)"
            valor_why = (
                f"Probabilidad estimada: <strong>{base_prob}%</strong>. "
                f"Cuota real disponible: <strong>{cuota}</strong>. "
                f"El modelo detecta ventaja sobre el bookmaker en este mercado."
            )

        valor_html = f"""
<h2>¿Por que hay valor en este pick?</h2>
<p>{valor_why}</p>
<div class="sbox">
<div class="srow"><span class="slbl">Probabilidad estimada (modelo)</span><span class="sval" style="color:var(--gold-500)">{base_prob}%</span></div>
<div class="srow"><span class="slbl">Cuota real de mercado</span><span class="sval" style="color:var(--white)">{cuota}</span></div>
<div class="srow"><span class="slbl">Nivel de valor</span><span class="sval" style="color:{valor_color}">{valor_label}</span></div>
</div>"""

    if win.startswith("Doble oportunidad:"):
        conservador_tag = '<div class="ptag">Salida conservadora — cubre victoria + empate</div>'
    elif win.startswith("Apuesta sin empate:"):
        conservador_tag = '<div class="ptag">Empate = devolucion de la apuesta</div>'
    else:
        conservador_tag = ""

    # ── Pick del Día: detalle dentro del pbox (cuota + explicación + confianza) ──
    _plbl      = "Pick del Día" if _tipo_pick == "pick_dia" else "Pick de valor"
    _pbox_extra = ""
    if _tipo_pick == "pick_dia" and _pick_data:
        _pd_label = _pick_data.get("market_label", "")
        _pd_prob  = _pick_data.get("prob_adjusted", "—")
        _pd_odds  = _pick_data.get("bk_odds", "—")
        _pd_expl  = _market_explanation_copy(_pd_label)
        _pbox_extra = (
            f'<div style="margin-top:1.2rem;padding-top:1.2rem;'
            f'border-top:1px solid rgba(240,180,41,.15);text-align:left">'
            f'<p style="font-size:.92rem;color:var(--gray-100);line-height:1.7;margin:.3rem 0 1rem">'
            f'Con esta selección ganas si <strong>{_pd_expl}</strong>.</p>'
            f'<div style="display:flex;gap:2.5rem;margin-bottom:.8rem">'
            f'<div>'
            f'<div style="font-size:.6rem;letter-spacing:.2em;text-transform:uppercase;'
            f'color:var(--gray-400);margin-bottom:.2rem">Cuota actual</div>'
            f'<div style="font-family:var(--font-display);font-size:2.2rem;font-weight:800;'
            f'color:var(--success)">{_pd_odds}</div>'
            f'</div>'
            f'<div>'
            f'<div style="font-size:.6rem;letter-spacing:.2em;text-transform:uppercase;'
            f'color:var(--gray-400);margin-bottom:.2rem">Probabilidad</div>'
            f'<div style="font-family:var(--font-display);font-size:2.2rem;font-weight:800;'
            f'color:var(--gold-500)">{_pd_prob}%</div>'
            f'</div>'
            f'</div>'
            f'<div class="srow"><span class="slbl">Tipo de pick</span>'
            f'<span class="sval">Conservador</span></div>'
            f'<div class="srow"><span class="slbl">Nivel de confianza</span>'
            f'<span class="sval" style="color:var(--success)">Alto</span></div>'
            f'<div style="font-size:.75rem;color:var(--gray-400);margin-top:.8rem">'
            f'⚠️ La cuota en tu casa de apuestas puede variar — verifica antes de apostar</div>'
            f'</div>'
        )

    return f"""
<p>{intro}</p>
<h2>Analisis del equipo local: {home}</h2>
<p><strong>{home}</strong> acumula <strong>{hw} victorias y {hl} derrotas</strong> esta temporada. Promedia <strong>{hpts} {sp}</strong> a favor y <strong>{hpta}</strong> en contra por partido.</p>
<div class="sbox">
<div class="srow"><span class="slbl">Victorias</span><span class="sval" style="color:var(--success)">{hw}</span></div>
<div class="srow"><span class="slbl">Derrotas</span><span class="sval" style="color:var(--danger)">{hl}</span></div>
<div class="srow"><span class="slbl">{sp.capitalize()} prom. a favor</span><span class="sval">{hpts}</span></div>
<div class="srow"><span class="slbl">{sp.capitalize()} prom. en contra</span><span class="sval">{hpta}</span></div>
<div class="srow"><span class="slbl">Probabilidad de victoria</span><span class="sval" style="color:var(--gold-500)">{hp}%</span></div>
</div>
<h2>Analisis del equipo visitante: {away}</h2>
<p><strong>{away}</strong> registra <strong>{aw2} victorias y {al2} derrotas</strong>. Promedia <strong>{apts} {sp}</strong> anotados y <strong>{apta}</strong> recibidos por partido.</p>
<div class="sbox">
<div class="srow"><span class="slbl">Victorias</span><span class="sval" style="color:var(--success)">{aw2}</span></div>
<div class="srow"><span class="slbl">Derrotas</span><span class="sval" style="color:var(--danger)">{al2}</span></div>
<div class="srow"><span class="slbl">{sp.capitalize()} prom. a favor</span><span class="sval">{apts}</span></div>
<div class="srow"><span class="slbl">{sp.capitalize()} prom. en contra</span><span class="sval">{apta}</span></div>
<div class="srow"><span class="slbl">Probabilidad de victoria</span><span class="sval" style="color:var(--gold-500)">{ap}%</span></div>
</div>
<h2>Conclusion del analisis</h2>
<p>{analisis_pick}</p>
{valor_html}
<div class="pbox">
<div class="plbl">{_plbl}</div>
<div class="pres">{win}</div>
{conservador_tag}
<div class="pconf">{conf_txt}</div>
{_pbox_extra}
{f'<div style="margin-top:1.2rem;padding-top:1.2rem;border-top:1px solid rgba(240,180,41,.15)"><div style="font-size:.6rem;letter-spacing:.25em;text-transform:uppercase;color:var(--gray-400);margin-bottom:.4rem">Cuota de referencia (mercado europeo)</div><div style="font-family:var(--font-display);font-size:2.5rem;font-weight:800;color:var(--success)">{cuota}</div><div style="font-size:.75rem;color:var(--gray-400);margin-top:.2rem">⚠️ La cuota en tu casa de apuestas puede variar — verifica antes de apostar</div></div>' if cuota and not _pbox_extra else ''}
</div>
{goles_html}
<p><em>Este analisis es generado por nuestro motor estadistico con datos de la temporada actual. Apuesta siempre con responsabilidad y compara cuotas antes de decidir.</em></p>"""

def save(league, home, away, art):
    slug = f"{home}-vs-{away}-{league}-{today}".lower()
    # Eliminar caracteres especiales para URLs limpias
    import unicodedata
    slug = unicodedata.normalize('NFKD', slug)
    slug = slug.encode('ascii', 'ignore').decode('ascii')
    slug = ''.join(c if c.isalnum() or c == '-' else '-' for c in slug)
    slug = '-'.join(filter(None, slug.split('-')))[:100]
    canonical = f"{SITE_URL}/static/predictions/{slug}.html"
    title = f"Prediccion {home} vs {away} - {league} {today_display}"
    desc  = f"Prediccion y analisis de {home} vs {away} en {league} para {today_display}. Probabilidades, estadisticas y pronostico."
    kw    = f"prediccion {home} {away}, pronostico {league}, {home} vs {away} hoy, apuestas {league}"
    html  = HTML.format(
        title=title, desc=desc, kw=kw,
        canonical=canonical, site_url=SITE_URL,
        date_iso=today, adsense=ADSENSE, ga=GA,
        league=league, date=today_display,
        home=home, away=away, article=art
    )
    (OUTPUT_DIR / f"{slug}.html").write_text(html, encoding='utf-8')
    return slug

def _discover_guias_slugs():
    """
    Lee /content/guias/*.md y extrae el slug del frontmatter de cada uno.
    Retorna lista de slugs. Si la carpeta no existe o python-frontmatter
    no está instalado, retorna []. Falla silenciosa: el sitemap no debe
    bloquearse por una guía mal escrita.
    """
    content_dir = Path("content/guias")
    if not content_dir.exists():
        return []
    try:
        import frontmatter
    except ImportError:
        return []
    slugs = []
    for md_path in sorted(content_dir.glob("*.md")):
        try:
            post = frontmatter.load(md_path)
            slug = post.metadata.get("slug")
            if slug:
                slugs.append(slug)
        except Exception:
            continue  # archivo malformado: omite, no rompe el cron
    return slugs


def generate_sitemap(slugs):
    """Genera sitemap.xml con todas las URLs del sitio (incluye páginas de contenido SEO)."""
    static_urls = [
        f"{SITE_URL}/index.html",
        f"{SITE_URL}/static/predictions/index.html",
        f"{SITE_URL}/privacy.html",
    ]
    # Páginas de contenido educativo (críticas para AdSense)
    content_urls = [
        f"{SITE_URL}/metodologia.html",
        f"{SITE_URL}/glosario.html",
        f"{SITE_URL}/como-interpretar.html",
        f"{SITE_URL}/historial.html",
        f"{SITE_URL}/guias/",
        f"{SITE_URL}/about.html",
    ]
    # Guías individuales (descubiertas leyendo /content/guias/*.md)
    guias_slugs = _discover_guias_slugs()
    guias_urls  = [f"{SITE_URL}/guias/{s}.html" for s in guias_slugs]
    pred_urls   = [f"{SITE_URL}/static/predictions/{s}.html" for s in slugs]
    all_urls    = static_urls + content_urls + guias_urls + pred_urls

    def _priority(url):
        if url == f"{SITE_URL}/index.html":
            return "1.0"
        if url in content_urls:
            # Páginas de contenido importantes para SEO y AdSense
            if "metodologia" in url:       return "0.9"
            if "historial" in url:         return "0.9"
            if url.endswith("/guias/"):    return "0.85"
            if "glosario" in url:          return "0.8"
            if "como-interpretar" in url:  return "0.8"
            return "0.6"  # about
        if url in guias_urls:
            return "0.7"
        if "predictions" in url and "index" not in url:
            return "0.9"
        return "0.7"

    def _changefreq(url):
        # historial cambia diario (cron lo regenera con nuevos verificados)
        if "historial" in url:
            return "daily"
        # Resto del contenido educativo cambia poco → monthly
        if url in content_urls or url in guias_urls:
            return "monthly"
        return "daily"

    entries = "\n".join(
        f"""  <url>
    <loc>{u}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{_changefreq(u)}</changefreq>
    <priority>{_priority(u)}</priority>
  </url>"""
        for u in all_urls
    )

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>"""

    Path("sitemap.xml").write_text(sitemap, encoding='utf-8')
    print(f"   sitemap.xml → {len(all_urls)} URLs ({len(guias_urls)} guías)")

def generate_robots():
    """Genera robots.txt permitiendo todo e indicando el sitemap."""
    robots = f"""User-agent: *
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
"""
    Path("robots.txt").write_text(robots, encoding='utf-8')
    print("   robots.txt generado")

# ══════════════════════════════════════════════════════════════
#  CAPA DE COPY — Texto automático de presentación
#  Estas funciones NO calculan nada.
#  Reciben datos del motor y devuelven texto plano formateado.
# ══════════════════════════════════════════════════════════════

# Tabla de conversión: market_label → explicación en lenguaje humano
def _market_explanation_copy(label: str) -> str:
    lbl = (label or "").strip()
    low = lbl.lower()
    if low.startswith("doble oportunidad:"):
        team = lbl.split(":", 1)[1].strip()
        return f"{team} gana o empata"
    if low.startswith("apuesta sin empate:"):
        team = lbl.split(":", 1)[1].strip()
        return f"{team} gana — si hay empate, se devuelve la apuesta"
    if "over 1.5" in low:
        return "se marcan 2 o más goles en el partido"
    if "over 2.5" in low:
        return "se marcan 3 o más goles en el partido"
    return f"{lbl} gana el partido"   # 1X2 directo


def render_pick_dia_copy(pick: dict) -> str:
    """
    Genera el bloque de copy del Pick del Día.
    Entrada: dict con home, away, league, market_label (o prediccion),
             prob_adjusted (o probabilidad_modelo), bk_odds (o cuota_justa).
    Salida: texto plano, sin HTML.
    """
    home   = pick.get("home", "")
    away   = pick.get("away", "")
    league = pick.get("league", "")
    label  = (pick.get("market_label") or pick.get("prediccion") or "").strip()
    prob   = pick.get("prob_adjusted") or pick.get("probabilidad_modelo") or "—"
    odds   = pick.get("bk_odds") or pick.get("cuota_justa") or "—"
    expl   = _market_explanation_copy(label)
    extra_ctx = pick.get("extra_context", "")
    sep    = "═" * 43
    dash   = "─" * 43
    lines = [
        sep,
        "EL PICK MÁS CONFIABLE DE HOY",
        sep,
        "",
        f"{home} vs {away}",
        f"{league}",
        "",
        dash,
        f"RECOMENDACIÓN DEL SISTEMA: {label}",
        dash,
        "",
        f"Con esta selección ganas si {expl}.",
        "",
        f"  Probabilidad estimada:  {prob}%",
        f"  Cuota actual:           {odds}",
        "  Tipo de pick:           Conservador",
        "  Nivel de confianza:     Alto (según datos actuales)",
        "",
        "Por qué tiene sentido:",
        "  · Alta consistencia reciente del equipo seleccionado.",
        "  · Ventaja estadística clara frente al rival según datos actuales.",
        "  · Mercado de bajo riesgo, diseñado para reducir la variabilidad.",
    ]
    if extra_ctx:
        lines += ["", "Contexto adicional (datos externos):", extra_ctx]
    lines += [
        "",
        "Este pick es el único seleccionado hoy como la opción",
        "con mayor probabilidad real según nuestros criterios de seguridad.",
        sep,
    ]
    return "\n".join(lines)


def render_pick_extra_copy(picks: list) -> str:
    """
    Genera el bloque de copy de todos los Picks Extra.
    Entrada: lista de dicts con home, away, market_label (o prediccion), bk_odds (o cuota_justa).
    Salida: texto plano, sin HTML.
    """
    if not picks:
        return ""
    dash = "─" * 43
    lines = [
        dash,
        "PICKS EXTRA PARA QUIEN QUIERA ALGO MÁS",
        dash,
        "",
        "Además del Pick del Día, dejamos algunas opciones adicionales",
        "para quienes quieran intentar algo diferente.",
        "Estos picks implican más riesgo y NO son el foco principal.",
    ]
    for p in picks:
        label = (p.get("market_label") or p.get("prediccion") or "").strip()
        odds  = p.get("bk_odds") or p.get("cuota_justa") or "—"
        lines += [
            "",
            "· · ·",
            "",
            f"{p.get('home', '')} vs {p.get('away', '')}",
            f"Mercado: {label} @ {odds}",
            "",
            "Opción con mayor riesgo, pero con lógica estadística detrás.",
            "Recomendado solo como complemento.",
        ]
    lines += [
        "",
        dash,
        "Recuerda: el Pick del Día es siempre la referencia principal.",
        dash,
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  MVP — PROPS DE JUGADOR NBA
#  Genera candidatos de player props (Over puntos/rebotes/asistencias).
#  Estos props NUNCA pueden ser pick_dia (_es_mercado_vendible los bloquea).
#  Se inyectan como EXTRA en el pipeline existente.
# ══════════════════════════════════════════════════════════════

# Mínimos para generar un prop
_MVP_MIN_GAMES = 5      # partidos mínimos revisados
_MVP_MIN_RATIO = 0.60   # 60% de veces over

# Configuración por stat: (avg_key, stat_api, label_es, min_line, min_avg)
_MVP_PROP_STATS = [
    ("avg_points",   "points",   "puntos",      8.0, 15.0),
    ("avg_rebounds",  "rebounds", "rebotes",     5.0,  6.0),
    ("avg_assists",   "assists",  "asistencias", 4.0,  5.0),
]


def _compute_realistic_line(recent_values: list, season_avg: float) -> float:
    """
    Calcula línea realista a partir de datos recientes.
    base = (avg_recent + median_recent) / 2, luego descuento del 5%
    para que la línea quede ligeramente por debajo del centro
    (simula una línea de casa de apuestas atacable).
    Fallback a season_avg × 0.90 si no hay datos recientes.
    """
    if not recent_values:
        return round(season_avg * 0.90, 1)
    n = len(recent_values)
    avg_recent = sum(recent_values) / n
    sorted_vals = sorted(recent_values)
    if n % 2 == 1:
        median_recent = sorted_vals[n // 2]
    else:
        median_recent = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    base = (avg_recent + median_recent) / 2
    return round(base * 0.95, 1)


def generate_nba_player_props(nba_games, nba_teams_data):
    """
    MVP: genera candidatos de props NBA (Over puntos/rebotes/asistencias).
    Retorna lista de tuplas compatibles con el pipeline de candidatos (18 elementos).

    Flujo por partido:
      1. Identifica 1 estrella por equipo por stat
      2. Consulta nba_players_api para game logs recientes
      3. Calcula línea realista: (avg_recent + median_recent) / 2
      4. Si ratio >= 60%, datos suficientes, avg >= line → crea candidato
    """
    props = []
    if not nba_games:
        return props

    for home, away in nba_games:
        hd = find(nba_teams_data, home)
        ad = find(nba_teams_data, away)
        if not hd:
            hd = ad
        if not ad:
            ad = hd

        for team_name, team_data, opp_name, opp_data in [
            (home, hd, away, ad),
            (away, ad, home, hd),
        ]:
            players = team_data.get("players", [])
            if not players:
                continue

            available = [p for p in players if p.get("available", True)]
            if not available:
                continue

            # Evaluar cada stat independientemente
            for avg_key, stat_api, label_es, min_line, min_avg in _MVP_PROP_STATS:

                # Encontrar estrella para este stat
                star = max(available, key=lambda p, k=avg_key: p.get(k, 0))
                season_avg = star.get(avg_key, 0)
                if season_avg < min_avg:
                    continue

                star_name = star["name"]

                # Consultar API para game logs reales
                player_ctx = enrich_nba_player_prop(star_name, stat_api, 0)
                # ^ línea=0 temporal para obtener valores recientes sin filtrar

                if not player_ctx or player_ctx.get("games_checked", 0) < _MVP_MIN_GAMES:
                    continue

                recent_values = player_ctx.get("recent_values", [])
                if len(recent_values) < _MVP_MIN_GAMES:
                    continue

                # Calcular línea realista
                line = _compute_realistic_line(recent_values, season_avg)
                if line < min_line:
                    continue

                # Recalcular ratio con la línea real
                times_over = sum(1 for v in recent_values if v > line)
                games_checked = len(recent_values)
                ratio = round(times_over / games_checked, 2)
                avg_recent = round(sum(recent_values) / games_checked, 1)

                # Filtros de calidad
                if ratio < _MVP_MIN_RATIO:
                    continue
                if avg_recent < line:
                    continue

                # Obtener odds reales de props
                prop_odds = get_player_prop_odds(star_name, stat_api, home, away)
                if not prop_odds or not prop_odds.get("odds_over"):
                    continue  # sin odds reales → no crear prop

                bk_odds = prop_odds["odds_over"]
                real_line = prop_odds.get("line", line)

                # Si la API ofrece una línea distinta, usar la del bookmaker
                # y recalcular ratio contra esa línea
                if abs(real_line - line) > 0.5:
                    line = real_line
                    times_over = sum(1 for v in recent_values if v > line)
                    ratio = round(times_over / games_checked, 2)
                    if ratio < _MVP_MIN_RATIO:
                        continue
                    if avg_recent < line:
                        continue

                # Construir prop con odds reales
                p_over = ratio
                prob_pct = round(p_over * 100, 1)
                cf_adj = player_ctx.get("cf_adjustment", 0)
                cf = max(CONF_FLOOR, min(1.0, round(1.0 + cf_adj, 4)))

                ev_adjusted = round(p_over * bk_odds - 1, 4)
                if ev_adjusted <= 0:
                    continue
                value_score = round(ev_adjusted * cf * math.log(bk_odds), 4)

                label = f"Over {line} {label_es}: {star_name}"

                # Copy contextual con datos reales
                stat_short = label_es[:3]
                copy_lines = []
                if times_over >= 4:
                    copy_lines.append(
                        f"{star_name} superó la línea de {line} {stat_short} "
                        f"en {times_over} de sus últimos {games_checked} partidos."
                    )
                elif times_over >= 3:
                    copy_lines.append(
                        f"{star_name} superó {line} {stat_short} "
                        f"en {times_over} de {games_checked} partidos recientes."
                    )
                if avg_recent > line * 1.1:
                    copy_lines.append(
                        f"Promedia {avg_recent} {label_es} en sus últimos "
                        f"{games_checked} partidos (línea: {line})."
                    )

                best_eval = {
                    "label": label,
                    "prob_original": prob_pct,
                    "prob_adjusted": round(prob_pct * cf, 1),
                    "confidence_factor": cf,
                    "bk_odds": bk_odds,
                    "ev_adjusted": ev_adjusted,
                    "value_score": value_score,
                    "valid": True,
                    "reason": "ok",
                    "market_type": "nba_player_prop",
                }

                ext_ctx = {
                    "copy_lines": copy_lines,
                    "player_prop": {
                        "player": star_name,
                        "stat": stat_api,
                        "stat_label": label_es,
                        "line": line,
                        "games_checked": games_checked,
                        "times_over": times_over,
                        "ratio": ratio,
                        "recent_values": recent_values,
                        "avg_recent": avg_recent,
                    },
                    "cf_adjustment": cf_adj,
                }

                # Tupla compatible con el pipeline (18 elementos)
                props.append((
                    value_score,        # [0]  vs
                    "NBA",              # [1]  league
                    team_name,          # [2]  home (equipo del jugador)
                    team_data,          # [3]  hd
                    opp_name,           # [4]  away (rival)
                    opp_data,           # [5]  ad
                    True,               # [6]  nba
                    label,              # [7]  display_pick
                    prob_pct,           # [8]  display_prob
                    bk_odds,            # [9]  cj
                    value_level(value_score),  # [10] vl
                    prob_pct,           # [11] base_prob
                    label,              # [12] base_pick
                    bk_odds,            # [13] bk_odds
                    cf,                 # [14] cf
                    best_eval,          # [15] best_eval
                    [best_eval],        # [16] all_evals
                    ext_ctx,            # [17] ext_ctx
                ))

    return props


# ══════════════════════════════════════════════════════════════
#  CAPA DE PRODUCTO — Pick del día vendible
#  Estas funciones NO tocan el pipeline estadístico.
#  Solo filtran y ordenan candidatos ya validados por el motor.
# ══════════════════════════════════════════════════════════════

def _es_mercado_vendible(label: str) -> bool:
    """
    Retorna True si el mercado es apto para el pick del día vendible.
    Permitidos: DC, 1X2 claro, DNB, Over 1.5.
    Excluidos:  Over 2.5, cualquier 'over' que no sea 1.5, mercados exóticos.
    """
    if not label:
        return False
    lbl = label.lower()
    if "over 2.5"      in lbl: return False   # excluido explícito
    if "over" in lbl and "1.5" not in lbl: return False  # otros overs
    if "doble oportunidad" in lbl: return True   # DC ✓
    if "sin empate"        in lbl: return True   # DNB ✓
    if "over 1.5"          in lbl: return True   # Over 1.5 ✓
    # Si no tiene prefijo especial asumimos que es victoria directa (1X2) ✓
    return True


def _market_simplicity(label: str) -> int:
    """
    Orden de preferencia para desempate entre picks vendibles igualmente válidos.
    Menor número = mercado más simple = preferido.
    DC=0 > 1X2=1 > DNB=2 > Over 1.5=3
    """
    if not label:
        return 9
    lbl = label.lower()
    if "doble oportunidad" in lbl: return 0
    if "sin empate"        in lbl: return 2
    if "over 1.5"          in lbl: return 3
    return 1   # victoria directa u otro


# ══════════════════════════════════════════════════════════════
#  ARQUITECTURA DE 3 NIVELES — Outputs separados por capa
#  Nivel 1: Análisis del Día (todos los partidos, sin filtro EV)
#  Nivel 2: Value Picks (mismos filtros premium/suscripción actuales)
#  Nivel 3: Featured Pick (1 pick estable garantizado, prob ≥55%)
# ══════════════════════════════════════════════════════════════

# Umbrales del Featured Pick (Nivel 3) — DECISIÓN DE PRODUCTO
FEATURED_MIN_PROB = 55.0   # prob_adjusted mínima — bajo de 55% NO se publica
FEATURED_STABLE_MARKETS = {"win_home", "win_away", "dnb_home", "dnb_away",
                            "dc_home", "dc_away"}
# NOTA: Over/Under, BTTS, mercados raros NO califican para featured.
# Razón: el Featured Pick es la "señal estadística más sólida" del día.
# Mercados de goles tienen varianza alta y no son representativos.


def _build_analysis_output(evaluated_picks: list, today_str: str) -> dict:
    """
    Nivel 1 — Análisis del Día.
    Lista TODOS los partidos evaluados con sus probabilidades 1X2 y Over.
    Sin filtro EV, sin recomendación. Es información cruda del modelo.

    Las probabilidades 1X2 se calculan llamando a get_probabilities() que
    retorna las probabilidades crudas del modelo (no las ajustadas por
    confidence_factor, esas son para decisión de pick, no para mostrar).

    Schema:
    {
        "date": "YYYY-MM-DD",
        "total_fixtures": int,
        "matches": [{matchup, league, home, away, probabilities, favorite, ...}]
    }
    """
    matches = []
    api_data = _danger_load_data(today_str)
    for ep in evaluated_picks:
        raw = ep.get("raw")
        if not raw:
            continue
        # raw es la tupla original con (vs, league, home, hd, away, ad, nba, ...)
        # Recalcular probabilidades crudas del modelo
        hd = raw[3]
        ad = raw[5]
        nba = raw[6]
        
        # Recuperar danger signals
        danger_record = api_data.get((_norm(ep.get("home", "")), _norm(ep.get("away", ""))))
        danger = None
        if danger_record:
            home_danger = danger_record.get("home_danger") or {}
            away_danger = danger_record.get("away_danger") or {}
            danger = {
                "home_sot": home_danger.get("shots_on_target_avg"),
                "away_sot": away_danger.get("shots_on_target_avg")
            }
            
        try:
            model_probs = get_probabilities(hd, ad, nba=nba, danger=danger)
        except Exception:
            continue

        # 1X2 (porcentajes redondeados)
        win_home = round(model_probs["win_home"] * 100, 1)
        win_away = round(model_probs["win_away"] * 100, 1)
        draw     = round(model_probs["draw"]     * 100, 1)
        over_2_5 = (round(model_probs["over_2_5"] * 100, 1)
                    if model_probs.get("over_2_5") else None)
        over_1_5 = (round(model_probs["over_1_5"] * 100, 1)
                    if model_probs.get("over_1_5") else None)

        # Determinar favorito por probabilidad mayor
        if win_home >= win_away and win_home >= draw:
            favorite = ep.get("home", "?")
        elif win_away >= win_home and win_away >= draw:
            favorite = ep.get("away", "?")
        else:
            favorite = "Empate técnico"

        matches.append({
            "matchup":           f"{ep.get('home','?')} vs {ep.get('away','?')}",
            "league":            ep.get("league", ""),
            "home":              ep.get("home", "?"),
            "away":              ep.get("away", "?"),
            "probabilities":     {
                "win_home": win_home,
                "draw":     draw,
                "win_away": win_away,
                "over_2_5": over_2_5,
                "over_1_5": over_1_5,
            },
            "favorite":          favorite,
            "stats_complete":    ep.get("stats_complete", False),
            "confidence_factor": ep.get("confidence_factor", 1.0),
            "is_nba":            bool(nba),
            "lambda_home":       model_probs.get("lambda_home"),
            "lambda_away":       model_probs.get("lambda_away"),
            "elo_home":          hd.get("elo") if isinstance(hd, dict) else None,
            "elo_away":          ad.get("elo") if isinstance(ad, dict) else None,
            "danger":            danger,
        })

    return {
        "date":           today_str,
        "total_fixtures": len(matches),
        "matches":        matches,
        "nota":           "Análisis estadístico de todos los partidos del día. "
                          "Probabilidades crudas del modelo (sin ajuste por liga "
                          "ni mercado). No incluye recomendación de apuesta — "
                          "ver value_picks y featured_pick para picks oficiales.",
    }


def _build_featured_pick_output(evaluated_picks: list, value_picks_dict: dict,
                                  today_str: str) -> dict | None:
    """
    Nivel 3 — Featured Pick (Pick Destacado).
    Garantiza 1 pick por día CON umbral mínimo de 55% prob_adjusted en
    mercados estables (1X2, DNB, DC). Si nada cumple, retorna None.

    Reglas:
      1. Filtra evaluated_picks por mercado estable (no Over/Under)
      2. Filtra por prob_adjusted ≥ FEATURED_MIN_PROB (55%)
      3. Ordena por prob_adjusted desc → confidence_factor desc
      4. Retorna el primero (o None si no hay)

    El pick puede coincidir con un value_pick (si lo hay) o ser solo
    estadístico (sin EV+). El campo `tier_origin` distingue:
      - "value_pick" → también es un value pick oficial
      - "statistical_only" → solo estadística sólida, sin EV+
    """
    candidates = []
    for ep in evaluated_picks:
        # Bug auditoría: ligas excluidas tampoco entran a Featured Pick
        if ep.get("league") in EXCLUDED_LEAGUES:
            continue
        # Filtro 1: favoritos con mala forma reciente tampoco entran a Featured
        if ep.get("_rf_rejected"):
            continue
        # Solo mercados estables (h2h)
        market_type = ep.get("market_type", "h2h")
        if market_type != "h2h":
            continue
        # Etiqueta NO debe ser Over/DC/DNB (queremos victoria directa u otra h2h estable)
        label = (ep.get("label") or "").lower()
        if "over" in label:
            continue
        # Umbral mínimo
        prob = ep.get("prob_adjusted") or 0.0
        if prob < FEATURED_MIN_PROB:
            continue
        candidates.append(ep)

    if not candidates:
        return None

    # Ordenar: mayor prob_adjusted desc, desempate por confidence_factor desc
    candidates.sort(
        key=lambda p: (p.get("prob_adjusted") or 0, p.get("confidence_factor") or 0),
        reverse=True
    )
    best = candidates[0]

    # Determinar si es también un value_pick (cruzar con value_picks_dict)
    home, away = best.get("home", ""), best.get("away", "")
    matchup = f"{home} vs {away}"
    is_value_pick = False
    for level_key in ("pick_dia", "pick_gratuito"):
        vp = value_picks_dict.get(level_key)
        if vp and vp.get("matchup") == matchup:
            is_value_pick = True
            break
    if not is_value_pick:
        for vp in value_picks_dict.get("picks_suscripcion", []):
            if vp.get("matchup") == matchup:
                is_value_pick = True
                break

    prob = best.get("prob_adjusted") or 0.0
    if prob >= 70:
        confidence_label = "alta"
    elif prob >= 60:
        confidence_label = "media-alta"
    else:
        confidence_label = "media"

    bk_o   = best.get("bk_odds")
    ev_adj = best.get("ev_adjusted")
    out = {
        "date":              today_str,
        "matchup":           matchup,
        "home":              home,
        "away":              away,
        "league":            best.get("league", ""),
        "market":            best.get("label", ""),
        "prob_adjusted":     round(prob, 1),
        "confidence_factor": best.get("confidence_factor", 1.0),
        "confidence_label":  confidence_label,
        "tier_origin":       "value_pick" if is_value_pick else "statistical_only",
        "bk_odds":           bk_o,
        "ev_adjusted":       ev_adj,
        "nota":              ("Pick destacado del día — máxima confianza estadística"
                              if not is_value_pick else
                              "Pick destacado del día — coincide con un value pick"),
    }
    out.update(_betplay_fields(bk_o, round(prob, 1), ev_adj))
    return out


def _select_confidence_picks(evaluated_picks: list) -> list:
    """Capa de confianza — fallback SIN cuotas reales.

    Cuando el pipeline de EV no produce ningún pick (típico cuando
    odds.json está vacío), selecciona picks por PROBABILIDAD del modelo,
    sin exigir cuota ni EV. Mercados considerados por partido:
      · Favorito a ganar  → prob ≥ CONF_WIN_MIN_PROB (y ≤ CONF_MAX_PROB)
      · Over 1.5 goles     → prob ≥ CONF_OVER15_MIN_PROB (no NBA)
    Respeta EXCLUDED_LEAGUES y el Filtro 1 (forma reciente, _rf_rejected).

    Devuelve hasta CONF_MAX_PICKS tuplas (label, prob, raw) donde `raw`
    es la tupla de 18 elementos lista para entrar a `top`. El raw lleva
    bk_odds=None, vl="estadistico" y un best_eval sintético con
    reason="confianza" (≠"ok", así no lo toca el re-sync de _updated_top).
    """
    cands = []
    for ep in evaluated_picks:
        if ep.get("league") in EXCLUDED_LEAGUES:
            continue
        if ep.get("_rf_rejected"):
            continue
        raw = ep["raw"]
        hd, ad, nba = raw[3], raw[5], raw[6]
        league, home, away = raw[1], raw[2], raw[4]
        cf = ep.get("confidence_factor", 1.0)
        probs = get_probabilities(hd, ad, nba=nba)

        match_markets = []
        # Mercado 1 — favorito a ganar
        fav      = probs.get("favorite")
        win_key  = "win_home" if fav == "home" else "win_away"
        win_prob = round(probs.get(win_key, 0.0) * 100, 1)
        fav_team = home if fav == "home" else away
        if CONF_WIN_MIN_PROB <= win_prob <= CONF_MAX_PROB:
            match_markets.append((fav_team, win_prob))
        # Mercado 2 — Over 1.5 goles (no aplica a NBA)
        if not nba:
            o15 = probs.get("over_1_5")
            if o15 is not None:
                o15_prob = round(o15 * 100, 1)
                if o15_prob >= CONF_OVER15_MIN_PROB:
                    match_markets.append(("Over 1.5 goles", o15_prob))

        if not match_markets:
            continue
        label, prob = max(match_markets, key=lambda m: m[1])
        best_eval = {
            "label": label, "prob_original": prob, "prob_adjusted": prob,
            "confidence_factor": cf, "ev": None, "ev_model": None,
            "penalty": None, "ev_adjusted": None, "value_score": None,
            "bk_odds": None, "valid": False, "reason": "confianza",
        }
        raw_list = list(raw)
        raw_list[0]  = prob            # value_score (sortable, solo display)
        raw_list[7]  = label           # display_pick
        raw_list[8]  = prob            # display_prob
        raw_list[10] = "estadistico"   # value_level
        raw_list[13] = None            # bk_odds
        raw_list[15] = best_eval       # best_eval
        cands.append((label, prob, tuple(raw_list)))

    cands.sort(key=lambda c: c[1], reverse=True)
    return cands   # todos los candidatos; la escalera en main() limita


def _poisson_ge(lam, k):
    """P(X >= k) para X ~ Poisson(lam). Usado para líneas de córners."""
    if lam <= 0 or k <= 0:
        return 0.0
    cdf = 0.0
    term = math.exp(-lam)   # término i=0
    for i in range(0, k):
        if i > 0:
            term *= lam / i
        cdf += term
    return max(0.0, min(1.0, 1.0 - cdf))


def _select_corners_picks(today_matches: list, danger_data: dict) -> list:
    """Línea de córners por confianza — análisis INDEPENDIENTE por mercado.

    Evalúa TODOS los partidos próximos del día (today_matches), sin depender
    del pipeline de goles/ganador. Para cada partido con datos de córners por
    localía (home_danger/away_danger), modela el total como Poisson con
    lambda = corners_avg(local) + corners_avg(visita) y elige la línea MÁS
    ALTA de CONF_CORNERS_LINES cuya P(Over) ≥ CONF_CORNERS_MIN_PROB.

    today_matches: lista de (league, home, away, hd, ad, nba).
    Devuelve hasta CONF_CORNERS_MAX_PICKS tuplas (label, prob, raw), ordenadas
    por total esperado de córners (los partidos más 'corneros' primero)."""
    cands = []
    for (league, home, away, hd, ad, nba) in today_matches:
        if nba or league in EXCLUDED_LEAGUES:   # NBA sin córners; respeta exclusión
            continue
        rec = danger_data.get((_norm(home), _norm(away)))
        if not rec:
            continue
        hd_rec = rec.get("home_danger") or {}
        ad_rec = rec.get("away_danger") or {}
        hd_c = hd_rec.get("corners_avg")
        ad_c = ad_rec.get("corners_avg")
        if hd_c is None or ad_c is None:
            continue
        # Protección: no apostar córners con muestra chica por localía.
        if (hd_rec.get("n_fixtures", 0) < CONF_MIN_SAMPLE_CORNERS
                or ad_rec.get("n_fixtures", 0) < CONF_MIN_SAMPLE_CORNERS):
            continue
        lam = hd_c + ad_c
        chosen = None
        for line in sorted(CONF_CORNERS_LINES, reverse=True):
            prob = round(_poisson_ge(lam, int(line) + 1) * 100, 1)  # Over 8.5 → X≥9
            if prob >= CONF_CORNERS_MIN_PROB:
                chosen = (line, prob)
                break
        if not chosen:
            continue
        line, prob = chosen
        label = f"Over {line} córners"
        best_eval = {
            "label": label, "prob_original": prob, "prob_adjusted": prob,
            "confidence_factor": 1.0, "ev": None, "ev_model": None,
            "penalty": None, "ev_adjusted": None, "value_score": None,
            "bk_odds": None, "valid": False, "reason": "confianza_corners",
        }
        # raw 18-tupla compatible con `top` (con hd/ad reales para renderizado)
        raw = (prob, league, home, hd, away, ad, False, label, prob, None,
               "estadistico", 0.0, "", None, 1.0, best_eval, [], {})
        cands.append((label, prob, raw, lam))

    cands.sort(key=lambda c: c[3], reverse=True)   # más córners esperados primero
    return [(lbl, p, r) for (lbl, p, r, _lam) in cands]   # todos; la escalera limita


def _api_goal_avg(team_stats, side, venue):
    """Promedio de goles de la API-Football. side='for'|'against',
    venue='home'|'away'. Devuelve float o None."""
    try:
        v = (((team_stats or {}).get("goals") or {}).get(side) or {}).get("average", {}).get(venue)
        return float(v) if v not in (None, "") else None
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def _select_over25_picks(today_matches: list, danger_data: dict) -> list:
    """Línea de Over 2.5 goles con datos REALES de API-Football (independiente).

    Para cada partido, usa los promedios de goles POR LOCALÍA:
      λ_local    = (local marca de local      + visitante recibe de visita) / 2
      λ_visita   = (visitante marca de visita  + local recibe de local)     / 2
      λ_total    = λ_local + λ_visita
    P(Over 2.5) = P(Poisson(λ_total) ≥ 3). Publica si ≥ CONF_OVER25_MIN_PROB.

    today_matches: lista de (league, home, away, hd, ad, nba). Solo fútbol."""
    cands = []
    for (league, home, away, hd, ad, nba) in today_matches:
        if nba or league in EXCLUDED_LEAGUES:
            continue
        rec = danger_data.get((_norm(home), _norm(away)))
        if not rec:
            continue
        hs = rec.get("home_stats") or {}
        as_ = rec.get("away_stats") or {}
        # goles esperados por localía
        h_for_home   = _api_goal_avg(hs,  "for",     "home")
        h_against_h  = _api_goal_avg(hs,  "against", "home")
        a_for_away   = _api_goal_avg(as_, "for",     "away")
        a_against_a  = _api_goal_avg(as_, "against", "away")
        if None in (h_for_home, h_against_h, a_for_away, a_against_a):
            continue
        lam_home = (h_for_home + a_against_a) / 2.0
        lam_away = (a_for_away + h_against_h) / 2.0
        lam = lam_home + lam_away
        prob = round(_poisson_ge(lam, 3) * 100, 1)   # Over 2.5 → total ≥ 3
        if prob < CONF_OVER25_MIN_PROB:
            continue
        label = "Over 2.5 goles"
        best_eval = {
            "label": label, "prob_original": prob, "prob_adjusted": prob,
            "confidence_factor": 1.0, "ev": None, "ev_model": None,
            "penalty": None, "ev_adjusted": None, "value_score": None,
            "bk_odds": None, "valid": False, "reason": "confianza_over25_api",
        }
        raw = (prob, league, home, hd, away, ad, False, label, prob, None,
               "estadistico", 0.0, "", None, 1.0, best_eval, [], {})
        cands.append((label, prob, raw, lam))

    cands.sort(key=lambda c: c[3], reverse=True)   # más goles esperados primero
    return [(lbl, p, r) for (lbl, p, r, _lam) in cands]   # todos; la escalera limita


def _conf_market_key(label: str) -> str:
    """Clasifica un pick de confianza por su etiqueta, para ponderar la
    confiabilidad del mercado en la escalera de publicación."""
    l = (label or "").lower()
    if "córners" in l or "corners" in l:
        return "corners"
    if "over 2.5" in l:
        return "over25"
    if "over 1.5" in l:
        return "over15"
    return "win"


def _build_confidence_ladder(evaluated_picks: list, today_matches: list,
                             danger_data: dict) -> list:
    """ESCALERA: junta los candidatos de TODOS los mercados de confianza,
    deja como máximo 1 mercado por partido (el más confiable), y devuelve los
    CONF_PUBLISH_MAX mejores. Pondera por confiabilidad de mercado para que un
    córners de muestra chica no le gane a un Over 1.5 sólido.

    Devuelve lista de (label, prob, raw, market_key), ya ordenada y limitada."""
    pool = []  # (adj_prob, prob, label, raw, market_key, match_key)
    sources = [_select_confidence_picks(evaluated_picks)]
    if CONF_CORNERS_ENABLED:
        sources.append(_select_corners_picks(today_matches, danger_data))
    if CONF_OVER25_ENABLED:
        sources.append(_select_over25_picks(today_matches, danger_data))
    for src in sources:
        for (label, prob, raw) in src:
            mkey = _conf_market_key(label)
            adj = prob * CONF_MARKET_RELIABILITY.get(mkey, 1.0)
            match_key = (_norm(raw[2]), _norm(raw[4]))
            pool.append((adj, prob, label, raw, mkey, match_key))

    # 1 mercado por partido: el de mayor prob ajustada
    pool.sort(key=lambda x: x[0], reverse=True)
    best_by_match = {}
    for item in pool:
        mk = item[5]
        if mk not in best_by_match:
            best_by_match[mk] = item

    ranked = sorted(best_by_match.values(), key=lambda x: x[0], reverse=True)
    return [(it[2], it[1], it[3], it[4]) for it in ranked[:CONF_PUBLISH_MAX]]


def main():
    import sys
    force     = "--force"     in sys.argv
    adicional = "--adicional" in sys.argv   # modo transición: añade 2 picks sin tocar los ya publicados
    preview   = "--preview"   in sys.argv or "--dry-run" in sys.argv  # solo muestra picks, no publica nada

    # Si ya existen picks del día, no regenerar (protege la consistencia).
    # --adicional, --preview y --force omiten este bloqueo.
    _log_path = Path("static/predictions_log.json")
    if not force and not adicional and not preview and _log_path.exists():
        existing = [e for e in json.loads(_log_path.read_text()) if e.get("fecha") == today]
        if existing:
            print(f"✅ Picks del {today} ya publicados ({len(existing)} picks) — sin cambios.")
            print("   Usa --force para regenerar.")
            return

    preds = []
    print(f"Generando predicciones — {today_display}")
    print(f"Hoy: {today} | Acepta hasta {tomorrow} 05:59 UTC\n")

    # ── FASE 1: recopilar todos los candidatos con su score de valor ──
    candidates = []  # tupla de 18 elementos: índice 17 = ext_ctx (contexto API externa)
    api_data = _danger_load_data(today)
    
    # Cargar Elo ratings y mapa de equipos
    elo_path = Path("static/api_football/elo_ratings.json")
    elo_ratings = {}
    if elo_path.exists():
        try:
            elo_ratings = json.loads(elo_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️ Error cargando elo_ratings.json: {e}")

    teams_map_path = Path("static/api_football/teams_map.json")
    teams_map = {}
    if teams_map_path.exists():
        try:
            teams_map = json.loads(teams_map_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️ Error cargando teams_map.json: {e}")

    # Todos los partidos próximos del día (ligas no excluidas), con sus stats.
    # Sirve para análisis INDEPENDIENTE por mercado (ej: córners), sin depender
    # de que el partido pase el filtro de goles. (league, home, away, hd, ad, nba)
    all_today_matches = []

    for code, (league, stats_file) in ESPN_LEAGUES.items():
        matches = espn_fixtures(code)
        if not matches: continue
        stats = load(stats_file)
        league_elos = elo_ratings.get(league, {})
        for home, away in matches:
            hd = find(stats, home); ad = find(stats, away)
            if not hd: hd = ad
            if not ad: ad = hd
            
            if hd:
                hd = dict(hd)
            if ad:
                ad = dict(ad)
                
            home_mapped = teams_map.get(home, {})
            away_mapped = teams_map.get(away, {})
            home_api_name = home_mapped.get("name") or home
            away_api_name = away_mapped.get("name") or away
            
            elo_home = league_elos.get(home_api_name, 1500.0)
            elo_away = league_elos.get(away_api_name, 1500.0)
            
            if hd:
                hd["elo"] = elo_home
            if ad:
                ad["elo"] = elo_away
            
            # Obtener danger signals de la API externa
            danger_record = api_data.get((_norm(home), _norm(away)))
            danger = None
            if danger_record:
                home_danger = danger_record.get("home_danger") or {}
                away_danger = danger_record.get("away_danger") or {}
                danger = {
                    "home_sot": home_danger.get("shots_on_target_avg"),
                    "away_sot": away_danger.get("shots_on_target_avg")
                }
                
            base_pick, base_prob, display_pick, display_prob, vs, cj, vl, bk_odds, cf, best_eval, all_evals = calc_wp(league, home, hd, away, ad, nba=False, danger=danger)
            # Bug auditoría: excluir ligas con yield negativo sostenido del
            # pipeline de value picks. Análisis del Día sigue listándolas.
            if league in EXCLUDED_LEAGUES:
                continue
            all_today_matches.append((league, home, away, hd, ad, False))
            if base_prob >= MIN_CONF_SUBSCRIPTION:
                # Enriquecer con API externa (solo contexto, no decisor)
                ext_ctx = enrich_match_context(home, away, league)
                # Ajustar confidence_factor con dato externo (acotado ±0.03)
                if ext_ctx.get("cf_adjustment"):
                    cf = max(CONF_FLOOR, min(1.0, round(cf + ext_ctx["cf_adjustment"], 4)))
                # Enriquecer corners con TechCorner (solo si el mercado es corners)
                _be_label = ((best_eval or {}).get("label") or "").lower()
                if "corner" in _be_label:
                    corners_ctx = enrich_corners_context(home, away, league, hd, ad)
                    if corners_ctx:
                        ext_ctx = ext_ctx or {}
                        ext_ctx["corners"] = corners_ctx
                        if corners_ctx.get("cf_adjustment"):
                            cf = max(CONF_FLOOR, min(1.0, round(cf + corners_ctx["cf_adjustment"], 4)))
                        ext_ctx.setdefault("copy_lines", []).extend(corners_ctx.get("copy_lines", []))
                candidates.append((vs, league, home, hd, away, ad, False, display_pick, display_prob, cj, vl, base_prob, base_pick, bk_odds, cf, best_eval, all_evals, ext_ctx))

    nba_games = nba_fixtures()
    if nba_games:
        nba_teams = load("nba_stats.json").get("teams", {})
        for home, away in nba_games:
            hd = find(nba_teams, home); ad = find(nba_teams, away)
            if not hd: hd = ad
            if not ad: ad = hd
            base_pick, base_prob, display_pick, display_prob, vs, cj, vl, bk_odds, cf, best_eval, all_evals = calc_wp("NBA", home, hd, away, ad, nba=True)
            if base_prob >= MIN_CONF_SUBSCRIPTION:
                # Enriquecer con API NBA Games (contexto partido/equipo)
                ext_ctx = enrich_nba_game_context(home, away, hd, ad)
                if ext_ctx.get("cf_adjustment"):
                    cf = max(CONF_FLOOR, min(1.0, round(cf + ext_ctx["cf_adjustment"], 4)))
                candidates.append((vs, "NBA", home, hd, away, ad, True, display_pick, display_prob, cj, vl, base_prob, base_pick, bk_odds, cf, best_eval, all_evals, ext_ctx))

    # ── FASE 1b: MVP player props NBA (solo Over puntos, solo extra) ──
    if nba_games:
        _prop_candidates = generate_nba_player_props(nba_games, nba_teams)
        if _prop_candidates:
            candidates.extend(_prop_candidates)
            print(f"      Props NBA generados: {len(_prop_candidates)}")

    # ── FASE 2: selección pick del día + picks premium ──
    #
    # Pick del día (gratuito) — máxima CERTEZA:
    #   Seleccionamos el pick con prob_adjusted más alta entre todos los válidos.
    #   No usamos value_score aquí: cuotas altas no implican más certeza.
    #   Objetivo: 1 pick de alta probabilidad real de cumplirse → retención del usuario.
    #
    # Picks premium — máximo VALUE_SCORE:
    #   Ordenados por ev_adjusted × cf × log(bk_odds) descendente.
    #   Excluye el pick del día para evitar repetición.
    #   Objetivo: maximizar retorno esperado ajustado a largo plazo → ROI del producto.
    #
    # Separar certeza de valor mejora la experiencia:
    #   - El pick del día reduce rachas de derrotas (alta prob real)
    #   - Los premium maximizan el upside de los picks más prometedores
    #   - Nunca se solapan → el usuario recibe señales distintas y complementarias

    # Inicializar análisis de goles (display complementario, se llena en modo normal)
    analisis_goles = []
    # Inicializar evaluated_picks al scope superior para que esté accesible
    # al construir los outputs de Nivel 1 (Análisis) y Nivel 3 (Featured Pick).
    evaluated_picks = []
    # Picks rechazados por Filtro 1 — se loggean al final con tipo_pick="rejected_recent_form"
    rejected_recent_form = []

    if adicional:
        # ── MODO TRANSICIÓN (solo hoy, --adicional) ──
        # Añade 2 picks nuevos sin tocar los ya publicados.
        # No aplica lógica pick_dia ni cap estándar.
        # A partir del próximo ciclo se usa el flujo normal.
        already_published = set()
        if _log_path.exists():
            for e in json.loads(_log_path.read_text()):
                if e.get("fecha") == today:
                    already_published.add(
                        (e.get("home", "").lower(), e.get("away", "").lower())
                    )
        new_valid = [
            c for c in candidates
            if c[0] is not None and c[0] > 0                               # reason == "ok"
            and (c[2].lower(), c[4].lower()) not in already_published      # no publicado hoy
        ]
        new_valid.sort(key=lambda c: c[0], reverse=True)
        top = [("adicional", c) for c in new_valid[:2]]
        print(f"Candidatos totales: {len(candidates)} | Ya publicados hoy: {len(already_published)} | "
              f"Nuevos válidos: {len(new_valid)} | Seleccionados: {len(top)}\n")

    else:
        # ══════════════════════════════════════════════════════════
        #  FASE 2 — Clasificación por perfiles (PRODUCTO, no modelo)
        #  Fórmulas intactas. Solo decide qué se PUBLICA.
        # ══════════════════════════════════════════════════════════

        # ── PASO 2: Recolectar evaluated_picks con metadatos ──
        # Cada candidato se enriquece con campos necesarios para
        # qualifies_for_profile(). No filtra nada todavía.
        evaluated_picks = []
        for c in candidates:
            be = c[15] or {}   # best_eval dict
            all_evals = c[16]  # all evaluations list
            label = be.get("label", "")
            is_goals = "over" in label.lower() if label else False

            # Determinar si ambos equipos tienen stats reales
            hd, ad = c[3], c[5]
            hd_has = bool(hd and hd.get("position", {}).get("partidos"))
            ad_has = bool(ad and ad.get("position", {}).get("partidos"))
            # Para NBA: verificar campo distinto
            if c[6]:  # nba flag
                hd_has = bool(hd and hd.get("wins"))
                ad_has = bool(ad and ad.get("wins"))
            stats_complete = hd_has and ad_has

            evaluated_picks.append({
                "raw":              c,
                "league":           c[1],
                "home":             c[2],
                "away":             c[4],
                "nba":              c[6],
                "prob_adjusted":    be.get("prob_adjusted", 0.0),
                "ev_adjusted":      be.get("ev_adjusted"),
                "value_score":      be.get("value_score") or (c[0] if isinstance(c[0], (int, float)) else 0.0),
                "confidence_factor": be.get("confidence_factor", c[14]),
                "bk_odds":          be.get("bk_odds", c[13]),
                "market_type":      "goals" if is_goals else "h2h",
                "label":            label,
                "stats_complete":   stats_complete,
                "reason":           be.get("reason", "no_eval"),
                "all_evals":        all_evals,
            })

        # ── PASO 3: Funciones de elegibilidad por perfil ──
        def qualifies_for_profile(pick, filters):
            """Función PURA: decide si un pick es elegible para un perfil."""
            # Debe tener reason == "ok" en el pipeline original
            # O tener EV positivo recalculable con los nuevos umbrales
            ev = pick["ev_adjusted"]
            if ev is None or ev <= 0:
                # Revisar all_evals: ¿algún mercado pasa con los nuevos umbrales?
                found = _find_best_market_for_profile(pick, filters)
                if found:
                    # Actualizar el pick con el mercado encontrado
                    pick.update(found)
                    ev = pick["ev_adjusted"]
                else:
                    return False

            if pick["prob_adjusted"] < filters["MIN_PROB"]:
                return False
            if ev < filters["MIN_EV"]:
                return False
            if pick["confidence_factor"] < filters["MIN_CONF_FACTOR"]:
                return False
            if pick["value_score"] < filters["MIN_VS"]:
                return False
            if filters["REQUIRE_BOTH_TEAMS_STATS"] and not pick["stats_complete"]:
                return False

            # BUG-3: se eliminó el techo de EV (max_ev). Ya no se descartan
            # los picks de mayor valor esperado.
            return True

        def _find_best_market_for_profile(pick, filters):
            """Busca en all_evals un mercado que pase con los umbrales del perfil.
            No recalcula EV — usa los valores ya computados por evaluate_value()."""
            best = None
            best_vs = -1
            min_ev = filters["MIN_EV"]

            for e in (pick.get("all_evals") or []):
                ev = e.get("ev_adjusted")
                if ev is None or ev <= 0:
                    continue
                if ev < min_ev:
                    continue
                prob = e.get("prob_adjusted", 0.0)
                if prob < filters["MIN_PROB"]:
                    continue
                cf = e.get("confidence_factor", 0.0)
                if cf < filters["MIN_CONF_FACTOR"]:
                    continue

                # BUG-3: sin techo de EV.
                label = e.get("label", "")
                is_goals = "over" in label.lower()

                vs = e.get("value_score") or 0.0
                # Recalcular value_score si no existe pero EV es válido
                if vs <= 0 and ev > 0 and cf > 0:
                    bk = e.get("bk_odds") or 0
                    vs = round(ev * cf * math.log(max(bk, 1.01)), 4) if bk > 1 else 0.0

                if vs > best_vs:
                    best_vs = vs
                    best = {
                        "prob_adjusted":    prob,
                        "ev_adjusted":      ev,
                        "value_score":      vs,
                        "confidence_factor": cf,
                        "bk_odds":          e.get("bk_odds"),
                        "label":            label,
                        "market_type":      "goals" if is_goals else "h2h",
                        "reason":           "ok",
                    }
            return best

        # ── Filtro 1 (forma reciente del favorito) ──
        # Marca evaluated_picks con _rf_rejected=True si el favorito tiene
        # <RECENT_FORM_MIN_WINS victorias en sus últimos RECENT_FORM_LOOKBACK
        # partidos en liga doméstica. Si no hay datos → modo conservador.
        rejected_recent_form = _rf_apply_filter(evaluated_picks, today)

        # ── Clasificar candidatos ──
        subscription_candidates = [
            p for p in evaluated_picks
            if qualifies_for_profile(p, FILTERS_SUBSCRIPTION)
            and not p.get("_rf_rejected")
        ]
        premium_candidates = [
            p for p in subscription_candidates
            if qualifies_for_profile(p, FILTERS_PREMIUM)
        ]

        # ── PASO 4: Selección de picks de suscripción ──
        subscription_candidates.sort(key=lambda p: p["value_score"], reverse=True)
        subscription_picks = subscription_candidates[:TIER_SUSCRIPCION_MAX]

        # ── PASO 5: Pick Gratuito (más ESTABLE, no mayor value_score) ──
        # Priorizar: mayor prob_adjusted → mercados entendibles → mayor cf
        def _gratuito_sort_key(p):
            label = p.get("label", "").lower()
            # Mercados entendibles: victoria directa (3), over 1.5 (2), over 2.5 (1), otros (0)
            simplicity = 0
            if "over 1.5" in label:          simplicity = 2
            elif "over 2.5" in label:        simplicity = 1
            elif "doble" not in label and "sin empate" not in label:
                simplicity = 3  # victoria directa
            return (p["prob_adjusted"], simplicity, p["confidence_factor"])

        pick_gratuito = max(subscription_picks, key=_gratuito_sort_key) if subscription_picks else None

        # ══════════════════════════════════════════════════════════
        #  PASO 6 — PICK DEL DÍA (PREMIUM) — Decisión de producto
        # ══════════════════════════════════════════════════════════
        # Regla actualizada (Paso 2 del rediseño comercial):
        # Publicamos pick_dia siempre que exista al menos UN candidato
        # premium, sin importar cuántos picks de suscripción haya.
        #
        # Antes: se exigía len(subscription_picks) >= 2 (bloqueaba días
        # con 1 solo pick excelente). Ahora: el mejor pick premium del
        # día se destaca como Pick del Día aunque sea el único.
        #
        # Si pick_dia coincide con pick_gratuito (caso de 1 solo pick),
        # pick_dia prevalece y reasignamos pick_gratuito al siguiente
        # subscription_pick disponible — o queda None si no hay más.
        pick_dia = None
        if premium_candidates:
            premium_candidates.sort(key=lambda p: p["value_score"], reverse=True)
            pick_dia = premium_candidates[0]

            # Resolver conflicto pick_dia == pick_gratuito (mismo pick)
            if pick_dia is pick_gratuito:
                alt = [p for p in subscription_picks if p is not pick_dia]
                pick_gratuito = max(alt, key=_gratuito_sort_key) if alt else None

        # ══════════════════════════════════════════════════════════
        #  PASO 7 — PICK EXPLORATORIO (fallback de publicación)
        #  Solo si:
        #    · No hay picks de suscripción oficiales (len == 0)
        #    · Hay fixtures hoy en ligas CORE
        #    · Al menos 1 evaluated_pick pasa umbrales exploratorios
        #  NO es premium. NO es suscripción. Es un fallback honesto
        #  para evitar días en blanco en Telegram/web.
        # ══════════════════════════════════════════════════════════
        pick_exploratorio = None

        if not subscription_picks:
            # ¿Hay ligas CORE activas hoy?
            core_active = any(p["league"] in CORE_LEAGUES for p in evaluated_picks)

            if core_active:
                # Buscar en all_evals de cada pick un mercado que cumpla
                # condiciones exploratorias. No recalcula EV — usa valores
                # ya computados por evaluate_value().
                def _is_understandable_market(label):
                    l = (label or "").lower()
                    if "over 1.5" in l or "over 2.5" in l:
                        return True
                    if "sin empate" in l:  # DNB
                        return True
                    if "doble" in l:  # DC no aplica
                        return False
                    # Victoria directa (no tiene prefijo)
                    return "over" not in l

                exploratory_pool = []
                for ep in evaluated_picks:
                    if ep["league"] not in CORE_LEAGUES:
                        continue
                    # Buscar mejor mercado exploratorio en all_evals
                    best_market = None
                    best_vs = -1
                    for e in (ep.get("all_evals") or []):
                        ev = e.get("ev_adjusted")
                        if ev is None or ev < EXPLORATORY_MIN_EV:
                            continue
                        prob = e.get("prob_adjusted", 0.0)
                        if prob < EXPLORATORY_MIN_PROB:
                            continue
                        label = e.get("label", "")
                        if not _is_understandable_market(label):
                            continue
                        cf = e.get("confidence_factor", 0.0)
                        bk = e.get("bk_odds") or 0
                        vs = e.get("value_score") or 0.0
                        if vs <= 0 and bk > 1 and cf > 0:
                            vs = round(ev * cf * math.log(bk), 4)
                        if vs > best_vs:
                            best_vs = vs
                            best_market = {
                                "raw":               ep["raw"],
                                "home":              ep["home"],
                                "away":              ep["away"],
                                "league":            ep["league"],
                                "prob_adjusted":     prob,
                                "ev_adjusted":       ev,
                                "value_score":       vs,
                                "confidence_factor": cf,
                                "bk_odds":           e.get("bk_odds"),
                                "label":             label,
                                "reason":            "ok",
                            }
                    if best_market:
                        exploratory_pool.append(best_market)

                if exploratory_pool:
                    exploratory_pool.sort(key=lambda p: p["value_score"], reverse=True)
                    pick_exploratorio = exploratory_pool[0]
                    print(f"  [EXPLORATORIO] Activado — {pick_exploratorio['label']} "
                          f"prob={pick_exploratorio['prob_adjusted']}% "
                          f"ev={pick_exploratorio['ev_adjusted']}%")

        # ══════════════════════════════════════════════════════════
        #  PASO 8 — ANÁLISIS DE GOLES (display complementario)
        #  Mercados Over con valor moderado que NO ganaron el pick
        #  principal del partido. Se exponen como "insight", no
        #  como pick. NO se publican en Telegram automáticamente.
        # ══════════════════════════════════════════════════════════
        # Set de partidos ya elegidos (para excluirlos)
        _picks_principales = set()
        if pick_dia:
            _picks_principales.add((pick_dia["home"], pick_dia["away"]))
        for p in subscription_picks:
            _picks_principales.add((p["home"], p["away"]))
        if pick_exploratorio:
            _picks_principales.add((pick_exploratorio["home"], pick_exploratorio["away"]))

        _goals_pool = []
        for ep in evaluated_picks:
            if ep["league"] not in GOALS_ANALYSIS_LEAGUES:
                continue
            # Buscar el mejor mercado de goles del partido
            best_goal = None
            best_vs = -1
            for e in (ep.get("all_evals") or []):
                label = (e.get("label") or "")
                if "Over" not in label:
                    continue
                ev = e.get("ev_adjusted")
                if ev is None or ev < GOALS_ANALYSIS_MIN_EV:
                    continue
                prob = e.get("prob_adjusted", 0.0)
                if prob < GOALS_ANALYSIS_MIN_PROB:
                    continue
                cf = e.get("confidence_factor", 0.0)
                if cf < GOALS_ANALYSIS_MIN_CF:
                    continue
                bk = e.get("bk_odds")
                if bk is None:
                    continue
                vs = e.get("value_score") or 0.0
                if vs <= 0 and bk > 1 and cf > 0:
                    vs = round(ev * cf * math.log(bk), 4)
                if vs > best_vs:
                    best_vs = vs
                    best_goal = {
                        "league":             ep["league"],
                        "matchup":            f"{ep['home']} vs {ep['away']}",
                        "home":               ep["home"],
                        "away":               ep["away"],
                        "market":             label,
                        "bk_odds":            bk,
                        "prob_adjusted":      prob,
                        "ev_adjusted":        ev,
                        "confidence_factor":  cf,
                        "value_score":        vs,
                    }
            if best_goal:
                # Excluir si el partido ya tiene pick principal con mercado de goles
                key = (best_goal["home"], best_goal["away"])
                # Si ya es pick principal, verificar si su mercado es de goles
                principal_es_goles = False
                if key in _picks_principales:
                    for ep2 in evaluated_picks:
                        if (ep2["home"], ep2["away"]) == key:
                            if "over" in (ep2.get("label") or "").lower():
                                principal_es_goles = True
                            break
                if not principal_es_goles:
                    _goals_pool.append(best_goal)

        # Ordenar por value_score y limitar a GOALS_ANALYSIS_MAX
        _goals_pool.sort(key=lambda g: g["value_score"], reverse=True)
        analisis_goles = _goals_pool[:GOALS_ANALYSIS_MAX]

        # ── Construir lista final compatible con el resto del pipeline ──
        top = []
        used = set()
        if pick_dia:
            top.append(("pick_dia", pick_dia["raw"]))
            used.add(id(pick_dia))
        for p in subscription_picks:
            if id(p) in used:
                continue
            if p is pick_gratuito:
                top.append(("pick_gratuito", p["raw"]))
            else:
                top.append(("pick_suscripcion", p["raw"]))
            used.add(id(p))
        # Agregar pick exploratorio al final si existe
        if pick_exploratorio:
            top.append(("pick_exploratorio", pick_exploratorio["raw"]))

        # ── Actualizar tupla raw con el mercado elegido por el perfil ──
        # evaluated_pick (o pick_exploratorio) puede haber encontrado un
        # mercado mejor con umbrales más flexibles. Sincronizamos la tupla
        # para que HTML, preview y log reflejen el mercado correcto.
        def _find_profile_pick(raw):
            """Devuelve el dict (evaluated_pick o exploratorio) asociado a raw."""
            if pick_exploratorio and pick_exploratorio["raw"] is raw:
                return pick_exploratorio
            for p in evaluated_picks:
                if p["raw"] is raw:
                    return p
            return None

        _updated_top = []
        for tipo, raw in top:
            ep = _find_profile_pick(raw)
            if ep and ep.get("reason") == "ok" and ep.get("label"):
                target_label = ep["label"]
                matched_eval = None
                for e in raw[16]:
                    if e.get("label") == target_label:
                        matched_eval = e
                        break
                if matched_eval:
                    raw_list = list(raw)
                    raw_list[0]  = ep["value_score"]          # vs (posición 0)
                    raw_list[7]  = ep["label"]                # display_pick
                    raw_list[8]  = ep["prob_adjusted"]        # display_prob
                    raw_list[13] = ep.get("bk_odds")          # bk_odds
                    raw_list[14] = ep["confidence_factor"]    # cf
                    raw_list[15] = matched_eval               # best_eval
                    _updated_top.append((tipo, tuple(raw_list)))
                    continue
            _updated_top.append((tipo, raw))
        top = _updated_top

        # ── CAPA DE CONFIANZA (fallback sin cuotas) ──────────────────
        # Si el pipeline de EV no produjo NINGÚN pick (típico cuando
        # odds.json está vacío), publicamos picks por confianza del
        # modelo. No exige cuota ni EV. El primero va como pick_gratuito
        # (se publica en el canal), el resto como suscripción.
        if CONF_PICK_ENABLED and not top:
            # ESCALERA: junta todos los mercados de confianza (goles, córners,
            # Over 2.5), deja 1 por partido y publica los más confiables.
            _api_data = _danger_load_data(today)
            _ladder = _build_confidence_ladder(
                evaluated_picks, all_today_matches, _api_data)
            for _i, (_lbl, _p, _raw_t, _mk) in enumerate(_ladder):
                _tipo = "pick_gratuito" if _i == 0 else "pick_suscripcion"
                top.append((_tipo, _raw_t))
            if _ladder:
                print("  [ESCALERA confianza] " + " | ".join(
                    f"{_lbl} {_p}% [{_mk}]" for _lbl, _p, _, _mk in _ladder))

        print(f"Candidatos totales: {len(candidates)} | Evaluados: {len(evaluated_picks)} | "
              f"Suscripción elegibles: {len(subscription_candidates)} | Premium elegibles: {len(premium_candidates)} | "
              f"Picks suscripción: {len(subscription_picks)} | Pick día: {1 if pick_dia else 0} | "
              f"Gratuito: {1 if pick_gratuito else 0} | "
              f"Exploratorio: {1 if pick_exploratorio else 0} | "
              f"Análisis goles: {len(analisis_goles)}\n")

    # ── PREVIEW / DRY-RUN: mostrar picks en consola y salir sin publicar nada ──
    if preview:
        print("\n" + "═" * 60)
        print("  PREVIEW — sin publicar nada (--preview / --dry-run)")
        print("═" * 60)
        if is_api_active():
            print("  API fútbol activa (RAPIDAPI_KEY detectada)")
        else:
            print("  API fútbol desactivada (sin key)")
        if is_nba_games_api_active():
            print("  API NBA Games activa (RAPIDAPI_KEY detectada)")
        else:
            print("  API NBA Games desactivada (sin key)")
        if is_nba_players_api_active():
            print("  API NBA Players activa (RAPIDAPI_KEY detectada)")
        else:
            print("  API NBA Players desactivada (sin key)")
        if is_techcorner_active():
            print("  API TechCorner activa (RAPIDAPI_KEY detectada)")
        else:
            print("  API TechCorner desactivada (sin key)")
        if is_nba_props_odds_active():
            print("  API NBA Prop Odds activa (ODDS_API_KEY detectada)")
        else:
            print("  API NBA Prop Odds desactivada (sin key)")
        if not top:
            print("  (sin picks válidos para hoy)")
        _preview_suscripcion = []
        _tipo_labels = {
            "pick_dia": "PICK DEL DÍA (PREMIUM)",
            "pick_gratuito": "PICK GRATUITO (TELEGRAM)",
            "pick_suscripcion": "PICK SUSCRIPCIÓN",
            "pick_exploratorio": "PICK EXPLORATORIO (RIESGO MEDIO)",
        }
        for tipo_pick, (vs, league, home, hd, away, ad, nba, win, wp, cj, vl, base_prob, base_pick, bk_odds, cf, best_eval, all_evals, ext_ctx) in top:
            be = best_eval or {}
            cuota_str = f"@{round(bk_odds, 2)}" if bk_odds else "(sin cuota)"
            pa_str    = f"{be.get('prob_adjusted', wp):.1f}%"
            ev_str    = f"{be.get('ev_adjusted'):.1f}%" if be.get('ev_adjusted') is not None else "—"
            vs_str    = f"{vs:.4f}" if vs is not None else "—"
            mercado   = be.get("label") or win
            print(f"\n[{_tipo_labels.get(tipo_pick, tipo_pick.upper())}]")
            print(f"  {home} vs {away} ({league})")
            print(f"  Mercado:       {mercado} {cuota_str}")
            print(f"  prob_adjusted: {pa_str}")
            print(f"  ev_adjusted:   {ev_str}")
            print(f"  value_score:   {vs_str}")
            print(f"  cf:            {be.get('confidence_factor', cf)}")
            if ext_ctx.get("risk_flags"):
                print(f"  ⚠ riesgos:     {', '.join(ext_ctx['risk_flags'])}")
            if ext_ctx.get("copy_lines"):
                print("  contexto API:")
                for _cl in ext_ctx["copy_lines"]:
                    print(f"    · {_cl}")
            _pick_data = {"home": home, "away": away, "league": league,
                          "market_label": mercado, "prob_adjusted": pa_str.rstrip("%"),
                          "bk_odds": round(bk_odds, 2) if bk_odds else "—"}
            if tipo_pick == "pick_dia":
                print("\n── COPY PICK DEL DÍA (PREMIUM) ──")
                print(render_pick_dia_copy(_pick_data))
            elif tipo_pick == "pick_gratuito":
                print(f"  ★ Este pick se publica en Telegram (gratuito)")
                _preview_suscripcion.append(_pick_data)
            elif tipo_pick == "pick_exploratorio":
                print(f"  ⚠ PICK EXPLORATORIO — riesgo medio")
                print(f"    Hoy no hay valor premium claro — este es el mejor")
                print(f"    pick disponible en ligas CORE con EV positivo.")
            else:
                _preview_suscripcion.append(_pick_data)
        if _preview_suscripcion:
            print("\n── COPY PICKS SUSCRIPCIÓN ──")
            print(render_pick_extra_copy(_preview_suscripcion))

        # ── ANÁLISIS DE GOLES (display complementario, no es pick) ──
        if analisis_goles:
            print("\n── ANÁLISIS DE GOLES ──")
            print("(insight complementario — no es pick oficial)\n")
            for g in analisis_goles:
                ev_label = "moderado" if g["ev_adjusted"] < 12 else "alto"
                print(f"  • {g['matchup']} ({g['league']})")
                print(f"    {g['market']} @{g['bk_odds']}")
                print(f"    Prob: {g['prob_adjusted']:.0f}% | EV: +{g['ev_adjusted']:.1f}% | cf: {g['confidence_factor']}")
                print(f"    Nota: valor {ev_label} en mercado eficiente\n")
        print("\n" + "═" * 60 + "\n")
        return  # ← salida limpia: nada se escribe en disco

    # ── FASE 3: generar HTML solo para los elegidos ──
    for tipo_pick, (vs, league, home, hd, away, ad, nba, win, wp, cj, vl, base_prob, base_pick, bk_odds, cf, best_eval, all_evals, ext_ctx) in top:
        # Solo el pick_dia recibe _pick_data (para inyectar cuota + explicación en su pbox)
        # Los picks extra se renderizan como artículos normales sin copy adicional
        if tipo_pick == "pick_dia":
            _be_d = best_eval or {}
            _pick_data = {
                "market_label": _be_d.get("label", ""),
                "prob_adjusted": round(_be_d.get("prob_adjusted", 0), 1) if _be_d.get("prob_adjusted") else "—",
                "bk_odds": round(bk_odds, 2) if bk_odds else "—",
            }
            # Enriquecer copy del pick del día con contexto externo
            if nba:
                _ext_copy = format_nba_game_context_for_copy(ext_ctx)
            else:
                _ext_copy = format_context_for_copy(ext_ctx)
            if _ext_copy:
                _pick_data["extra_context"] = _ext_copy
        else:
            _pick_data = None
        art = article(league, home, hd, away, ad, nba=nba,
                      _win=win, _wp=wp, _valor=vs, _cuota=cj, _base_prob=base_prob, _bk_odds=bk_odds,
                      _tipo_pick=tipo_pick, _pick_data=_pick_data)
        slug = save(league, home, away, art)
        lg_label = "NBA" if nba else league
        cj_display = round(cj, 2) if cj else None
        preds.append((slug, f"{home} vs {away}", lg_label, round(base_prob,1), cj_display, vs, vl, base_pick, cf, best_eval, all_evals, tipo_pick))
        print(f"   [{tipo_pick}] [{vs:.2f} vs] {home} vs {away} → {win} | base: {base_pick} {base_prob}% | cuota: {cj_display or 'estadístico'} | cf: {cf}")

    _index_path = OUTPUT_DIR / "index.html"

    if adicional and preds and _index_path.exists():
        # Modo transición: inyectar sección adicional en el index.html existente.
        # No se toca el contenido ya publicado; se añade ANTES de </body>.
        adicional_cards = ''.join(
            f'<a href="/static/predictions/{s}.html" class="card">'
            f'<span class="lg">{lg}</span><h3>{m}</h3>'
            f'<span class="lnk">Ver prediccion →</span></a>'
            for s, m, lg, *_ in preds
        )
        adicional_section = (
            '\n<section style="max-width:1000px;margin:2rem auto;padding:0 2rem 3rem">'
            '<h2 style="font-family:var(--font-display);font-size:1.8rem;font-weight:800;'
            'color:var(--white);margin-bottom:.4rem">Picks adicionales</h2>'
            '<p style="color:var(--gray-400);font-size:.85rem;letter-spacing:.2em;'
            'text-transform:uppercase;margin-bottom:1.5rem">'
            'Motor actualizado &mdash; selecci&oacute;n por value score</p>'
            f'<div class="grid">{adicional_cards}</div>'
            '</section>'
        )
        existing_html = _index_path.read_text(encoding="utf-8")
        _index_path.write_text(
            existing_html.replace("</body>", adicional_section + "\n</body>"),
            encoding="utf-8"
        )
        print("Sección adicional inyectada en index.html")
    else:
        # Modo normal: escribe el index completo desde cero.
        # 3 niveles de cards: Premium (dorado), Suscripción (azul), Gratuito (verde)
        def _card_html(entry):
            s, m, lg, prob, cj_d, vs, vl, base_pick, cf, best_eval, all_evals, tipo_pick = entry
            be = best_eval or {}
            market = be.get("label", "")
            odds   = be.get("bk_odds")
            odds_str = f' @ {round(odds, 2)}' if odds else ""
            if tipo_pick == "pick_dia":
                return (
                    f'<a href="/static/predictions/{s}.html" class="card" '
                    f'style="border-color:rgba(240,180,41,.4);border-top:3px solid var(--gold-600)">'
                    f'<span class="lg" style="color:var(--gold-500)">PICK DEL D\u00cdA (PREMIUM) &nbsp;·&nbsp; {lg}</span>'
                    f'<h3>{m}</h3>'
                    f'<div style="font-size:.82rem;color:var(--gray-400);margin:-.2rem 0 .8rem">'
                    f'{market}{odds_str}</div>'
                    f'<span class="lnk">Ver predicci\u00f3n →</span>'
                    f'</a>'
                )
            elif tipo_pick == "pick_gratuito":
                return (
                    f'<a href="/static/predictions/{s}.html" class="card" '
                    f'style="border-color:rgba(34,197,94,.3);border-top:3px solid var(--success)">'
                    f'<span class="lg" style="color:var(--success)">PICK GRATUITO &nbsp;·&nbsp; {lg}</span>'
                    f'<h3>{m}</h3>'
                    f'<div style="font-size:.82rem;color:var(--gray-400);margin:-.2rem 0 .8rem">'
                    f'{market}{odds_str}</div>'
                    f'<span class="lnk">Ver predicci\u00f3n →</span>'
                    f'</a>'
                )
            else:
                return (
                    f'<a href="/static/predictions/{s}.html" class="card" '
                    f'style="border-color:rgba(100,140,200,.2);border-top:3px solid #4a7abf">'
                    f'<span class="lg" style="color:#6b9bd2">SUSCRIPCI\u00d3N &nbsp;·&nbsp; {lg}</span>'
                    f'<h3>{m}</h3>'
                    f'<div style="font-size:.82rem;color:var(--gray-400);margin:-.2rem 0 .8rem">'
                    f'{market}{odds_str}</div>'
                    f'<span class="lnk">Ver predicci\u00f3n →</span>'
                    f'</a>'
                )

        cards = ''.join(_card_html(p) for p in preds) if preds else '<div class="empty"><p>No hay partidos programados hoy.</p></div>'
        _index_path.write_text(
            INDEX.format(date=today_display, adsense=ADSENSE, ga=GA,
                         site_url=SITE_URL, cards=cards),
            encoding='utf-8'
        )

    # ── JSON DIARIO — estructura de 3 niveles ──
    def _pick_to_dict(slug, matchup, league, tipo, best_eval, bk_odds, cf):
        be = best_eval or {}
        bk_o = be.get("bk_odds", bk_odds)
        prob = be.get("prob_adjusted")
        ev   = be.get("ev_adjusted")
        entry = {
            "slug": slug,
            "matchup": matchup,
            "league": league,
            "tipo": tipo,
            "market": be.get("label", ""),
            "prob_adjusted": prob,
            "value_score": be.get("value_score"),
            "confidence_factor": be.get("confidence_factor", cf),
            "ev_adjusted": ev,
            "bk_odds": bk_o,
            # Gestión de capital — Quarter-Kelly. En modo "lectura" el stake
            # real es 0 (no se apuesta); stake_sugerido es solo informativo.
            "stake_sugerido_pct": kelly_stake(prob, bk_o),
            "stake_real_pct":     (kelly_stake(prob, bk_o)
                                   if STAKE_MODE == "activo" else 0.0),
            "stake_modo":         STAKE_MODE,
        }
        entry.update(_betplay_fields(bk_o, prob, ev))
        return entry

    if not adicional:
        # ═══════════════════════════════════════════════════════════
        # NIVEL 2 — VALUE PICKS (única fuente de verdad para picks)
        # ═══════════════════════════════════════════════════════════
        # Shadow mode: el bot lee estos campos y NO publica si shadow_mode=True.
        _shadow = today <= SHADOW_MODE_UNTIL
        value_picks_output = {
            "date": today,
            "model_version": MODEL_VERSION,
            "shadow_mode": _shadow,
            "shadow_until": SHADOW_MODE_UNTIL,
            "pick_dia": None,
            "picks_suscripcion": [],
            "pick_gratuito": None,
            "pick_exploratorio": None,
            "analisis_goles": [],
        }
        if _shadow:
            print(f"  · SHADOW MODE activo hasta {SHADOW_MODE_UNTIL} — "
                  f"el bot no publicará en canales (solo se loguea).")
        for slug, matchup, lg, prob, cj_d, vs, vl, base_pick, cf, best_eval, all_evals, tipo_pick in preds:
            entry = _pick_to_dict(slug, matchup, lg, tipo_pick, best_eval, cj_d, cf)
            if tipo_pick == "pick_dia":
                value_picks_output["pick_dia"] = entry
            elif tipo_pick == "pick_gratuito":
                value_picks_output["pick_gratuito"] = entry
                value_picks_output["picks_suscripcion"].append(entry)
            elif tipo_pick == "pick_suscripcion":
                value_picks_output["picks_suscripcion"].append(entry)
            elif tipo_pick == "pick_exploratorio":
                entry["riesgo"] = "medio"
                entry["nota"] = "Pick exploratorio — hoy no hay valor premium claro"
                value_picks_output["pick_exploratorio"] = entry
                if value_picks_output["pick_gratuito"] is None:
                    value_picks_output["pick_gratuito"] = entry
        for g in analisis_goles:
            entry = {
                "league":             g["league"],
                "matchup":            g["matchup"],
                "market":             g["market"],
                "bk_odds":            g["bk_odds"],
                "prob_adjusted":      g["prob_adjusted"],
                "ev_adjusted":        g["ev_adjusted"],
                "confidence_factor":  g["confidence_factor"],
                "nota":               "Análisis de goles — no es pick oficial",
            }
            entry.update(_betplay_fields(g["bk_odds"], g["prob_adjusted"], g["ev_adjusted"]))
            value_picks_output["analisis_goles"].append(entry)

        _value_picks_path = OUTPUT_DIR / f"value_picks_{today}.json"
        _value_picks_path.write_text(
            json.dumps(value_picks_output, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"  ✓ Nivel 2 (value picks) → {_value_picks_path}")

        # ═══════════════════════════════════════════════════════════
        # daily_picks.json — DERIVADO de value_picks (compatibilidad)
        # Una sola fuente de verdad: el contenido es idéntico a value_picks.
        # ═══════════════════════════════════════════════════════════
        _daily_path = OUTPUT_DIR / "daily_picks.json"
        _daily_path.write_text(
            json.dumps(value_picks_output, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"  ✓ daily_picks.json (derivado) → {_daily_path}")

        # ═══════════════════════════════════════════════════════════
        # NIVEL 1 — ANÁLISIS DEL DÍA (todos los partidos, sin filtros)
        # ═══════════════════════════════════════════════════════════
        analysis_output = _build_analysis_output(evaluated_picks, today)
        _analysis_path = OUTPUT_DIR / f"analysis_{today}.json"
        _analysis_path.write_text(
            json.dumps(analysis_output, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"  ✓ Nivel 1 (análisis del día) → {_analysis_path} "
              f"({analysis_output['total_fixtures']} partidos)")

        # ═══════════════════════════════════════════════════════════
        # NIVEL 3 — FEATURED PICK (1 pick estable garantizado, ≥55%)
        # ═══════════════════════════════════════════════════════════
        featured_output = _build_featured_pick_output(
            evaluated_picks, value_picks_output, today
        )
        if featured_output:
            _featured_path = OUTPUT_DIR / f"featured_pick_{today}.json"
            _featured_path.write_text(
                json.dumps(featured_output, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"  ✓ Nivel 3 (featured pick) → {_featured_path} "
                  f"({featured_output['matchup']} {featured_output['prob_adjusted']}%)")
        else:
            print(f"  ⚠ Nivel 3 (featured pick) → ningún candidato ≥{FEATURED_MIN_PROB}% — no se publica")

    # ── SEO: sitemap y robots ──
    print("\nGenerando archivos SEO...")
    slugs = [s for s, *_ in preds]
    generate_sitemap(slugs)
    generate_robots()

    # --- LOG DE PREDICCIONES DIARIO ---
    import json as _json, re as _re
    from pathlib import Path as _Path
    _log_path = _Path("static/predictions_log.json")
    _log = _json.loads(_log_path.read_text()) if _log_path.exists() else []
    if not adicional:
        # Modo normal: reemplaza las entradas del día (idempotente)
        _log = [e for e in _log if e.get("fecha") != today]
    # Modo adicional: conserva entradas existentes del día y simplemente añade al final
    for slug, matchup, league, _wp, _cj, _vs, _vl, _base_pick, _cf, _best_eval, _all_evals, _tipo_pick in preds:
        parts = matchup.split(" vs ")
        if len(parts) != 2:
            continue
        _pred, _conf = None, None
        try:
            _html = (OUTPUT_DIR / f"{slug}.html").read_text(encoding="utf-8")
            _m = _re.search(r'class="pres">([^<]+)<', _html)
            if _m: _pred = _m.group(1).strip()
            _m2 = _re.search(r'class="pconf">([^<]+)<', _html)
            if _m2: _conf = _m2.group(1).strip()
        except: pass
        # Trazabilidad completa del pick ganador
        _be = _best_eval or {}
        _bk_o   = _be.get("bk_odds", _cj)
        _prob   = _be.get("prob_adjusted")
        _ev_adj = _be.get("ev_adjusted")
        _bp     = _betplay_fields(_bk_o, _prob, _ev_adj)
        _log.append({
            "fecha":             today,
            "slug":              slug,
            "home":              parts[0].strip(),
            "away":              parts[1].strip(),
            "league":            league,
            "prediccion":        _pred,
            "confianza":         _conf,
            "resultado_real":    None,
            "acerto":            None,
            # Pipeline completo del mercado elegido
            "prob_original":     _be.get("prob_original"),
            "confidence_factor": _be.get("confidence_factor", _cf),
            "prob_adjusted":     _prob,
            "bk_odds":           _bk_o,
            "ev":                _be.get("ev"),
            "penalty":           _be.get("penalty"),
            "ev_adjusted":       _ev_adj,
            "value_score":       _be.get("value_score"),
            "reason":            _be.get("reason"),
            # Versión del motor — etiqueta para auditoría longitudinal
            "version":           MODEL_VERSION,
            # Gestión de capital — Quarter-Kelly. Modo "lectura": stake real 0.
            "stake_sugerido_pct": kelly_stake(_prob, _bk_o),
            "stake_real_pct":     (kelly_stake(_prob, _bk_o)
                                   if STAKE_MODE == "activo" else 0.0),
            "stake_modo":         STAKE_MODE,
            # Transparencia Betplay (aditivo)
            "cuota_betplay_estimada": _bp["cuota_betplay_estimada"],
            "ev_betplay_estimado":    _bp["ev_betplay_estimado"],
            # Clasificación del pick
            "tipo_pick":         _tipo_pick,
            # Campos de resumen
            "base_pick":         _base_pick,
            "value_level":       _vl,
            # Todos los mercados evaluados (forma resumida para auditoría/calibración)
            "markets_evaluated": [
                {"market": e["label"], "ev_adjusted": e["ev_adjusted"],
                 "value_score": e["value_score"], "reason": e["reason"]}
                for e in _all_evals
            ],
        })
    # ── Picks rechazados por Filtro 1 (forma reciente del favorito) ──
    # Se loggean para auditoría prospectiva. tipo_pick="rejected_recent_form"
    # los excluye de hit_rate / yield (ver update_results.py).
    if rejected_recent_form:
        for r in rejected_recent_form:
            be = r.get("best_eval") or {}
            _bk_o = r.get("bk_odds")
            _prob = r.get("prob_adjusted")
            _ev_adj = r.get("ev_adjusted")
            _bp = _betplay_fields(_bk_o, _prob, _ev_adj)
            _log.append({
                "fecha":             today,
                "slug":              None,
                "home":              r["home"],
                "away":              r["away"],
                "league":            r["league"],
                "prediccion":        r["label"],
                "confianza":         f"Probabilidad: {_prob}%" if _prob is not None else None,
                "resultado_real":    None,
                "acerto":            None,                  # nunca se llena para rechazados
                "prob_original":     be.get("prob_original"),
                "confidence_factor": r.get("confidence_factor"),
                "prob_adjusted":     _prob,
                "bk_odds":           _bk_o,
                "ev":                be.get("ev"),
                "penalty":           be.get("penalty"),
                "ev_adjusted":       _ev_adj,
                "value_score":       be.get("value_score"),
                "reason":            "rejected_recent_form",
                "version":           MODEL_VERSION,
                "cuota_betplay_estimada": _bp["cuota_betplay_estimada"],
                "ev_betplay_estimado":    _bp["ev_betplay_estimado"],
                "tipo_pick":         "rejected_recent_form",
                "base_pick":         r.get("team"),
                "value_level":       None,
                # Auditoría del filtro
                "rf_wins":           r["wins5"],
                "rf_forma":          r["forma"],
                "markets_evaluated": [],
            })
        print(f"  · Filtro 1: {len(rejected_recent_form)} pick(s) rechazado(s) y loggeado(s)")

    _log_path.write_text(_json.dumps(_log, ensure_ascii=False, indent=2))
    print(f"Log guardado: {len(_log)} predicciones")

    print(f"\n{len(preds)} predicciones generadas!")
    print(f"\nProximo paso: registra tu sitemap en Google Search Console")
    print(f"→ https://search.google.com/search-console")
    print(f"→ Agrega propiedad: {SITE_URL}")
    print(f"→ Envia sitemap: {SITE_URL}/sitemap.xml")

if __name__ == "__main__":
    main()
