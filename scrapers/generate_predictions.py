# VERSION DE PRUEBA - NO PRODUCCION
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
    "Premier League",
    "La Liga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Liga Colombiana",
    "Liga Argentina",
    "NBA",
}

# ── Regla de PICK EXPLORATORIO ──
# Fallback de publicación para evitar días en blanco cuando hay
# ligas CORE activas pero ningún pick pasa suscripción.
# NO es premium, NO es suscripción oficial — es una capa honesta
# de "hoy no hay valor claro pero esto es lo mejor que encontramos".
EXPLORATORY_MIN_PROB = 48.0   # prob_adjusted mínima (%)
EXPLORATORY_MIN_EV   = 5.0    # ev_adjusted mínimo (%)

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
MIN_CUOTA_DC      = 1.20   # cuota mínima para DC (doble oportunidad)
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
HOME_ADVANTAGE_PCT  = 0.10  # ventaja de local (% adicional sobre propio score)
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
    "Premier League":   CONF_LEAGUE_TOP,
    "La Liga":          CONF_LEAGUE_TOP,
    "Serie A":          CONF_LEAGUE_TOP,
    "Bundesliga":       CONF_LEAGUE_TOP,
    "Ligue 1":          CONF_LEAGUE_TOP,
    "Champions League": CONF_LEAGUE_TOP,
    "NBA":              CONF_LEAGUE_TOP,
    "Liga Argentina":      CONF_LEAGUE_MID,
    "Brasileirao":         CONF_LEAGUE_MID,
    "Super Lig":           CONF_LEAGUE_MID,
    "Copa Libertadores":   CONF_LEAGUE_MID,
    "Copa Sudamericana":   CONF_LEAGUE_MID,
    # Liga Colombiana y demás → CONF_LEAGUE_MINOR (default)
}

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
<footer class="ftr">PREDIKTOR 2026 · <a href="/privacy.html" style="color:var(--gray-600);text-decoration:none;">Privacidad</a></footer>
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

def find(stats, name):
    if not stats:
        # Stats vacío (típico en CONMEBOL) → buscar en ligas locales
        fallback = _find_in_local_leagues(name)
        if fallback:
            print(f"      [CONMEBOL fallback] '{name}' encontrado en liga local")
            return fallback
        return {}
    nl = norm(name)
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
    for k in stats:
        if norm(k) == nl: return stats[k]
    for k in stats:
        nk = norm(k)
        if nk in nl or nl in nk: return stats[k]
    words = [w for w in nl.split() if len(w) >= 4]
    for k in stats:
        nk = norm(k)
        if sum(1 for w in words if w in nk) >= 1: return stats[k]
    # No encontrado en stats principal → intentar ligas locales
    fallback = _find_in_local_leagues(name)
    if fallback:
        print(f"      [CONMEBOL fallback] '{name}' encontrado en liga local")
        return fallback
    print(f"      [WARN] '{name}' no encontrado, usando fallback")
    return list(stats.values())[0] if stats else {}

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
def prob_futbol(hd, ad):
    pos_h = hd.get("position", {})
    pos_a = ad.get("position", {})

    h_score = (POSITION_RANGE - safe_float(pos_h.get("posicion"), DEFAULT_POSITION)) * WEIGHT_POSITION * 5
    a_score = (POSITION_RANGE - safe_float(pos_a.get("posicion"), DEFAULT_POSITION)) * WEIGHT_POSITION * 5

    h_games = safe_float(pos_h.get("partidos"), 1) or 1
    a_games = safe_float(pos_a.get("partidos"), 1) or 1
    h_score += (safe_float(pos_h.get("ganados")) / h_games * 100) * WEIGHT_WIN_RATE
    a_score += (safe_float(pos_a.get("ganados")) / a_games * 100) * WEIGHT_WIN_RATE

    h_score += safe_float(pos_h.get("diferencia")) * WEIGHT_GOAL_DIFF
    a_score += safe_float(pos_a.get("diferencia")) * WEIGHT_GOAL_DIFF

    h_score += h_score * HOME_ADVANTAGE_PCT

    total = (h_score + a_score) or 1
    hp = (h_score / total) * 100
    hp = min(MODEL_MAX_PROB, max(MODEL_MIN_PROB, hp))
    ap = round(100 - hp, 1)
    hp = round(hp, 1)

    if abs(hp - ap) < MODEL_DRAW_DIFF:
        return 50.0, 50.0

    return hp, ap

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

