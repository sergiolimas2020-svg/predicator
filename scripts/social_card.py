#!/usr/bin/env python3
"""
Generador de la PIEZA DIARIA para redes (TikTok/Instagram/Telegram).

A partir del pick del día que ya produce el motor (static/predictions/daily_picks.json),
crea automáticamente:
  - static/social/pick-YYYY-MM-DD.png  + static/social/today.png   (imagen 1080x1350)
  - static/social/caption-YYYY-MM-DD.txt + static/social/today.txt (texto + hashtags)
  - static/social/today.json  (metadatos que lee la página /social)

NO muestra cuotas (regla dura del proyecto): solo liga, partido, pick y probabilidad.
Uso:  python3 scripts/social_card.py [YYYY-MM-DD]
"""
from __future__ import annotations
import json
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT  = ROOT / "static" / "social"

# Paleta System A
NEGRO  = (10, 10, 15)
DORADO = (240, 180, 41)
BLANCO = (255, 255, 255)
GRIS   = (148, 163, 184)
BORDE  = (42, 42, 58)
ORO_TX = (42, 29, 0)   # texto sobre dorado

W, H = 1080, 1350

MESES = ["", "ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
         "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

# Candidatos de fuente bold (Mac primero, luego Ubuntu/CI, luego fallback).
_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
_REG = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _font(size: int, bold: bool = True):
    for p in (_BOLD if bold else _REG):
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _w(draw, text, font) -> float:
    return draw.textlength(text, font=font)


def _center(draw, y, text, font, fill):
    draw.text(((W - _w(draw, text, font)) / 2, y), text, font=font, fill=fill)


def _fit_font(draw, text, sizes, maxw, bold=True):
    """Devuelve la fuente más grande de `sizes` cuyo ancho de `text` cabe en maxw."""
    for s in sizes:
        f = _font(s, bold)
        if _w(draw, text, f) <= maxw:
            return f
    return _font(sizes[-1], bold)


def _wrap(draw, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for word in words:
        t = (cur + " " + word).strip()
        if _w(draw, t, font) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = word
    if cur:
        lines.append(cur)
    return lines


def _best_pick(data: dict):
    for k in ("pick_dia", "pick_gratuito", "pick_exploratorio"):
        v = data.get(k)
        if isinstance(v, dict):
            return v
    subs = data.get("picks_suscripcion") or []
    return subs[0] if subs else None


def _draw_card(pick: dict | None, d: date) -> Image.Image:
    img = Image.new("RGB", (W, H), NEGRO)
    dr = ImageDraw.Draw(img)
    dr.rounded_rectangle([28, 28, W - 28, H - 28], radius=28, outline=DORADO, width=3)

    # Encabezado de marca
    big = _font(82)
    pre_w, kt_w = _w(dr, "PREDI", big), _w(dr, "KTOR", big)
    x0 = (W - (pre_w + kt_w)) / 2
    dr.text((x0, 70), "PREDI", font=big, fill=BLANCO)
    dr.text((x0 + pre_w, 70), "KTOR", font=big, fill=DORADO)
    _center(dr, 188, "A N Á L I S I S   E S T A D Í S T I C O", _font(24, False), GRIS)
    dr.line([(340, 236), (W - 340, 236)], fill=BORDE, width=2)

    if not pick:
        _center(dr, 470, "HOY DESCANSAMOS", _font(72), DORADO)
        _center(dr, 580, "No hubo partidos que pasen", _font(34, False), BLANCO)
        _center(dr, 628, "nuestros filtros estrictos.", _font(34, False), BLANCO)
        _center(dr, 740, "Mejor sin pick que un mal pick.", _font(36), DORADO)
        _center(dr, 880, "El de mañana en", _font(32, False), GRIS)
        _center(dr, 930, "prediktorcol.com", _font(40), BLANCO)
    else:
        league  = str(pick.get("league", ""))
        matchup = str(pick.get("matchup", ""))
        market  = str(pick.get("market", ""))
        prob    = pick.get("prob_adjusted") or 0
        prob_pct = int(round(prob if prob > 1 else prob * 100))

        _center(dr, 286, "PICK DEL DÍA", _font(70), DORADO)
        _center(dr, 388, f"{d.day:02d} · {MESES[d.month]} · {d.year}", _font(30, False), GRIS)

        # Pill de liga
        lf = _fit_font(dr, league.upper(), [30, 28, 26, 24], 560)
        lw = _w(dr, league.upper(), lf)
        dr.rounded_rectangle([(W - lw) / 2 - 28, 446, (W + lw) / 2 + 28, 506],
                             radius=30, outline=DORADO, width=2)
        _center(dr, 458, league.upper(), lf, DORADO)

        # Partido (Equipo vs Equipo)
        if " vs " in matchup.lower():
            i = matchup.lower().index(" vs ")
            home, away = matchup[:i].strip(), matchup[i + 4:].strip()
        else:
            home, away = matchup, ""
        hf = _fit_font(dr, home, [56, 50, 44, 40], 900)
        _center(dr, 558, home, hf, BLANCO)
        _center(dr, 636, "VS", _font(34), DORADO)
        if away:
            af = _fit_font(dr, away, [56, 50, 44, 40], 900)
            _center(dr, 686, away, af, BLANCO)

        dr.line([(340, 786), (W - 340, 786)], fill=BORDE, width=2)
        _center(dr, 812, "NUESTRO PICK", _font(26, False), GRIS)

        mf = _fit_font(dr, market, [50, 46, 42], 880)
        lines = _wrap(dr, market, mf, 880)[:2]
        my = 858
        for ln in lines:
            _center(dr, my, ln, mf, BLANCO)
            my += mf.size + 8

        # Caja de probabilidad
        by0 = 980
        dr.rounded_rectangle([(W - 360) / 2, by0, (W + 360) / 2, by0 + 180],
                             radius=18, fill=DORADO)
        _center(dr, by0 + 14, f"{prob_pct}%", _font(112), ORO_TX)
        _center(dr, by0 + 148, "PROBABILIDAD DEL MODELO", _font(24), ORO_TX)

        _center(dr, 1196, "Sin corazonadas. Solo estadística.", _font(33), DORADO)

    dr.line([(340, H - 118), (W - 340, H - 118)], fill=BORDE, width=2)
    _center(dr, H - 96, "+18 · JUEGA CON RESPONSABILIDAD", _font(24, False), GRIS)
    _center(dr, H - 58, "prediktorcol.com", _font(32), BLANCO)
    return img


def _caption(pick: dict | None, d: date) -> str:
    if not pick:
        return ("📊 Hoy no publicamos pick: ningún partido pasó nuestros filtros "
                "estadísticos estrictos. Preferimos no dar un mal pick. 👉 "
                "prediktorcol.com\n\n#apuestas #pronosticos #futbol +18")
    league  = pick.get("league", "")
    matchup = pick.get("matchup", "")
    market  = pick.get("market", "")
    prob    = pick.get("prob_adjusted") or 0
    prob_pct = int(round(prob if prob > 1 else prob * 100))
    tag = "".join(c for c in league.lower() if c.isalnum())
    return (
        f"⚽ PICK DEL DÍA — {league}\n"
        f"{matchup}\n"
        f"📊 Nuestro modelo: {market} ({prob_pct}% de probabilidad)\n\n"
        f"Sin corazonadas, solo estadística. El historial completo y el pick de "
        f"mañana 👉 prediktorcol.com\n\n"
        f"#apuestas #{tag} #futbolcolombiano #pronosticos #predicciones #parley +18"
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1:
        y, m, dd = map(int, sys.argv[1].split("-"))
        d = date(y, m, dd)
        src = ROOT / "static" / "predictions" / f"value_picks_{sys.argv[1]}.json"
    else:
        src = ROOT / "static" / "predictions" / "daily_picks.json"
        d = None

    data = json.loads(src.read_text(encoding="utf-8")) if src.exists() else {}
    if d is None:
        ds = data.get("date")
        d = date(*map(int, ds.split("-"))) if ds else date.today()

    pick = _best_pick(data)
    img = _draw_card(pick, d)

    iso = d.isoformat()
    for name in (f"pick-{iso}.png", "today.png"):
        img.save(OUT / name, "PNG")
    cap = _caption(pick, d)
    for name in (f"caption-{iso}.txt", "today.txt"):
        (OUT / name).write_text(cap, encoding="utf-8")
    (OUT / "today.json").write_text(json.dumps({
        "date": iso,
        "has_pick": bool(pick),
        "league": (pick or {}).get("league"),
        "matchup": (pick or {}).get("matchup"),
        "market": (pick or {}).get("market"),
        "image": f"/static/social/pick-{iso}.png",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ pieza social {iso} → {'pick: ' + str(pick.get('matchup')) if pick else 'sin pick (tarjeta de descanso)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
