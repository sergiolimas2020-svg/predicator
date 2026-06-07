#!/usr/bin/env python3
"""
Limpia la prosa legacy de cuota/valor-vs-bookmaker en páginas históricas de pick.

Estas páginas quedaron congeladas con texto de versiones viejas del generador
que prometían "cuota justa", "ventaja matematica sobre el bookmaker", "hay valor
a tu favor", etc. Eso contradice la regla dura del proyecto: NO afirmamos nada
sobre cuotas (no las tenemos). Reescribe los párrafos a versión solo-probabilidad,
conservando el % (dato que sí tenemos).

Idempotente: si no encuentra la plantilla, no toca el archivo.
Uso:  python3 scripts/strip_legacy_cuota.py
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRED = ROOT / "static" / "predictions"

# (regex, replacement) — la prob (%) se captura en grupo 1; el rango en grupo 2 si aplica.
T1 = (
    re.compile(
        r"<p>Nuestra probabilidad estadistica es <strong>([\d.]+)%</strong>, "
        r"lo que equivale a una cuota justa de <strong>[\d.]+</strong>\. "
        r"Esto significa que si encuentras este mercado en tu bookmaker a una "
        r"cuota igual o superior a <strong>[\d.]+</strong>, matematicamente hay "
        r"valor a tu favor\. Los mercados con probabilidades en este rango "
        r"\(([\d]+-[\d]+%)\) son los que los bookmakers suelen sub-valorar "
        r"frente a los grandes favoritos — aqui esta la oportunidad\.</p>"
    ),
    lambda m: (
        f"<p>Nuestra probabilidad estadistica para este mercado es "
        f"<strong>{m.group(1)}%</strong>. Es una de las mas altas del dia: "
        f"priorizamos los partidos donde el modelo proyecta mayor certeza a "
        f"partir de la forma reciente, los goles esperados y la fuerza relativa "
        f"de los equipos. El rango {m.group(2)} es, segun nuestro historico de "
        f"calibracion, uno de los mas fiables del modelo.</p>"
    ),
)

T2 = (
    re.compile(
        r"<p>Nuestra probabilidad es <strong>([\d.]+)%</strong> "
        r"\(cuota justa <strong>[\d.]+</strong>\)\. Hay margen de valor si el "
        r"bookmaker ofrece una cuota igual o superior\. Recomendamos comparar "
        r"lineas en al menos dos casas antes de apostar — una diferencia de "
        r"[\d.]+-[\d.]+ en la cuota puede ser la diferencia entre valor "
        r"positivo y negativo\.</p>"
    ),
    lambda m: (
        f"<p>Nuestra probabilidad estadistica para este mercado es "
        f"<strong>{m.group(1)}%</strong>. Recuerda que es un analisis "
        f"estadistico, no una garantia: apuesta siempre con responsabilidad y "
        f"solo lo que estes dispuesto a arriesgar.</p>"
    ),
)

T3 = (
    re.compile(
        r"<p>Nuestro modelo asigna a este resultado una probabilidad del "
        r"<strong>([\d.]+)%</strong>, lo que equivale a una cuota justa de "
        r"<strong>[\d.]+</strong>\. Si tu casa de apuestas paga igual o mas "
        r"que esa cuota, tienes ventaja matematica real\.</p>"
    ),
    lambda m: (
        f"<p>Nuestro modelo asigna a este resultado una probabilidad del "
        f"<strong>{m.group(1)}%</strong>, calculada con un modelo de Poisson "
        f"sobre goles esperados, forma reciente y fuerza relativa de los "
        f"equipos. Es el factor que mas pesa en nuestra seleccion de picks.</p>"
    ),
)

# Filas estructurales de cuota/edge dentro de .sbox — eliminar el div completo.
# Cubre: "Cuota justa", "Cuota minima con valor", "Cuota real (mejor bookmaker)",
# "Edge sobre el bookmaker". Conserva "Probabilidad estimada (modelo)".
ROW = re.compile(
    r"[ \t]*<div class=\"srow\"><span class=\"slbl\">"
    r"(?:Cuota[^<]*|Edge sobre el bookmaker)</span>"
    r"<span[^>]*>[^<]*</span></div>\n?"
)

# --- Variantes adicionales (NBA + colombiana) ---
T4 = (
    re.compile(
        r"<p>Probabilidad estimada: <strong>([\d.]+)%</strong>\. La cuota justa "
        r"para este resultado es <strong>[\d.]+</strong>\. Compara con tu casa "
        r"de apuestas — si pagan esa cuota o mas, hay valor\.</p>"
    ),
    lambda m: (
        f"<p>Probabilidad estimada por el modelo: <strong>{m.group(1)}%</strong>. "
        f"Es un analisis estadistico, no una garantia: apuesta con responsabilidad.</p>"
    ),
)

T5 = (
    re.compile(
        r"<p>Este resultado es demasiado favorito\. Los bookmakers pagan poco "
        r"\(cuota justa ~[\d.]+\)\. <strong>No representa valor apostable</strong> "
        r"— es predecible pero no rentable a largo plazo\.</p>"
    ),
    lambda m: (
        "<p>Este resultado es un favorito demasiado claro: la probabilidad es "
        "muy alta pero tambien muy evidente. <strong>No lo destacamos como "
        "pick</strong> — preferimos mercados donde el modelo aporta mas que lo obvio.</p>"
    ),
)

T6 = (
    re.compile(
        r"<p>Nuestro modelo 3-way asigna a este resultado una probabilidad del "
        r"<strong>([\d.]+)%</strong>, equivalente a una cuota justa de "
        r"<strong>[\d.]+</strong>\. Si encuentras este mercado a una cuota igual "
        r"o superior, tienes ventaja matematica sobre el bookmaker\.</p>"
    ),
    lambda m: (
        f"<p>Nuestro modelo 3-way asigna a este resultado una probabilidad del "
        f"<strong>{m.group(1)}%</strong>, calculada sobre goles esperados, forma "
        f"reciente y fuerza relativa de los equipos.</p>"
    ),
)

TEMPLATES = [T1, T2, T3, T4, T5, T6]

# Bloque visual: columna "Cuota actual" (se elimina, queda la de Probabilidad).
CUOTA_COL = re.compile(
    r"<div><div style=\"[^\"]*\">Cuota actual</div>"
    r"<div style=\"[^\"]*\">[\d.]+</div></div>"
)
# Advertencia sobre la cuota.
WARN = re.compile(
    r"<div style=\"[^\"]*\">⚠️ La cuota en tu casa de apuestas puede variar "
    r"— verifica antes de apostar</div>"
)


def main() -> int:
    changed = 0
    counts = {f"T{i}": 0 for i in range(1, len(TEMPLATES) + 1)}
    counts.update({"row": 0, "col": 0, "warn": 0})
    for f in sorted(PRED.glob("*.html")):
        txt = f.read_text(encoding="utf-8")
        orig = txt
        for i, (rx, rep) in enumerate(TEMPLATES, 1):
            txt, n = rx.subn(rep, txt)
            counts[f"T{i}"] += n
        txt, nr = ROW.subn("", txt)
        counts["row"] += nr
        txt, nc = CUOTA_COL.subn("", txt)
        counts["col"] += nc
        txt, nw = WARN.subn("", txt)
        counts["warn"] += nw
        if txt != orig:
            f.write_text(txt, encoding="utf-8")
            changed += 1
    print(f"Archivos modificados: {changed}")
    for k in counts:
        print(f"  {k:5s}: {counts[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