def prob_futbol_3way(hd, ad):
    """Modelo de 3 resultados (win%, draw%, lose%) para fútbol.
    Incorpora probabilidad de empate según competitividad del partido."""
    hp, ap = prob_futbol(hd, ad)
    diff = abs(hp - ap)
    # Más parejo → más empates. Rango: 20% (muy desigual) a 30% (50/50)
    # Mínimo 20% refleja la realidad del fútbol: incluso favoritos claros pierden
    # ~20% al empate, lo que hace que DNB tenga siempre cuota >= ~1.25
    draw_pct = max(DRAW_PCT_MIN, DRAW_PCT_MAX - diff * DRAW_DIFF_FACTOR)
    scale = (100.0 - draw_pct) / 100.0
    win  = round(hp * scale, 1)
    lose = round(ap * scale, 1)
    draw = round(100.0 - win - lose, 1)
    return win, draw, lose  # (local_win%, draw%, away_win%)

def goals_section(hd, ad):
    hg = hd.get("goals", {})
    ag = ad.get("goals", {})

    o15 = round((parse_pct(hg.get("over_1_5")) + parse_pct(ag.get("over_1_5"))) / 2, 1)
    o25 = round((parse_pct(hg.get("over_2_5")) + parse_pct(ag.get("over_2_5"))) / 2, 1)

    def cls(p):
        if p >= GOALS_HIGH_PCT: return "high"
        if p >= GOALS_MID_PCT:  return "mid"
        return "low"

    def rec(p):
        if p >= GOALS_HIGH_PCT: return "<strong>Recomendado</strong> · Alta probabilidad"
        if p >= GOALS_MID_PCT:  return "Probabilidad media"
        return "Probabilidad baja"

    c15, c25 = cls(o15), cls(o25)

    return f"""
<div class="goals-section">
<h2>Prediccion de Goles</h2>
<p>Probabilidad de que el partido supere 1.5 o 2.5 goles, basada en el historial de ambos equipos esta temporada.</p>
<div class="goals-grid">
  <div class="goal-card">
    <div class="goal-label">⚽ Over 1.5 goles</div>
    <div class="goal-value {c15}">{o15}%</div>
    <div class="goal-bar-wrap"><div class="goal-bar {c15}" style="width:{min(o15,100)}%"></div></div>
    <div class="goal-rec">{rec(o15)}</div>
  </div>
  <div class="goal-card">
    <div class="goal-label">⚽ Over 2.5 goles</div>
    <div class="goal-value {c25}">{o25}%</div>
    <div class="goal-bar-wrap"><div class="goal-bar {c25}" style="width:{min(o25,100)}%"></div></div>
    <div class="goal-rec">{rec(o25)}</div>
  </div>
</div>
</div>"""

