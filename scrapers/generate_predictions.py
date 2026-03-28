import json, os, random, requests
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
ADSENSE = '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5953880132871590" crossorigin="anonymous"></script>'

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
<meta name="description" content="{desc}"><meta name="keywords" content="{kw}">
{adsense}
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--navy-900:#050d1a;--navy-800:#0b1d3a;--navy-700:#112b55;--gold-600:#c9a84c;--gold-500:#d4b865;--white:#fff;--gray-100:#e8edf5;--gray-400:#8896ae;--gray-600:#4a5568;--success:#22c55e;--danger:#ef4444;--font-display:'Barlow Condensed',sans-serif;--font-body:'Barlow',sans-serif;}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--font-body);background:var(--navy-900);color:var(--gray-100);min-height:100vh}}
.hdr{{background:rgba(5,13,26,.97);border-bottom:1px solid rgba(201,168,76,.15);padding:.9rem 2rem;display:flex;align-items:center;gap:1.5rem;position:sticky;top:0;z-index:100}}
.back{{background:none;border:1px solid rgba(201,168,76,.2);border-radius:4px;color:var(--gray-400);padding:.35rem .8rem;font-size:.85rem;text-decoration:none}}
.back:hover{{color:var(--gold-500)}}
.logo{{font-family:var(--font-display);font-size:1.6rem;font-weight:800;letter-spacing:.1em;color:var(--white);text-decoration:none}}
.logo span{{color:var(--gold-600)}}
.wrap{{max-width:860px;margin:3rem auto;padding:0 2rem 5rem}}
.badge{{display:inline-block;padding:.3rem 1rem;border-radius:2px;font-size:.62rem;letter-spacing:.25em;text-transform:uppercase;font-weight:600;background:rgba(201,168,76,.12);color:var(--gold-500);border:1px solid rgba(201,168,76,.25);margin-bottom:1rem}}
h1{{font-family:var(--font-display);font-size:clamp(1.8rem,4vw,2.8rem);font-weight:800;color:var(--white);line-height:1.2;margin-bottom:.8rem}}
.div{{width:60px;height:2px;background:linear-gradient(90deg,transparent,var(--gold-600),transparent);margin:1rem 0 1.5rem}}
.meta{{font-size:.75rem;letter-spacing:.2em;text-transform:uppercase;color:var(--gray-400);margin-bottom:2.5rem}}
.body p{{font-size:1rem;line-height:1.9;color:var(--gray-100);margin-bottom:1.2rem}}
.body h2{{font-family:var(--font-display);font-size:1.5rem;font-weight:700;color:var(--gold-500);margin:2.5rem 0 1rem;letter-spacing:.08em}}
.body strong{{color:var(--gold-500)}}
.sbox{{background:var(--navy-800);border:1px solid rgba(201,168,76,.15);border-left:3px solid var(--gold-600);border-radius:0 6px 6px 0;padding:1.5rem 2rem;margin:2rem 0}}
.srow{{display:flex;justify-content:space-between;padding:.5rem 0;border-bottom:1px solid rgba(255,255,255,.04)}}
.srow:last-child{{border-bottom:none}}
.slbl{{font-size:.85rem;color:var(--gray-400)}}
.sval{{font-size:.9rem;font-weight:600}}
.pbox{{background:var(--navy-800);border:1px solid rgba(201,168,76,.2);border-top:3px solid var(--gold-600);border-radius:8px;padding:2rem;margin:2.5rem 0;text-align:center}}
.plbl{{font-size:.65rem;letter-spacing:.25em;text-transform:uppercase;color:var(--gray-400);margin-bottom:.5rem}}
.pres{{font-family:var(--font-display);font-size:2.2rem;font-weight:800;color:var(--gold-500)}}
.pconf{{font-size:.85rem;color:var(--gray-400);margin-top:.3rem}}
.cta{{background:linear-gradient(135deg,var(--navy-800),var(--navy-700));border:1px solid rgba(201,168,76,.2);border-radius:8px;padding:2rem;text-align:center;margin-top:3rem}}
.cta p{{margin-bottom:1rem;color:var(--gray-400)}}
.cta a{{display:inline-block;background:linear-gradient(135deg,#b88e30,var(--gold-500));color:#050d1a;padding:.9rem 2rem;border-radius:4px;font-family:var(--font-display);font-size:1.1rem;font-weight:700;letter-spacing:.1em;text-decoration:none}}
.ftr{{border-top:1px solid rgba(201,168,76,.1);padding:1.5rem 2rem;text-align:center;font-size:.68rem;color:var(--gray-600);letter-spacing:.1em}}
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
{adsense}
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--navy-900:#050d1a;--navy-800:#0b1d3a;--gold-600:#c9a84c;--gold-500:#d4b865;--white:#fff;--gray-100:#e8edf5;--gray-400:#8896ae;--gray-600:#4a5568;--font-display:'Barlow Condensed',sans-serif;--font-body:'Barlow',sans-serif;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--font-body);background:var(--navy-900);color:var(--gray-100);min-height:100vh}}
.hdr{{background:rgba(5,13,26,.97);border-bottom:1px solid rgba(201,168,76,.15);padding:.9rem 2rem;display:flex;align-items:center;gap:1.5rem;position:sticky;top:0;z-index:100}}
.back{{background:none;border:1px solid rgba(201,168,76,.2);border-radius:4px;color:var(--gray-400);padding:.35rem .8rem;font-size:.85rem;text-decoration:none}}
.logo{{font-family:var(--font-display);font-size:1.6rem;font-weight:800;letter-spacing:.1em;color:var(--white);text-decoration:none}}
.logo span{{color:var(--gold-600)}}
.wrap{{max-width:1000px;margin:3rem auto;padding:0 2rem 5rem}}
h1{{font-family:var(--font-display);font-size:2.5rem;font-weight:800;color:var(--white);margin-bottom:.5rem}}
.sub{{color:var(--gray-400);font-size:.85rem;letter-spacing:.2em;text-transform:uppercase;margin-bottom:3rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1.5rem}}
.card{{background:var(--navy-800);border:1px solid rgba(201,168,76,.1);border-radius:8px;padding:1.5rem;text-decoration:none;display:block;transition:transform .3s,border-color .3s}}
.card:hover{{transform:translateY(-4px);border-color:rgba(201,168,76,.3)}}
.lg{{font-size:.6rem;letter-spacing:.25em;text-transform:uppercase;color:var(--gold-500);font-weight:600}}
.card h3{{font-family:var(--font-display);font-size:1.2rem;font-weight:700;color:var(--white);margin:.5rem 0 1rem;line-height:1.3}}
.lnk{{font-size:.8rem;color:var(--gold-500)}}
.empty{{text-align:center;padding:4rem;color:var(--gray-400)}}
.ftr{{border-top:1px solid rgba(201,168,76,.1);padding:1.5rem 2rem;text-align:center;font-size:.68rem;color:var(--gray-600);letter-spacing:.1em}}
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

def espn_fixtures(code):
    """
    Obtiene partidos de HOY en hora Colombia (UTC-5).
    Acepta partidos con fecha UTC de hoy O de manana antes de las 06:00 UTC
    (porque en Colombia la medianoche = 05:00 UTC del dia siguiente).
    Excluye partidos ya terminados.
    """
    try:
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/{code}/scoreboard",
            timeout=10
        )
        matches = []
        for e in r.json().get("events", []):
            event_date_utc = e.get("date", "")  # ej: 2026-03-29T01:20:00Z
            event_date = event_date_utc[:10]     # ej: 2026-03-29
            event_hour = int(event_date_utc[11:13]) if len(event_date_utc) > 12 else 0
            status = e.get("status", {}).get("type", {}).get("description", "")

            # Excluir partidos ya terminados
            if status in ("Full Time", "Final", "FT"):
                continue

            # Incluir si:
            # - fecha UTC es hoy, O
            # - fecha UTC es manana pero hora UTC <= 05:59 (medianoche Colombia = 05:00 UTC)
            es_hoy = event_date == today
            es_noche_colombia = (event_date == tomorrow and event_hour <= 5)

            if not es_hoy and not es_noche_colombia:
                continue

            cs = e.get("competitions", [{}])[0].get("competitors", [])
            if len(cs) >= 2:
                h = next((c["team"]["displayName"] for c in cs if c.get("homeAway") == "home"), None)
                a = next((c["team"]["displayName"] for c in cs if c.get("homeAway") == "away"), None)
                if h and a:
                    matches.append((h, a))
        return matches
    except Exception as ex:
        print(f"   ESPN error: {ex}")
        return []

def nba_fixtures():
    if not BALLDONTLIE_KEY:
        return []
    try:
        r = requests.get(
            f"https://api.balldontlie.io/v1/games?dates[]={today}",
            headers={"Authorization": BALLDONTLIE_KEY},
            timeout=10
        )
        return [(g["home_team"]["full_name"], g["visitor_team"]["full_name"]) for g in r.json().get("data", [])]
    except Exception as ex:
        print(f"   BallDontLie error: {ex}")
        return []

def load(f):
    p = Path(f"static/{f}")
    return json.load(open(p)) if p.exists() else {}

def find(stats, name):
    if not stats: return {}
    nl = name.lower()
    for k in stats:
        if k.lower() == nl: return stats[k]
    for k in stats:
        if k.lower() in nl or nl in k.lower(): return stats[k]
    ws = [w for w in nl.split() if len(w) > 3]
    for k in stats:
        if any(w in k.lower() for w in ws): return stats[k]
    return list(stats.values())[0] if stats else {}

def prob(hd, ad):
    hw = hd.get('wins', hd.get('won', 0)) or 0
    hl = hd.get('losses', hd.get('lost', 0)) or 0
    aw = ad.get('wins', ad.get('won', 0)) or 0
    al = ad.get('losses', ad.get('lost', 0)) or 0
    hg = hw + hl or 1; ag = aw + al or 1
    hp = hw / hg; ap = aw / ag
    h = min(85, max(15, round(hp / (hp + ap + 0.001) * 100 + 5)))
    return h, 100 - h

def gs(d, *ks):
    for k in ks:
        v = d.get(k)
        if v is not None: return v
    return "N/A"

def article(league, home, hd, away, ad, nba=False):
    hp, ap = prob(hd, ad)
    win = home if hp >= 50 else away
    wp = hp if hp >= 50 else ap
    sp = "puntos" if nba else "goles"
    hw = gs(hd,'wins','won'); hl = gs(hd,'losses','lost')
    hpts = gs(hd,'avg_points','goals_for'); hpta = gs(hd,'avg_points_allowed','goals_against')
    aw = gs(ad,'wins','won'); al = gs(ad,'losses','lost')
    apts = gs(ad,'avg_points','goals_for'); apta = gs(ad,'avg_points_allowed','goals_against')
    try: tot_txt = f"El total proyectado es de <strong>{round(float(hpts)+float(apts),1)} {sp}</strong>."
    except: tot_txt = ""
    intro = random.choice([
        f"Uno de los encuentros de la jornada en <strong>{league}</strong> enfrenta a <strong>{home}</strong> y <strong>{away}</strong>.",
        f"La <strong>{league}</strong> presenta este choque entre <strong>{home}</strong> y <strong>{away}</strong>.",
        f"<strong>{home}</strong> recibe a <strong>{away}</strong> en un partido clave de la <strong>{league}</strong>.",
    ])
    fav = random.choice([
        f"Nuestro analisis indica que <strong>{win}</strong> parte como favorito con una probabilidad del <strong>{wp}%</strong>.",
        f"Los datos apuntan a <strong>{win}</strong> con un <strong>{wp}%</strong> de probabilidad de victoria.",
        f"Segun nuestro modelo, <strong>{win}</strong> tiene el <strong>{wp}%</strong> de posibilidades de ganar.",
    ])
    return f"""
<p>{intro}</p>
<h2>Analisis del equipo local: {home}</h2>
<p><strong>{home}</strong> llega con <strong>{hw} victorias y {hl} derrotas</strong>. Promedia <strong>{hpts} {sp}</strong> por partido y recibe <strong>{hpta}</strong> en contra.</p>
<div class="sbox">
<div class="srow"><span class="slbl">Victorias</span><span class="sval" style="color:var(--success)">{hw}</span></div>
<div class="srow"><span class="slbl">Derrotas</span><span class="sval" style="color:var(--danger)">{hl}</span></div>
<div class="srow"><span class="slbl">{sp.capitalize()} prom. a favor</span><span class="sval">{hpts}</span></div>
<div class="srow"><span class="slbl">{sp.capitalize()} prom. en contra</span><span class="sval">{hpta}</span></div>
<div class="srow"><span class="slbl">Probabilidad de victoria</span><span class="sval" style="color:var(--gold-500)">{hp}%</span></div>
</div>
<h2>Analisis del equipo visitante: {away}</h2>
<p><strong>{away}</strong> presenta <strong>{aw} victorias y {al} derrotas</strong>. Promedia <strong>{apts} {sp}</strong> anotados y <strong>{apta}</strong> recibidos.</p>
<div class="sbox">
<div class="srow"><span class="slbl">Victorias</span><span class="sval" style="color:var(--success)">{aw}</span></div>
<div class="srow"><span class="slbl">Derrotas</span><span class="sval" style="color:var(--danger)">{al}</span></div>
<div class="srow"><span class="slbl">{sp.capitalize()} prom. a favor</span><span class="sval">{apts}</span></div>
<div class="srow"><span class="slbl">{sp.capitalize()} prom. en contra</span><span class="sval">{apta}</span></div>
<div class="srow"><span class="slbl">Probabilidad de victoria</span><span class="sval" style="color:var(--gold-500)">{ap}%</span></div>
</div>
<h2>Prediccion final</h2>
<p>{fav} {tot_txt}</p>
<div class="pbox">
<div class="plbl">Ganador probable</div>
<div class="pres">{win}</div>
<div class="pconf">Probabilidad de victoria: {wp}%</div>
</div>
<p>Este analisis esta basado en las estadisticas actuales de la temporada. Usa nuestro analizador interactivo para explorar mas datos.</p>"""

def save(league, home, away, art):
    slug = f"{home}-vs-{away}-{league}-{today}".lower()
    slug = ''.join(c if c.isalnum() or c == '-' else '-' for c in slug)
    slug = '-'.join(filter(None, slug.split('-')))[:100]
    html = HTML.format(
        title=f"Prediccion {home} vs {away} - {league} {today_display}",
        desc=f"Prediccion y analisis de {home} vs {away} en {league} para {today_display}.",
        kw=f"prediccion {home} {away}, pronostico {league}, {home} vs {away} hoy",
        adsense=ADSENSE, league=league, date=today_display,
        home=home, away=away, article=art
    )
    (OUTPUT_DIR / f"{slug}.html").write_text(html, encoding='utf-8')
    return slug

def main():
    preds = []
    print(f"Generando predicciones — {today_display}")
    print(f"Hoy UTC: {today} | Acepta hasta {tomorrow} 05:59 UTC (medianoche Colombia)\n")

    for code, (league, stats_file) in ESPN_LEAGUES.items():
        matches = espn_fixtures(code)
        if not matches:
            continue
        print(f"Futbol {league}: {len(matches)} partidos")
        stats = load(stats_file)
        for home, away in matches:
            hd = find(stats, home); ad = find(stats, away)
            if not hd: hd = ad
            if not ad: ad = hd
            art = article(league, home, hd, away, ad)
            slug = save(league, home, away, art)
            preds.append((slug, f"{home} vs {away}", league))
            print(f"   OK: {home} vs {away}")

    nba_games = nba_fixtures()
    if nba_games:
        print(f"\nNBA: {len(nba_games)} partidos")
        nba_teams = load("nba_stats.json").get("teams", {})
        for home, away in nba_games:
            hd = find(nba_teams, home); ad = find(nba_teams, away)
            if not hd: hd = ad
            if not ad: ad = hd
            art = article("NBA 2025-26", home, hd, away, ad, nba=True)
            slug = save("NBA", home, away, art)
            preds.append((slug, f"{home} vs {away}", "NBA"))
            print(f"   OK: {home} vs {away}")

    cards = ''.join(
        f'<a href="/static/predictions/{s}.html" class="card"><span class="lg">{lg}</span><h3>{m}</h3><span class="lnk">Ver prediccion →</span></a>'
        for s, m, lg in preds
    ) if preds else '<div class="empty"><p>No hay partidos programados para hoy.</p></div>'

    (OUTPUT_DIR / "index.html").write_text(
        INDEX.format(date=today_display, adsense=ADSENSE, cards=cards),
        encoding='utf-8'
    )
    print(f"\n{len(preds)} predicciones generadas en static/predictions/")

if __name__ == "__main__":
    main()