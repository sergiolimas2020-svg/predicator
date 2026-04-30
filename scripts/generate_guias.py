#!/usr/bin/env python3
"""
Genera la sección /guias/ de PREDIKTOR a partir de archivos Markdown
con frontmatter en /content/guias/.

Salida:
  - guias/<slug>.html       — un archivo por artículo
  - guias/index.html        — listado con cards ordenadas

Uso (manual, después de agregar/editar un .md):
    python3 scripts/generate_guias.py

NO se invoca desde el cron diario — los artículos no cambian a diario.
El sitemap se actualiza automáticamente vía
scrapers/generate_predictions.py, que detecta los .md de /content/guias/.

Frontmatter esperado en cada .md (todos los campos obligatorios salvo
los marcados opcionales):

    ---
    title: "..."                 # h1 del artículo
    description: "..."           # meta description
    slug: "..."                  # nombre del archivo HTML output
    date: 2026-04-30             # fecha publicación (YAML date)
    tier: 1                      # 1 Básico | 2 Intermedio | 3 Avanzado
    reading_time: 8              # minutos estimados
    keywords: "..."              # opcional
    author: "PREDIKTOR"          # opcional
    featured: true               # opcional, default false
    ---

El cuerpo del .md soporta Markdown estándar + HTML inline. Se permite:
  - tablas, fenced_code, attr_list, md_in_html
  - [TOC] al inicio para tabla de contenidos automática
  - <div class="callout|formula|tip"> para componentes destacados
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import date as Date, datetime
from pathlib import Path

import frontmatter
import markdown

ROOT          = Path(__file__).resolve().parent.parent
CONTENT_DIR   = ROOT / "content" / "guias"
OUTPUT_DIR    = ROOT / "guias"
SITE_URL      = "https://prediktorcol.com"

REQUIRED_FIELDS = ("title", "description", "slug", "date", "tier", "reading_time")
TIER_LABEL = {1: "Básico", 2: "Intermedio", 3: "Avanzado"}


# ── Markdown engine ───────────────────────────────────────────
def _build_md() -> markdown.Markdown:
    return markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "attr_list", "md_in_html"],
        extension_configs={
            "toc": {"marker": "[TOC]", "permalink": False, "toc_class": "toc"},
        },
    )


# ── Carga + validación ────────────────────────────────────────
def load_articles() -> list[dict]:
    """Lee todos los .md de /content/guias/ (excepto .gitkeep) y los valida."""
    articles = []
    if not CONTENT_DIR.exists():
        return articles
    for md_path in sorted(CONTENT_DIR.glob("*.md")):
        post = frontmatter.load(md_path)
        meta = post.metadata
        for f in REQUIRED_FIELDS:
            if meta.get(f) in (None, ""):
                print(f"✗ {md_path.name}: falta el campo '{f}' en frontmatter",
                      file=sys.stderr)
                sys.exit(1)
        # Normalizar fecha a string ISO
        d = meta["date"]
        if isinstance(d, Date):
            meta["date"] = d.isoformat()
        articles.append({"meta": meta, "body": post.content, "src": md_path})
    return articles


# ── Render HTML del artículo individual ───────────────────────
def _esc(s: object) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _word_count(md_body: str) -> int:
    """Aproximado: cuenta palabras del Markdown body (descarta sintaxis)."""
    text = re.sub(r"```.*?```", " ", md_body, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[#*_`\[\]\(\)>!]", " ", text)
    return len([w for w in text.split() if len(w) > 1])


def _article_jsonld(meta: dict, word_count: int) -> str:
    payload = {
        "@context":         "https://schema.org",
        "@type":            "Article",
        "headline":         meta["title"],
        "description":      meta["description"],
        "datePublished":    meta["date"],
        "dateModified":     meta["date"],
        "author":           {"@type": "Organization", "name": meta.get("author") or "PREDIKTOR",
                             "url": SITE_URL},
        "publisher":        {"@type": "Organization", "name": "PREDIKTOR",
                             "url": SITE_URL},
        "mainEntityOfPage": {"@type": "WebPage",
                             "@id":   f'{SITE_URL}/guias/{meta["slug"]}.html'},
        "wordCount":        word_count,
    }
    if meta.get("keywords"):
        payload["keywords"] = meta["keywords"]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _breadcrumb_jsonld(meta: dict) -> str:
    payload = {
        "@context":         "https://schema.org",
        "@type":            "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Inicio",
             "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Guías",
             "item": f"{SITE_URL}/guias/"},
            {"@type": "ListItem", "position": 3, "name": meta["title"],
             "item": f'{SITE_URL}/guias/{meta["slug"]}.html'},
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_article(article: dict) -> str:
    meta, body = article["meta"], article["body"]
    md = _build_md()
    html_body = md.convert(body)
    wc = _word_count(body)
    article_ld    = _article_jsonld(meta, wc)
    breadcrumb_ld = _breadcrumb_jsonld(meta)
    tier      = int(meta["tier"])
    tier_lbl  = TIER_LABEL.get(tier, "Guía")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_esc(meta["title"])} — PREDIKTOR</title>
  <meta name="description" content="{_esc(meta["description"])}">
  <meta name="keywords" content="{_esc(meta.get("keywords",""))}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{SITE_URL}/guias/{_esc(meta["slug"])}.html">

  <meta property="og:title" content="{_esc(meta["title"])}">
  <meta property="og:description" content="{_esc(meta["description"])}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{SITE_URL}/guias/{_esc(meta["slug"])}.html">
  <meta property="og:site_name" content="PREDIKTOR">
  <meta property="article:published_time" content="{_esc(meta["date"])}">

  <script type="application/ld+json">
{article_ld}
  </script>
  <script type="application/ld+json">
{breadcrumb_ld}
  </script>

  <script async src="https://www.googletagmanager.com/gtag/js?id=G-K3JES4SQS9"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-K3JES4SQS9');
  </script>
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5953880132871590" crossorigin="anonymous"></script>

  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">

{_render_css()}
</head>
<body>

  <nav>
    <a href="/" class="logo">PREDI<span>KTOR</span></a>
    <div class="nav-links">
      <a href="/">Inicio</a>
      <a href="/metodologia.html">Metodología</a>
      <a href="/glosario.html">Glosario</a>
      <a href="/como-interpretar.html">Cómo usar</a>
      <a href="/guias/" class="active">Guías</a>
      <a href="/historial.html">Historial</a>
      <a href="/about.html">Sobre</a>
    </div>
  </nav>

  <article>
    <div class="breadcrumb">
      <a href="/">Inicio</a> · <a href="/guias/">Guías</a> · {_esc(meta["title"])}
    </div>

    <h1>{_esc(meta["title"])}</h1>
    <div class="article-meta">
      <span class="tier-badge tier-{tier}">{tier_lbl}</span>
      <span>📅 {_esc(meta["date"])}</span>
      <span>📖 {_esc(meta["reading_time"])} min de lectura</span>
    </div>

    {html_body}
  </article>

  <div class="disclaimer">⚠️ <strong>Aviso:</strong> Este contenido es informativo y educativo. PREDIKTOR no es una casa de apuestas. Apuesta con responsabilidad.</div>

  <footer>
    <div class="footer-logo">PREDIKTOR</div>
    <div class="footer-desc">Sistema automatizado de análisis estadístico deportivo. Metodología abierta, datos verificables.</div>
    <div class="footer-links">
      <a href="/">Inicio</a>
      <a href="/metodologia.html">Metodología</a>
      <a href="/glosario.html">Glosario</a>
      <a href="/como-interpretar.html">Cómo usar</a>
      <a href="/guias/">Guías</a>
      <a href="/historial.html">Historial</a>
      <a href="/about.html">Sobre</a>
      <a href="/privacy.html">Privacidad</a>
    </div>
    <div class="footer-copy">© 2026 PREDIKTOR · contacto@prediktor.app</div>
  </footer>

</body>
</html>
"""