# ══════════════════════════════════════════════════════════════
#  CAPA 1 — Probabilidades puras del modelo
# ══════════════════════════════════════════════════════════════
def get_probabilities(hd, ad, nba=False):
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

    win_3w, draw_3w, lose_3w = prob_futbol_3way(hd, ad)
    hp, ap = prob_futbol(hd, ad)

    def avg_goals_per_game(d):
        pos = d.get('position', {})
        pj = float(pos.get('partidos') or 1)
        gf = float(pos.get('goles_favor') or 0)
        gc = float(pos.get('goles_contra') or 0)
        return (gf + gc) / pj if pj >= 1 else 0.0

    def poisson_over(lam, threshold):
        if lam <= 0: return 0.0
        p_under = sum((lam**k * math.exp(-lam)) / math.factorial(k) for k in range(int(threshold) + 1))
        return round(1 - p_under, 4)

    total_esperado = (avg_goals_per_game(hd) + avg_goals_per_game(ad)) / 2

    if total_esperado > 0:
        o25 = poisson_over(total_esperado, 2)
        o15 = poisson_over(total_esperado, 1)
    else:
        hg, ag = hd.get("goals", {}), ad.get("goals", {})
        def goals_prob_fallback(key):
            h, a = parse_pct(hg.get(key)), parse_pct(ag.get(key))
            if h == 0 and a == 0: return 0.0
            return round((50 + ((h + a) / 2 - 50) * GOALS_FALLBACK_REGRESS) / 100, 4)
        o25 = goals_prob_fallback("over_2_5")
        o15 = goals_prob_fallback("over_1_5")

    p_win  = win_3w  / 100
    p_draw = draw_3w / 100
    p_lose = lose_3w / 100
    favorite = "home" if win_3w >= lose_3w else "away"
    p_dnb_home = p_win  / (p_win  + p_draw) if (p_win  + p_draw) > 0 else 0.0
    p_dnb_away = p_lose / (p_lose + p_draw) if (p_lose + p_draw) > 0 else 0.0

    return {
        "win_home": p_win,  "draw": p_draw, "win_away": p_lose,
        "dnb_home": p_dnb_home, "dnb_away": p_dnb_away,
        "dc_home":  p_win + p_draw, "dc_away": p_lose + p_draw,
        "over_2_5": o25, "over_1_5": o15,
        "favorite": favorite, "hp_raw": hp, "ap_raw": ap, "nba": False,
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

    markets = [
        # (prob, label, odds_key, min_cuota, max_ev)
        (probs["win_home" if fav == "home" else "win_away"],
         fav_team,
         "win_home" if fav == "home" else "win_away",
         MIN_CUOTA_WIN, MAX_EV_H2H),
        (probs["dnb_home" if fav == "home" else "dnb_away"],
         f"Apuesta sin empate: {fav_team}",
         "dnb_home" if fav == "home" else "dnb_away",
         MIN_CUOTA_DNB, MAX_EV_H2H),
        (probs["dc_home" if fav == "home" else "dc_away"],
         f"Doble oportunidad: {fav_team}",
         "dc_home" if fav == "home" else "dc_away",
         MIN_CUOTA_DC, MAX_EV_H2H),
        (probs["over_2_5"], "Over 2.5 goles", "over_2_5", MIN_CUOTA_OVER25, MAX_EV_GOALS),
        (probs["over_1_5"], "Over 1.5 goles", "over_1_5", MIN_CUOTA_OVER15, MAX_EV_GOALS),
    ]

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
        prob_adj      = our_p * cf
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

        # reason deriva exclusivamente de ev_final (pipeline completo)
        if ev_final < 0:
            reason = "ev_negativo"
        elif ev_final < MIN_EV:
            reason = "ev_insuficiente"
        elif ev_final > max_ev:
            reason = "ev_excesivo"
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
def calc_wp(league, home, hd, away, ad, nba=False):
    """Orquesta las 3 capas. Retorna 11-tupla:
    (base_pick, base_prob, display_pick, display_prob, vs, cj, vl, bk_odds,
     confidence_factor, best_eval, all_evals)
    - best_eval: dict completo de evaluate_value() para el pick ganador (None si no hay valor)
    - all_evals: lista completa de todos los mercados evaluados (aceptados y rechazados)
    vs y display_prob usan valores ajustados por confidence + liquidez.
    """
    probs = get_probabilities(hd, ad, nba=nba)
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
        return (fav_team, base_prob, best["label"], best["prob_adjusted"],
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
    return (fav_team, base_prob, best["label"], best["prob_adjusted"],
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
    for ep in evaluated_picks:
        raw = ep.get("raw")
        if not raw:
            continue
        # raw es la tupla original con (vs, league, home, hd, away, ad, nba, ...)
        # Recalcular probabilidades crudas del modelo
        hd = raw[3]
        ad = raw[5]
        nba = raw[6]
        try:
            model_probs = get_probabilities(hd, ad, nba=nba)
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

    for code, (league, stats_file) in ESPN_LEAGUES.items():
        matches = espn_fixtures(code)
        if not matches: continue
        stats = load(stats_file)
        for home, away in matches:
            hd = find(stats, home); ad = find(stats, away)
            if not hd: hd = ad
            if not ad: ad = hd
            base_pick, base_prob, display_pick, display_prob, vs, cj, vl, bk_odds, cf, best_eval, all_evals = calc_wp(league, home, hd, away, ad, nba=False)
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

            # Cap de EV según tipo de mercado
            max_ev = filters["MAX_EV_GOALS"] if pick["market_type"] == "goals" else filters["MAX_EV_H2H"]
            if ev > max_ev:
                return False

            return True

        def _find_best_market_for_profile(pick, filters):
            """Busca en all_evals un mercado que pase con los umbrales del perfil.
            No recalcula EV — usa los valores ya computados por evaluate_value()."""
            best = None
            best_vs = -1
            max_ev_h2h = filters["MAX_EV_H2H"]
            max_ev_goals = filters["MAX_EV_GOALS"]
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

                label = e.get("label", "")
                is_goals = "over" in label.lower()
                max_ev = max_ev_goals if is_goals else max_ev_h2h
                if ev > max_ev:
                    continue

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

        # ── Clasificar candidatos ──
        subscription_candidates = [
            p for p in evaluated_picks
            if qualifies_for_profile(p, FILTERS_SUBSCRIPTION)
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
        }
        entry.update(_betplay_fields(bk_o, prob, ev))
        return entry

    if not adicional:
        # ═══════════════════════════════════════════════════════════
        # NIVEL 2 — VALUE PICKS (única fuente de verdad para picks)
        # ═══════════════════════════════════════════════════════════
        value_picks_output = {
            "date": today,
            "pick_dia": None,
            "picks_suscripcion": [],
            "pick_gratuito": None,
            "pick_exploratorio": None,
            "analisis_goles": [],
        }
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
    _log_path.write_text(_json.dumps(_log, ensure_ascii=False, indent=2))
    print(f"Log guardado: {len(_log)} predicciones")

    print(f"\n{len(preds)} predicciones generadas!")
    print(f"\nProximo paso: registra tu sitemap en Google Search Console")
    print(f"→ https://search.google.com/search-console")
    print(f"→ Agrega propiedad: {SITE_URL}")
    print(f"→ Envia sitemap: {SITE_URL}/sitemap.xml")

if __name__ == "__main__":
    main()
