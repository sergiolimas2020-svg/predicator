import json, os, requests, unicodedata
from datetime import date, timedelta
from pathlib import Path

OUTPUT_DIR = Path("static/predictions")
OUTPUT_DIR.mkdir(exist_ok=True)
today = date.today().strftime("%Y-%m-%d")
tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

MESES = {"January":"enero","February":"febrero","March":"marzo","April":"abril","May":"mayo","June":"junio","July":"julio","August":"agosto","September":"septiembre","October":"octubre","November":"noviembre","December":"diciembre"}
today_display = date.today().strftime("%d de %B de %Y")
for en, es in MESES.items():
    today_display = today_display.replace(en, es)

BALLDONTLIE_KEY = os.environ.get("BALLDONTLIE_KEY", "")

# ── Límite de picks diarios y umbrales de valor ──
MAX_PICKS      = 4    # máximo picks publicados por día
MIN_CONF       = 56.0 # probabilidad mínima (descarta picks demasiado inciertos)
MIN_CUOTA      = 1.40 # cuota justa mínima — por debajo los bookmakers pagan ~1.05-1.20, sin valor real
MAX_CUOTA      = 2.00 # cuota justa máxima — por encima es demasiado incierto

def cuota_justa(wp):
    """Devuelve la cuota decimal justa para una probabilidad wp (%)."""
    if wp <= 0: return 99.0
    return round(100 / wp, 2)

def value_score(wp):
    """
    Score de valor apostable (0-100).
    Zona de valor real: cuota justa 1.40-1.85 (prob 54-71%).
    Por debajo de 1.40 (>71%): favorito aplastante, bookmakers pagan 1.05-1.20, sin valor.
    Por encima de 2.00 (<50%): demasiado incierto, no publicar.
    """
    cj = cuota_justa(wp)
    if wp < MIN_CONF or cj < MIN_CUOTA or cj > MAX_CUOTA:
        return 0
    # Sweet spot 1.45-1.75 (prob 57-69%): máximo valor
    if 1.45 <= cj <= 1.75:
        return round(wp * 1.0, 1)
    # Zona aceptable 1.40-1.44 o 1.76-2.00
    return round(wp * 0.80, 1)

ADSENSE = '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5953880132871590" crossorigin="anonymous"></script>'
GA = '<script async src="https://www.googletagmanager.com/gtag/js?id=G-K3JES4SQS9"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag("js",new Date());gtag("config","G-K3JES4SQS9");</script>'

# ── URL base del sitio en produccion ──
SITE_URL = "https://predicator-sergiolimas2020-svgs-projects.vercel.app"

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
    "Internacional de Bogota FC": "La Equidad",
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
}

def espn_fixtures(code):
    try:
        r = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/{code}/scoreboard", timeout=10)
        matches = []
        for e in r.json().get("events", []):
            event_date_utc = e.get("date", "")
            event_date = event_date_utc[:10]
            event_hour = int(event_date_utc[11:13]) if len(event_date_utc) > 12 else 0
            status = e.get("status", {}).get("type", {}).get("description", "")
            if status in ("Full Time", "Final", "FT"):
                continue
            es_hoy = event_date == today
            es_noche_col = (event_date == tomorrow and event_hour <= 5)
            if not es_hoy and not es_noche_col:
                continue
            cs = e.get("competitions", [{}])[0].get("competitors", [])
            if len(cs) >= 2:
                h = next((c["team"]["displayName"] for c in cs if c.get("homeAway") == "home"), None)
                a = next((c["team"]["displayName"] for c in cs if c.get("homeAway") == "away"), None)
                if h and a:
                    matches.append((h, a))
        return matches
    except Exception as ex:
        print(f"   ESPN error: {ex}"); return []

def nba_fixtures():
    return espn_fixtures("basketball/nba")

def load(f):
    p = Path(f"static/{f}")
    return json.load(open(p)) if p.exists() else {}

def find(stats, name):
    if not stats: return {}
    nl = norm(name)
    if name in TEAM_ALIASES:
        alias = TEAM_ALIASES[name]
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

    h_score = (21 - safe_float(pos_h.get("posicion"), 10)) * 0.4 * 5
    a_score = (21 - safe_float(pos_a.get("posicion"), 10)) * 0.4 * 5

    h_games = safe_float(pos_h.get("partidos"), 1) or 1
    a_games = safe_float(pos_a.get("partidos"), 1) or 1
    h_score += (safe_float(pos_h.get("ganados")) / h_games * 100) * 0.3
    a_score += (safe_float(pos_a.get("ganados")) / a_games * 100) * 0.3

    h_score += safe_float(pos_h.get("diferencia")) * 0.2
    a_score += safe_float(pos_a.get("diferencia")) * 0.2

    h_score += h_score * 0.1

    total = (h_score + a_score) or 1
    hp = (h_score / total) * 100
    hp = min(85.0, max(15.0, hp))
    ap = round(100 - hp, 1)
    hp = round(hp, 1)

    if abs(hp - ap) < 10:
        return 50.0, 50.0

    return hp, ap

