#!/usr/bin/env python3
"""
Migra enlaces internos y canonicals/OG/JSON-LD de las páginas de contenido
al esquema de URLs limpias en español. NO toca static/predictions/* (esas se
resuelven por redirects 301 en vercel.json).

Idempotente. Uso: python3 scripts/clean_urls_links.py
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (nombre de archivo .html, ruta limpia destino)
PAIRS = [
    ("about.html", "/sobre"),
    ("privacy.html", "/privacidad"),
    ("como-interpretar.html", "/como-usar"),
    ("apuestas-legales.html", "/casas-autorizadas"),
    ("contacto.html", "/contacto"),
    ("metodologia.html", "/metodologia"),
    ("glosario.html", "/glosario"),
    ("historial.html", "/historial"),
    ("plan-pro.html", "/plan-pro"),
    ("que-es-ev-apuestas.html", "/guias/que-es-ev-apuestas"),
    ("gestion-de-bankroll.html", "/guias/gestion-de-bankroll"),
    ("value-bets.html", "/guias/value-bets"),
    ("estadisticas-futbol.html", "/guias/estadisticas-futbol"),
]

DOMAIN = "https://prediktorcol.com"


def transform(txt: str) -> tuple[str, int]:
    total = 0
    for fname, clean in PAIRS:
        base = re.escape(fname)
        # A) URLs absolutas (canonical, og:url, JSON-LD): preservar dominio.
        rxA = re.compile(rf"{re.escape(DOMAIN)}/(?:guias/)?{base}")
        txt, n = rxA.subn(f"{DOMAIN}{clean}", txt)
        total += n
        # B) Enlaces entre comillas (href/src), relativos o root-relativos.
        rxB = re.compile(rf"([\"'])/?(?:guias/)?{base}")
        txt, n = rxB.subn(rf"\g<1>{clean}", txt)
        total += n
    return txt, total


def main() -> int:
    files = sorted(ROOT.glob("*.html")) + sorted((ROOT / "guias").glob("*.html"))
    skip = {"googlec66bb31e7c99957b.html"}
    changed = 0
    repl = 0
    for f in files:
        if f.name in skip:
            continue
        txt = f.read_text(encoding="utf-8")
        new, n = transform(txt)
        if new != txt:
            f.write_text(new, encoding="utf-8")
            changed += 1
            repl += n
            print(f"  {f.relative_to(ROOT)}: {n} reemplazos")
    print(f"Archivos modificados: {changed} · reemplazos totales: {repl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
