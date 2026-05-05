#!/usr/bin/env python3
"""
Genera historial.html (página estática indexable por Google y AdSense)
y reescribe los 3 contadores del home (index.html) con valores reales.

Lee:
  static/predictions_log.json   — fuente de verdad (49 verificados al 30-abr).

Escribe:
  historial.html                — página estática completa, server-rendered.
  index.html                    — los 3 placeholders del stats-bar quedan
                                  con valores reales en HTML estático.

Invocado por el cron diario tras update_results.py — ver
.github/workflows/prediktor-daily.yml step "Generar página historial".

Idempotente: correr 2 veces el mismo día deja los archivos iguales.
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT          = Path(__file__).resolve().parent.parent
LOG_PATH      = ROOT / "static" / "predictions_log.json"
HISTORIAL_OUT = ROOT / "historial.html"
INDEX_PATH    = ROOT / "index.html"

# Iconos por liga (mismos que usa app.html para coherencia visual)
LEAGUE_ICON = {
    "Liga Colombiana": "🇨🇴", "Premier League": "🏴",
    "La Liga": "🇪🇸", "Bundesliga": "🇩🇪", "Serie A": "🇮🇹",
    "Ligue 1": "🇫🇷", "Champions League": "⭐", "NBA": "🏀",
    "MLS": "🇺🇸", "Brasileirao": "🇧🇷", "Liga Argentina": "🇦🇷",
    "Super Lig": "🇹🇷", "Copa Libertadores": "🏆",
    "Copa Sudamericana": "🏆",
}

COL_TZ = timezone(timedelta(hours=-5))


def _today_str() -> str:
    return datetime.now(COL_TZ).strftime("%Y-%m-%d")


def _esc(s: object) -> str:
    """HTML-escape, tolerante a None."""
    return html.escape(str(s if s is not None else "—"), quote=True)


def load_stats() -> dict:
    """Lee el log y calcula stats + lista ordenada por fecha desc."""
    if not LOG_PATH.exists():
        print(f"✗ No existe {LOG_PATH}", file=sys.stderr)
        sys.exit(1)
    log = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    verificados = [e for e in log if e.get("acerto") is not None]
    if not verificados:
        print("✗ No hay predicciones verificadas — aborto", file=sys.stderr)
        sys.exit(1)

    total    = len(verificados)
    aciertos = sum(1 for e in verificados if e["acerto"])
    pct      = round(aciertos / total * 100) if total else 0

    # Ordenar por fecha desc (string ISO ordena bien lexicográfico)
    items = sorted(verificados, key=lambda e: e.get("fecha", ""), reverse=True)

    return {
        "total":     total,
        "aciertos":  aciertos,
        "fallos":    total - aciertos,
        "pct":       pct,
        "items":     items,
        "today":     _today_str(),
    }


def _render_jsonld(stats: dict) -> str:
    """Schema.org Dataset + ItemList con los 49 picks como ListItems."""
    item_list = []
    for i, e in enumerate(stats["items"], start=1):
        ok = "ACERTÓ" if e["acerto"] else "FALLÓ"
        item_list.append({
            "@type":         "ListItem",
            "position":      i,
            "name":          f'{e.get("home","?")} vs {e.get("away","?")}',
            "description":   (
                f'{e.get("prediccion","—")} — '
                f'Resultado: {e.get("resultado_real","—")} ({ok})'
            ),
            "datePublished": e.get("fecha", ""),
        })
    payload = {
        "@context":    "https://schema.org",
        "@type":       "Dataset",
        "name":        "Historial de predicciones verificadas — PREDIKTOR",
        "description": (
            f'Registro completo de {stats["total"]} predicciones deportivas '
            f'contrastadas con resultados oficiales de ESPN. '
            f'{stats["aciertos"]} correctas ({stats["pct"]}% de acierto).'
        ),
        "url":         "https://prediktorcol.com/historial.html",
        "creator":     {"@type": "Organization", "name": "PREDIKTOR",
                        "url": "https://prediktorcol.com"},
        "license":     "https://prediktorcol.com/about.html",
        "keywords":    "predicciones deportivas, fútbol, NBA, tasa de acierto, "
                       "value betting, picks verificados",
        "dateModified": stats["today"],
        "mainEntity":  {
            "@type":            "ItemList",
            "numberOfItems":    stats["total"],
            "itemListElement":  item_list,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _render_pick_row(idx: int, e: dict) -> str:
    icon  = LEAGUE_ICON.get(e.get("league", ""), "⚽")
    fecha = _esc(e.get("fecha"))
    league = _esc(e.get("league"))
    matchup = f'{_esc(e.get("home"))} vs {_esc(e.get("away"))}'
    pred   = _esc(e.get("prediccion"))
    res    = _esc(e.get("resultado_real"))
    if e["acerto"]:
        cls, mark, label = "ok",   "✓", "Acertó"
    else:
        cls, mark, label = "fail", "✗", "Falló"

    # Betplay info (solo si campos presentes — retrocompat con picks antiguos)
    bp_inline = ""
    cuota_bp = e.get("cuota_betplay_estimada")
    ev_bp    = e.get("ev_betplay_estimado")
    if cuota_bp is not None or ev_bp is not None:
        cuota_str = f"{cuota_bp:.2f}" if cuota_bp is not None else "—"
        ev_str    = (f"{'+' if ev_bp >= 0 else ''}{ev_bp:.1f}%"
                     if ev_bp is not None else "—")
        bp_inline = (
            f'<small class="pick-bp" title="Cuota Betplay estimada con descuento del 10% promedio. Verifica antes de apostar.">'
            f' · Betplay est: {cuota_str} ({ev_str})</small>'
        )

    return (
        f'<div class="pick-row">'
        f'<span class="pick-fecha">{fecha}</span>'
        f'<span class="pick-matchup">'
        f'<span class="pick-icon" aria-hidden="true">{icon}</span> '
        f'<strong>{matchup}</strong> '
        f'<span class="pick-league">({league})</span>'
        f'</span>'
        f'<span class="pick-pred">{pred}{bp_inline}</span>'
        f'<span class="pick-result">{res}</span>'
        f'<span class="pick-acerto {cls}" title="{label}">{mark}</span>'
        f'</div>'
    )


def render_html(stats: dict) -> str:
    rows   = "\n      ".join(
        _render_pick_row(i, e) for i, e in enumerate(stats["items"], start=1)
    )
    jsonld = _render_jsonld(stats)
    pct, total, aciertos = stats["pct"], stats["total"], stats["aciertos"]
    today = stats["today"]

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Historial Verificado — PREDIKTOR | {total} predicciones, {pct}% acierto</title>
  <meta name="description" content="Historial completo de predicciones de PREDIKTOR contrastadas con resultados oficiales de ESPN. {total} picks verificados, {aciertos} correctos, {pct}% de tasa de acierto. Datos auditables y transparentes.">
  <meta name="keywords" content="historial predicciones prediktor, tasa acierto, picks verificados, predicciones deportivas colombia, value betting auditable">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="https://prediktorcol.com/historial.html">

  <meta property="og:title" content="Historial Verificado — PREDIKTOR">
  <meta property="og:description" content="{total} predicciones verificadas, {pct}% de acierto. Auditable, transparente.">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://prediktorcol.com/historial.html">
  <meta property="og:site_name" content="PREDIKTOR">

  <script type="application/ld+json">
{jsonld}
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

  <style>
    :root {{
      --negro:#0a0a0f; --oscuro:#111118; --card:#16161f; --card2:#1c1c28;
      --borde:#2a2a3a; --dorado:#f0b429; --verde:#22c55e; --rojo:#ef4444;
      --texto:#e2e8f0; --gris:#94a3b8;
    }}
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ font-family:'DM Sans',sans-serif; background:var(--negro); color:var(--texto); line-height:1.7; }}

    nav {{
      display:flex; justify-content:space-between; align-items:center;
      padding:1.2rem 2rem; border-bottom:1px solid var(--borde);
      position:sticky; top:0; background:rgba(10,10,15,0.96);
      backdrop-filter:blur(12px); z-index:100;
    }}
    .logo {{ font-family:'Bebas Neue',sans-serif; font-size:1.8rem; letter-spacing:3px; color:var(--texto); text-decoration:none; }}
    .logo span {{ color:var(--dorado); }}
    .nav-links {{ display:flex; gap:1.5rem; align-items:center; flex-wrap:wrap; }}
    .nav-links a {{ color:var(--gris); text-decoration:none; font-size:0.9rem; font-weight:500; transition:color 0.2s; }}
    .nav-links a:hover, .nav-links a.active {{ color:var(--dorado); }}

    article {{ max-width:980px; margin:3rem auto; padding:0 1.5rem 5rem; }}
    .breadcrumb {{ font-size:0.8rem; color:var(--gris); margin-bottom:1.5rem; letter-spacing:1px; text-transform:uppercase; }}
    .breadcrumb a {{ color:var(--dorado); text-decoration:none; }}

    h1 {{ font-family:'Bebas Neue',sans-serif; font-size:clamp(2.4rem,6vw,3.8rem);
         line-height:1.05; letter-spacing:1px; margin-bottom:1rem; color:#fff; }}
    h1 span {{ color:var(--dorado); }}
    .subtitle {{ font-size:1.1rem; color:var(--gris); margin-bottom:2.5rem; max-width:680px; }}

    h2 {{ font-family:'Bebas Neue',sans-serif; font-size:clamp(1.7rem,3.5vw,2.4rem);
         letter-spacing:1px; color:#fff; margin:3rem 0 1.5rem;
         padding-bottom:0.6rem; border-bottom:1px solid var(--borde); }}

    .stats-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:1rem; margin:2rem 0 3rem; }}
    .stat-card {{ background:var(--card); border:1px solid var(--borde);
                 border-top:3px solid var(--dorado); border-radius:8px;
                 padding:1.5rem 1rem; text-align:center; }}
    .stat-card .stat-num {{ font-family:'Bebas Neue',sans-serif; font-size:clamp(2.2rem,5vw,3.2rem); color:var(--dorado); letter-spacing:2px; line-height:1; }}
    .stat-card .stat-label {{ color:var(--gris); font-size:0.8rem; text-transform:uppercase; letter-spacing:1.5px; margin-top:0.5rem; }}

    .pick-row {{
      display:grid;
      grid-template-columns: 110px minmax(0,1fr) 220px 90px 32px;
      gap:0.75rem; padding:0.85rem 1rem; background:var(--card);
      border:1px solid var(--borde); border-radius:8px;
      margin-bottom:0.4rem; align-items:center; font-size:0.92rem;
    }}
    .pick-fecha {{ color:var(--gris); font-family:monospace; font-size:0.82rem; }}
    .pick-matchup {{ color:var(--texto); overflow:hidden; text-overflow:ellipsis; }}
    .pick-matchup strong {{ color:#fff; font-weight:600; }}
    .pick-league {{ color:var(--gris); font-size:0.8rem; }}
    .pick-pred {{ color:var(--gris); font-size:0.86rem; }}
    .pick-bp   {{ color:var(--dorado); font-size:0.78rem; opacity:0.85; cursor:help; }}
    .pick-result {{ color:var(--gris); font-family:monospace; text-align:center; }}
    .pick-acerto {{ font-size:1.15rem; font-weight:bold; text-align:center; }}
    .pick-acerto.ok   {{ color:var(--verde); }}
    .pick-acerto.fail {{ color:var(--rojo); }}

    @media (max-width:720px) {{
      .stats-grid {{ grid-template-columns:1fr; }}
      .pick-row   {{
        grid-template-columns: 1fr 32px;
        grid-template-areas: "matchup acerto" "fecha acerto" "pred result";
        gap:0.3rem 0.6rem; padding:0.85rem 0.85rem;
      }}
      .pick-matchup {{ grid-area:matchup; font-size:0.95rem; }}
      .pick-fecha   {{ grid-area:fecha; }}
      .pick-pred    {{ grid-area:pred; font-size:0.82rem; }}
      .pick-result  {{ grid-area:result; text-align:right; }}
      .pick-acerto  {{ grid-area:acerto; font-size:1.4rem; }}
    }}

    .disclaimer {{
      max-width:780px; margin:2rem auto; padding:1rem 1.5rem;
      background:var(--card2); border-left:3px solid var(--dorado);
      border-radius:6px; color:var(--gris); font-size:0.9rem;
    }}
    .disclaimer strong {{ color:#fff; }}

    footer {{
      padding:2.5rem 2rem; border-top:1px solid var(--borde);
      text-align:center; color:var(--gris); font-size:0.85rem;
    }}
    .footer-logo {{ font-family:'Bebas Neue',sans-serif; font-size:1.4rem; letter-spacing:3px; color:var(--texto); margin-bottom:0.5rem; }}
    .footer-desc {{ max-width:560px; margin:0 auto 1.2rem; }}
    .footer-links {{ display:flex; justify-content:center; gap:1.2rem; flex-wrap:wrap; margin-bottom:1rem; }}
    .footer-links a {{ color:var(--gris); text-decoration:none; }}
    .footer-links a:hover {{ color:var(--dorado); }}
    .footer-copy {{ font-size:0.78rem; color:var(--borde); }}
  </style>
</head>
<body>

  <nav>
    <a href="/" class="logo">PREDI<span>KTOR</span></a>
    <div class="nav-links">
      <a href="/">Inicio</a>
      <a href="/metodologia.html">Metodología</a>
      <a href="/glosario.html">Glosario</a>
      <a href="/como-interpretar.html">Cómo usar</a>
      <a href="/guias/">Guías</a>
      <a href="/historial.html" class="active">Historial</a>
      <a href="/about.html">Sobre</a>
    </div>
  </nav>

  <article>
    <div class="breadcrumb"><a href="/">Inicio</a> · Historial</div>

    <h1>Historial<br><span>Verificado</span></h1>
    <p class="subtitle">Cada predicción que publicamos se contrasta automáticamente con el resultado oficial de ESPN al cierre del partido. Esta es la lista completa, sin filtros, ordenada por fecha. Sin retoques, sin "quitar" los fallos.</p>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-num">{pct}%</div>
        <div class="stat-label">Tasa de acierto</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{total}</div>
        <div class="stat-label">Predicciones verificadas</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{aciertos}</div>
        <div class="stat-label">Correctas</div>
      </div>
    </div>

    <h2>Predicciones</h2>
    <div class="pick-list">
      {rows}
    </div>

    <p class="subtitle" style="margin-top:2rem">Última actualización: <strong>{today}</strong>. Las predicciones se publican antes del partido y se cierran con el resultado oficial al final del día.</p>
  </article>

  <div class="disclaimer">⚠️ <strong>Aviso:</strong> PREDIKTOR es un sistema informativo de análisis estadístico. Las predicciones son orientativas, no garantías. Apuesta con responsabilidad.</div>

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


def patch_index_home(stats: dict) -> int:
    """
    Reescribe los 3 contadores del stats-bar en index.html con valores reales.
    Idempotente — funciona tanto si el placeholder es '…' como si es un valor
    numérico previo. No toca el JS que también los rellena.
    Retorna el número de reemplazos efectivos.
    """
    if not INDEX_PATH.exists():
        print(f"✗ No existe {INDEX_PATH}", file=sys.stderr)
        return 0

    src = INDEX_PATH.read_text(encoding="utf-8")
    out = src

    targets = [
        ("sb-pct",       f'{stats["pct"]}%'),
        ("sb-total",     str(stats["total"])),
        ("sb-correctas", str(stats["aciertos"])),
    ]
    replaced = 0
    for el_id, value in targets:
        pat = re.compile(
            rf'(<div id="{re.escape(el_id)}"[^>]*>)([^<]*)(</div>)'
        )
        new, n = pat.subn(rf'\g<1>{value}\g<3>', out)
        if n:
            out = new
            replaced += n

    if out != src:
        INDEX_PATH.write_text(out, encoding="utf-8")
    return replaced


def main() -> int:
    stats = load_stats()
    HISTORIAL_OUT.write_text(render_html(stats), encoding="utf-8")
    print(f"✓ historial.html → {stats['total']} picks "
          f"({stats['aciertos']} correctos, {stats['pct']}%)")

    n = patch_index_home(stats)
    print(f"✓ index.html → {n} contadores actualizados "
          f"(pct={stats['pct']}%, total={stats['total']}, "
          f"correctas={stats['aciertos']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