# ══════════════════════════════════════════════════════════════
#  NBA — replica index.html bkWinProb()
#  NUNCA retorna empate
# ══════════════════════════════════════════════════════════════
def prob_nba(hd, ad):
    h_win_pct = safe_float(hd.get("win_pct"), 50)
    a_win_pct = safe_float(ad.get("win_pct"), 50)
    h_avg_pts = safe_float(hd.get("avg_points"), 110)
    a_avg_pts = safe_float(ad.get("avg_points"), 110)

    diff = (h_win_pct - a_win_pct) + (h_avg_pts - a_avg_pts) * 0.5 + 3
    hp = min(85.0, max(15.0, 50 + diff))
    ap = round(100 - hp, 1)
    hp = round(hp, 1)
    return hp, ap

def goals_section(hd, ad):
    hg = hd.get("goals", {})
    ag = ad.get("goals", {})

    o15 = round((parse_pct(hg.get("over_1_5")) + parse_pct(ag.get("over_1_5"))) / 2, 1)
    o25 = round((parse_pct(hg.get("over_2_5")) + parse_pct(ag.get("over_2_5"))) / 2, 1)

    def cls(p):
        if p >= 65: return "high"
        if p >= 45: return "mid"
        return "low"

    def rec(p):
        if p >= 65: return "<strong>Recomendado</strong> · Alta probabilidad"
        if p >= 45: return "Probabilidad media"
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

def calc_wp(league, home, hd, away, ad, nba=False):
    """Calcula win/wp sin generar HTML. Retorna (win, wp, valor, cuota)."""
    if nba:
        hp, ap = prob_nba(hd, ad)
        win, wp = (home, hp) if hp >= ap else (away, ap)
    else:
        hp, ap = prob_futbol(hd, ad)
        hg = hd.get("goals", {})
        ag = ad.get("goals", {})
        o15 = round((parse_pct(hg.get("over_1_5")) + parse_pct(ag.get("over_1_5"))) / 2, 1)
        o25 = round((parse_pct(hg.get("over_2_5")) + parse_pct(ag.get("over_2_5"))) / 2, 1)
        if abs(hp - ap) < 10:
            win_prob, win_team = 33.0, "EMPATE"
        elif hp >= ap:
            win_prob, win_team = hp, home
        else:
            win_prob, win_team = ap, away
        mercados = [("Over 1.5 goles", o15), ("Over 2.5 goles", o25), (win_team, win_prob)]
        mercados.sort(key=lambda x: x[1], reverse=True)
        win, wp = mercados[0]
        if win == "EMPATE" and o15 > 33:
            win, wp = ("Over 1.5 goles", o15) if o15 >= o25 else ("Over 2.5 goles", o25)
    vs = value_score(wp)
    cj = cuota_justa(wp)
    return win, wp, vs, cj

def article(league, home, hd, away, ad, nba=False, _win=None, _wp=None, _valor=None, _cuota=None):
    # Usar valores pre-calculados por calc_wp() para consistencia
    win, wp = _win, _wp
    valor, cuota = _valor, _cuota

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

    # ── Bloque ¿Por qué hay valor aquí? ──
    if valor >= 60:
        valor_label = "ALTO"
        valor_color = "var(--success)"
        valor_why = (
            f"Nuestra probabilidad estadistica es <strong>{wp}%</strong>, lo que equivale a una cuota justa de "
            f"<strong>{cuota}</strong>. Esto significa que si encuentras este mercado en tu bookmaker a una cuota "
            f"igual o superior a <strong>{cuota}</strong>, matematicamente hay valor a tu favor. "
            f"Los mercados con probabilidades en este rango (60-71%) son los que los bookmakers "
            f"suelen sub-valorar frente a los grandes favoritos — aqui esta la oportunidad."
        )
    else:
        valor_label = "MEDIO"
        valor_color = "var(--gold-500)"
        valor_why = (
            f"Nuestra probabilidad es <strong>{wp}%</strong> (cuota justa <strong>{cuota}</strong>). "
            f"Hay margen de valor si el bookmaker ofrece una cuota igual o superior. "
            f"Recomendamos comparar lineas en al menos dos casas antes de apostar — "
            f"una diferencia de 0.05-0.10 en la cuota puede ser la diferencia entre valor positivo y negativo."
        )

    valor_html = f"""
<h2>¿Por que hay valor en este pick?</h2>
<p>{valor_why}</p>
<div class="sbox">
<div class="srow"><span class="slbl">Probabilidad estimada (modelo)</span><span class="sval" style="color:var(--gold-500)">{wp}%</span></div>
<div class="srow"><span class="slbl">Cuota minima con valor</span><span class="sval" style="color:var(--white)">{cuota}</span></div>
<div class="srow"><span class="slbl">Nivel de valor</span><span class="sval" style="color:{valor_color}">{valor_label}</span></div>
</div>"""

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
<div class="plbl">Pick de valor</div>
<div class="pres">{win}</div>
<div class="pconf">{conf_txt}</div>
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