# ── /guias/index.html ─────────────────────────────────────────
def _index_jsonld(articles: list[dict]) -> str:
    items = []
    for i, a in enumerate(articles, start=1):
        m = a["meta"]
        items.append({
            "@type":   "ListItem",
            "position": i,
            "name":     m["title"],
            "url":      f'{SITE_URL}/guias/{m["slug"]}.html',
        })
    payload = {
        "@context":    "https://schema.org",
        "@type":       "CollectionPage",
        "name":        "Guías de apuestas — PREDIKTOR",
        "description": "Artículos educativos sobre análisis estadístico de apuestas deportivas.",
        "url":         f"{SITE_URL}/guias/",
        "mainEntity":  {
            "@type":           "ItemList",
            "numberOfItems":   len(items),
            "itemListElement": items,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _sort_articles(articles: list[dict]) -> list[dict]:
    """Featured primero, después tier asc, después date desc."""
    def key(a):
        m = a["meta"]
        return (
            0 if m.get("featured") else 1,
            int(m.get("tier", 99)),
            # date desc → invertir string ISO
            tuple(-int(x) for x in str(m["date"]).split("-")),
        )
    return sorted(articles, key=key)


def render_index(articles: list[dict]) -> str:
    sorted_articles = _sort_articles(articles)
    if sorted_articles:
        cards_html = "\n      ".join(_render_card(a) for a in sorted_articles)
        empty_state = ""
    else:
        cards_html = ""
        empty_state = (
            '<div class="empty-state">'
            '<p style="color:var(--gris);text-align:center;padding:3rem 0">'
            'Próximamente — los primeros artículos se publicarán pronto.'
            '</p></div>'
        )

    index_ld = _index_jsonld(sorted_articles)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Guías de apuestas — PREDIKTOR | Educativos sobre análisis deportivo</title>
  <meta name="description" content="Guías educativas sobre apuestas deportivas: valor esperado, probabilidades, gestión de bankroll, errores comunes y más. Contenido basado en estadística, no opinión.">
  <meta name="keywords" content="guías apuestas deportivas, valor esperado, value betting, gestión bankroll, probabilidades apuestas">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{SITE_URL}/guias/">

  <meta property="og:title" content="Guías de apuestas — PREDIKTOR">
  <meta property="og:description" content="Aprende los conceptos clave del análisis estadístico de apuestas deportivas.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{SITE_URL}/guias/">

  <script type="application/ld+json">
{index_ld}
  </script>

  <script async src="https://www.googletagmanager.com/gtag/js?id=G-K3JES4SQS9"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-K3JES4SQS9');
  </script>
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5953880132871590" crossorigin="anonymous"></script>

  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">

{_render_css()}
</head>
<body>

  <nav>
    <a href="/" class="logo">PREDI<span>KTOR</span></a>
    <div class="nav-links">
      <a href="/">Inicio</a>
      <a href="/metodologia.html">Metodología</a>
      <a href="/glosario.html">Glosario</a>
      <a href="/como-interpretar.html">Cómo usar</a>
      <a href="/guias/" class="active">Guías</a>
      <a href="/historial.html">Historial</a>
      <a href="/about.html">Sobre</a>
    </div>
  </nav>

  <article>
    <div class="breadcrumb"><a href="/">Inicio</a> · Guías</div>

    <h1>Guías<br><span>de apuestas</span></h1>
    <p class="subtitle">Aprende los conceptos clave del análisis estadístico de apuestas deportivas. Desde fundamentos hasta técnicas avanzadas, basado en datos y no en opinión.</p>

    <div class="guias-grid">
      {cards_html}
    </div>
    {empty_state}
  </article>

  <div class="disclaimer">⚠️ <strong>Aviso:</strong> Contenido educativo. PREDIKTOR no es una casa de apuestas. Apuesta con responsabilidad.</div>

  <footer>
    <div class="footer-logo">PREDIKTOR</div>
    <div class="footer-desc">Sistema automatizado de análisis estadístico deportivo. Metodología abierta, datos verificables.</div>
    <div class="footer-links">
      <a href="/">Inicio</a>
      <a href="/metodologia.html">Metodología</a>
      <a href="/glosario.html">Glosario</a>
      <a href="/como-interpretar.html">Cómo usar</a>
      <a href="/guias/">Guías</a>
      <a href="/historial.html">Historial</a>
      <a href="/about.html">Sobre</a>
      <a href="/privacy.html">Privacidad</a>
    </div>
    <div class="footer-copy">© 2026 PREDIKTOR · contacto@prediktor.app</div>
  </footer>

</body>
</html>
"""


def _render_card(article: dict) -> str:
    m = article["meta"]
    tier = int(m["tier"])
    tier_lbl = TIER_LABEL.get(tier, "Guía")
    return (
        f'<a href="/guias/{_esc(m["slug"])}.html" class="guia-card">'
        f'<span class="tier-badge tier-{tier}">{tier_lbl}</span>'
        f'<h3>{_esc(m["title"])}</h3>'
        f'<p>{_esc(m["description"])}</p>'
        f'<div class="meta">📖 {_esc(m["reading_time"])} min · 📅 {_esc(m["date"])}</div>'
        f'</a>'
    )


# ── CSS compartido (template) ─────────────────────────────────
def _render_css() -> str:
    return """  <style>
    :root {
      --negro:#0a0a0f; --oscuro:#111118; --card:#16161f; --card2:#1c1c28;
      --borde:#2a2a3a; --dorado:#f0b429; --dorado2:#c9900a;
      --verde:#22c55e; --rojo:#ef4444; --azul:#3b82f6;
      --texto:#e2e8f0; --gris:#94a3b8;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body { font-family:'DM Sans',sans-serif; background:var(--negro); color:var(--texto); line-height:1.7; }

    nav {
      display:flex; justify-content:space-between; align-items:center;
      padding:1.2rem 2rem; border-bottom:1px solid var(--borde);
      position:sticky; top:0; background:rgba(10,10,15,0.96);
      backdrop-filter:blur(12px); z-index:100;
    }
    .logo { font-family:'Bebas Neue',sans-serif; font-size:1.8rem; letter-spacing:3px; color:var(--texto); text-decoration:none; }
    .logo span { color:var(--dorado); }
    .nav-links { display:flex; gap:1.5rem; align-items:center; flex-wrap:wrap; }
    .nav-links a { color:var(--gris); text-decoration:none; font-size:0.9rem; font-weight:500; transition:color 0.2s; }
    .nav-links a:hover, .nav-links a.active { color:var(--dorado); }

    article { max-width:820px; margin:3rem auto; padding:0 1.5rem 5rem; }
    .breadcrumb { font-size:0.8rem; color:var(--gris); margin-bottom:1.5rem; letter-spacing:1px; text-transform:uppercase; }
    .breadcrumb a { color:var(--dorado); text-decoration:none; }

    h1 { font-family:'Bebas Neue',sans-serif; font-size:clamp(2.4rem,6vw,3.8rem); line-height:1.05; letter-spacing:1px; margin-bottom:1rem; color:#fff; }
    h1 span { color:var(--dorado); }
    .subtitle { font-size:1.1rem; color:var(--gris); margin-bottom:2.5rem; max-width:680px; }

    h2 { font-family:'Bebas Neue',sans-serif; font-size:clamp(1.7rem,3.5vw,2.4rem); letter-spacing:1px; color:#fff; margin:3rem 0 1rem; padding-bottom:0.6rem; border-bottom:1px solid var(--borde); }
    h3 { font-size:1.25rem; font-weight:700; color:var(--dorado); margin:2rem 0 0.8rem; letter-spacing:0.5px; }

    p { margin-bottom:1.2rem; font-size:1rem; color:var(--texto); }
    p strong { color:#fff; font-weight:600; }
    a { color:var(--dorado); }

    ul, ol { margin:1rem 0 1.4rem 1.5rem; }
    li { margin-bottom:0.6rem; color:var(--texto); }
    li strong { color:#fff; }

    /* Componentes destacados (HTML inline en el .md) */
    .formula {
      background:var(--card); border:1px solid var(--borde); border-left:3px solid var(--dorado);
      border-radius:6px; padding:1.2rem 1.4rem; margin:1.4rem 0;
      font-family:'Courier New',monospace; font-size:0.95rem; color:var(--dorado); overflow-x:auto;
    }
    .callout {
      background:rgba(240,180,41,0.05); border:1px solid rgba(240,180,41,0.2); border-left:3px solid var(--dorado);
      border-radius:6px; padding:1rem 1.3rem; margin:1.5rem 0;
    }
    .callout strong { color:var(--dorado); }
    .tip {
      background:rgba(34,197,94,0.05); border:1px solid rgba(34,197,94,0.2); border-left:3px solid var(--verde);
      border-radius:6px; padding:1rem 1.3rem; margin:1.5rem 0; font-size:0.95rem;
    }

    /* Tablas */
    table { width:100%; border-collapse:collapse; margin:1.5rem 0; background:var(--card); border:1px solid var(--borde); border-radius:6px; overflow:hidden; font-size:0.92rem; }
    th, td { padding:0.8rem 1rem; text-align:left; border-bottom:1px solid var(--borde); }
    th { background:var(--card2); color:var(--dorado); font-weight:700; font-size:0.8rem; text-transform:uppercase; letter-spacing:1px; }
    tr:last-child td { border-bottom:none; }

    /* Código */
    pre { background:var(--card2); border:1px solid var(--borde); border-radius:6px; padding:1rem 1.2rem; overflow-x:auto; margin:1.4rem 0; }
    pre code { font-family:'Courier New',monospace; font-size:0.9rem; color:var(--texto); background:none; padding:0; }
    code { background:rgba(240,180,41,0.1); padding:2px 6px; border-radius:3px; font-size:0.9em; color:var(--dorado); font-family:'Courier New',monospace; }

    /* Tabla de contenidos (TOC marker) */
    .toc { background:var(--card2); border-left:3px solid var(--dorado); border-radius:6px; padding:1.2rem 1.4rem; margin:1.5rem 0 2.5rem; font-size:0.92rem; }
    .toc > ul { margin:0.5rem 0 0 1rem; }
    .toc a { color:var(--dorado); text-decoration:none; }
    .toc a:hover { text-decoration:underline; }

    /* Article metadata (fecha + reading time + tier) */
    .article-meta { display:flex; gap:1rem; flex-wrap:wrap; align-items:center; font-size:0.85rem; color:var(--gris); margin:0.5rem 0 2rem; }
    .article-meta span { display:inline-flex; align-items:center; gap:0.4rem; }

    /* Tier badges (ambos: article-meta + cards de index) */
    .tier-badge { font-size:0.7rem; padding:0.25rem 0.7rem; border-radius:3px; letter-spacing:1.5px; text-transform:uppercase; font-weight:700; }
    .tier-1 { background:rgba(34,197,94,0.15); color:var(--verde); }
    .tier-2 { background:rgba(240,180,41,0.15); color:var(--dorado); }
    .tier-3 { background:rgba(239,68,68,0.15); color:var(--rojo); }

    /* Cards en /guias/index.html */
    .guias-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:1.2rem; margin:2rem 0 3rem; }
    .guia-card {
      background:var(--card); border:1px solid var(--borde); border-top:3px solid var(--dorado);
      border-radius:8px; padding:1.5rem; transition:transform 0.2s, border-color 0.2s;
      text-decoration:none; display:block; color:var(--texto); position:relative;
    }
    .guia-card:hover { transform:translateY(-2px); border-color:var(--dorado); }
    .guia-card .tier-badge { position:absolute; top:0.8rem; right:0.8rem; }
    .guia-card h3 { color:#fff; margin:0 5rem 0.5rem 0; font-size:1.2rem; }
    .guia-card p { color:var(--gris); font-size:0.92rem; margin-bottom:1rem; }
    .guia-card .meta { color:var(--gris); font-size:0.78rem; }

    /* Footer */
    footer { background:var(--oscuro); border-top:1px solid var(--borde); padding:3rem 2rem 2rem; text-align:center; }
    .footer-logo { font-family:'Bebas Neue',sans-serif; font-size:2rem; color:var(--dorado); letter-spacing:3px; margin-bottom:0.8rem; }
    .footer-desc { color:var(--gris); font-size:0.88rem; max-width:480px; margin:0 auto 1.5rem; line-height:1.7; }
    .footer-links { display:flex; justify-content:center; gap:1.5rem; margin-bottom:2rem; flex-wrap:wrap; }
    .footer-links a { color:var(--gris); text-decoration:none; font-size:0.85rem; transition:color 0.2s; }
    .footer-links a:hover { color:var(--dorado); }
    .footer-copy { color:var(--borde); font-size:0.8rem; }

    .disclaimer {
      background:rgba(240,180,41,0.04); border-top:1px solid rgba(240,180,41,0.1); border-bottom:1px solid rgba(240,180,41,0.1);
      padding:1.2rem 2rem; text-align:center; color:var(--gris); font-size:0.82rem; line-height:1.6;
    }

    @media (max-width:640px) {
      nav { padding:1rem; }
      .nav-links { gap:0.8rem; }
    }
  </style>"""


# ── Main ──────────────────────────────────────────────────────
def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    articles = load_articles()

    # Render artículos individuales
    for a in articles:
        slug = a["meta"]["slug"]
        out  = OUTPUT_DIR / f"{slug}.html"
        out.write_text(render_article(a), encoding="utf-8")
        print(f"✓ guias/{slug}.html")

    # Render index
    index_path = OUTPUT_DIR / "index.html"
    index_path.write_text(render_index(articles), encoding="utf-8")
    print(f"✓ guias/index.html ({len(articles)} artículo{'s' if len(articles) != 1 else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