def generate_sitemap(slugs):
    """Genera sitemap.xml con todas las URLs del sitio."""
    static_urls = [
        f"{SITE_URL}/index.html",
        f"{SITE_URL}/static/predictions/index.html",
        f"{SITE_URL}/privacy.html",
    ]
    pred_urls = [f"{SITE_URL}/static/predictions/{s}.html" for s in slugs]
    all_urls  = static_urls + pred_urls

    entries = "\n".join(
        f"""  <url>
    <loc>{u}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>{"1.0" if u == f"{SITE_URL}/index.html" else "0.9" if "predictions" in u and "index" not in u else "0.7"}</priority>
  </url>"""
        for u in all_urls
    )

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>"""

    Path("sitemap.xml").write_text(sitemap, encoding='utf-8')
    print(f"   sitemap.xml → {len(all_urls)} URLs")

def generate_robots():
    """Genera robots.txt permitiendo todo e indicando el sitemap."""
    robots = f"""User-agent: *
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
"""
    Path("robots.txt").write_text(robots, encoding='utf-8')
    print("   robots.txt generado")

def main():
    preds = []
    print(f"Generando predicciones — {today_display}")
    print(f"Hoy: {today} | Acepta hasta {tomorrow} 05:59 UTC\n")

    # ── FASE 1: recopilar todos los candidatos con su score de valor ──
    candidates = []  # (valor_score, league, home, hd, away, ad, nba, win, wp, cuota)

    for code, (league, stats_file) in ESPN_LEAGUES.items():
        matches = espn_fixtures(code)
        if not matches: continue
        stats = load(stats_file)
        for home, away in matches:
            hd = find(stats, home); ad = find(stats, away)
            if not hd: hd = ad
            if not ad: ad = hd
            win, wp, vs, cj = calc_wp(league, home, hd, away, ad, nba=False)
            if wp >= MIN_CONF:
                candidates.append((vs, league, home, hd, away, ad, False, win, wp, cj))

    nba_games = nba_fixtures()
    if nba_games:
        nba_teams = load("nba_stats.json").get("teams", {})
        for home, away in nba_games:
            hd = find(nba_teams, home); ad = find(nba_teams, away)
            if not hd: hd = ad
            if not ad: ad = hd
            win, wp, vs, cj = calc_wp("NBA", home, hd, away, ad, nba=True)
            if wp >= MIN_CONF:
                candidates.append((vs, "NBA", home, hd, away, ad, True, win, wp, cj))

    # ── FASE 2: ordenar por valor y tomar los MAX_PICKS mejores ──
    candidates.sort(key=lambda x: x[0], reverse=True)
    # Descartar picks sin valor real (score 0 = favorito aplastante o demasiado incierto)
    top = [c for c in candidates if c[0] > 0][:MAX_PICKS]

    print(f"Candidatos totales: {len(candidates)} | Publicando top {len(top)} por valor\n")

    # ── FASE 3: generar HTML solo para los elegidos ──
    for vs, league, home, hd, away, ad, nba, win, wp, cj in top:
        art = article(league, home, hd, away, ad, nba=nba,
                      _win=win, _wp=wp, _valor=vs, _cuota=cj)
        slug = save(league, home, away, art)
        lg_label = "NBA" if nba else league
        preds.append((slug, f"{home} vs {away}", lg_label))
        print(f"   [{vs:.0f}pts valor] {home} vs {away} → {win} ({wp}%) cuota justa {cj}")

    cards = ''.join(
        f'<a href="/static/predictions/{s}.html" class="card"><span class="lg">{lg}</span><h3>{m}</h3><span class="lnk">Ver prediccion →</span></a>'
        for s, m, lg in preds
    ) if preds else '<div class="empty"><p>No hay partidos programados para hoy.</p></div>'

    (OUTPUT_DIR / "index.html").write_text(
        INDEX.format(date=today_display, adsense=ADSENSE, ga=GA,
                     site_url=SITE_URL, cards=cards),
        encoding='utf-8'
    )

    # ── SEO: sitemap y robots ──
    print("\nGenerando archivos SEO...")
    slugs = [s for s, _, _ in preds]
    generate_sitemap(slugs)
    generate_robots()

    # --- LOG DE PREDICCIONES DIARIO ---
    import json as _json, re as _re
    from pathlib import Path as _Path
    _log_path = _Path("static/predictions_log.json")
    _log = _json.loads(_log_path.read_text()) if _log_path.exists() else []
    _log = [e for e in _log if e.get("fecha") != today]
    for slug, matchup, league in preds:
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
        _log.append({"fecha": today, "slug": slug,
            "home": parts[0].strip(), "away": parts[1].strip(),
            "league": league, "prediccion": _pred, "confianza": _conf,
            "resultado_real": None, "acerto": None})
    _log_path.write_text(_json.dumps(_log, ensure_ascii=False, indent=2))
    print(f"Log guardado: {len(_log)} predicciones")

    print(f"\n{len(preds)} predicciones generadas!")
    print(f"\nProximo paso: registra tu sitemap en Google Search Console")
    print(f"→ https://search.google.com/search-console")
    print(f"→ Agrega propiedad: {SITE_URL}")
    print(f"→ Envia sitemap: {SITE_URL}/sitemap.xml")

if __name__ == "__main__":
    main()
    main()
