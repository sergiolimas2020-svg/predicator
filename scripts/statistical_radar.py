#!/usr/bin/env python3
"""
Radar estadístico PREDIKTOR — selector de mercado por PROBABILIDAD.

Motor probability-first: para cada partido busca el mercado donde la
estadística del modelo apoya una probabilidad ALTA de ocurrencia. NO usa
EV, cuotas ni Betplay estimado.

Alcance de esta entrega: Mundial/selecciones. NO está conectado a la
publicación premium global — es un artefacto radar/shadow para revisión.

Mercados evaluados:
  - Victoria directa   (todos)
  - Over 1.5 goles     (todos)
  - DNB                (SOLO selecciones; en clubes sigue bloqueado)
  - Doble oportunidad  (SOLO selecciones; en clubes sigue bloqueado)

Reglas:
  - Si un mercado no pasa su umbral, no es señal (se documenta por qué).
  - DNB/DC en clubes NO se evalúan (bloqueados globalmente por el blindaje).
  - Las señales DNB/DC de selección salen como `radar_only` (no oficiales).
    Victoria directa / Over 1.5 con respaldo API-Football son
    `official_eligible` pero ESTE radar NO publica: solo reporta.

Salida (artefactos; el motor de publicación NO los lee):
  static/statistical_radar.json
  static/_statistical_radar_report.md
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scrapers import generate_predictions as gp  # noqa: E402

RADAR_JSON = ROOT / "static" / "statistical_radar.json"
RADAR_REPORT = ROOT / "static" / "_statistical_radar_report.md"

# ── Umbrales iniciales (tunables) ──
RADAR_WIN_MIN    = 62.0   # Victoria directa
RADAR_OVER15_MIN = 72.0   # Over 1.5 goles
RADAR_DNB_MIN    = 72.0   # DNB — SOLO selecciones
RADAR_DC_MIN     = 80.0   # Doble oportunidad — SOLO selecciones

# Prioridad informativa para elegir el mercado recomendado entre los que pasan.
_PRIORITY = {
    "Victoria directa": 0,
    "Over 1.5 goles": 1,
    "DNB (apuesta sin empate)": 2,
    "Doble oportunidad": 3,
}


def _is_seleccion(league: str) -> bool:
    return league in gp.SELECCION_LEAGUES


def _market(name: str, pick, prob: float, threshold: float, tier: str) -> dict:
    passed = prob >= threshold
    reason = (f"prob {prob}% ≥ umbral {threshold}%" if passed
              else f"prob {prob}% < umbral {threshold}%")
    return {
        "market": name,
        "pick": pick,
        "prob": prob,
        "threshold": threshold,
        "passed": passed,
        "tier": tier,           # official_eligible | radar_only
        "reason": reason,
    }


def evaluate_match_radar(league: str, home: str, away: str, hd, ad,
                         neutral=None, source: str = "api_football") -> dict:
    """Evalúa los mercados de un partido y devuelve el dict de radar.

    Probability-first: reusa get_probabilities() del motor (mismas lambdas y
    fórmula). DNB/DC solo se evalúan para selecciones. Sin EV/cuotas/Betplay.
    """
    is_sel = _is_seleccion(league)
    probs = gp.get_probabilities(hd, ad, nba=False, danger=None,
                                 neutral=neutral, intl=is_sel)

    fav = probs.get("favorite")
    fav_team = home if fav == "home" else away
    win_prob = round(probs.get(f"win_{fav}", 0.0) * 100, 1)
    o15_prob = round(probs.get("over_1_5", 0.0) * 100, 1)

    markets = [
        _market("Victoria directa", fav_team, win_prob, RADAR_WIN_MIN,
                tier="official_eligible"),
        _market("Over 1.5 goles", None, o15_prob, RADAR_OVER15_MIN,
                tier="official_eligible"),
    ]

    # DNB / Doble Oportunidad: SOLO selecciones. En clubes quedan bloqueados
    # (el blindaje los mantiene fuera de picks oficiales globalmente), así que
    # ni siquiera se evalúan aquí.
    if is_sel:
        dnb_prob = round(probs.get(f"dnb_{fav}", 0.0) * 100, 1)
        dc_prob = round(probs.get(f"dc_{fav}", 0.0) * 100, 1)
        markets.append(_market("DNB (apuesta sin empate)", fav_team, dnb_prob,
                               RADAR_DNB_MIN, tier="radar_only"))
        markets.append(_market("Doble oportunidad", fav_team, dc_prob,
                               RADAR_DC_MIN, tier="radar_only"))

    passed = [m for m in markets if m["passed"]]
    recommended = None
    if passed:
        best = sorted(passed, key=lambda m: _PRIORITY[m["market"]])[0]
        recommended = {
            "market": best["market"],
            "pick": best["pick"],
            "prob": best["prob"],
            "tier": best["tier"],
        }

    return {
        "match": f"{home} vs {away}",
        "home": home,
        "away": away,
        "league": league,
        "is_seleccion": is_sel,
        "source": source,
        "neutral": neutral,
        "favorite": fav_team,
        "markets": markets,
        "recommended": recommended,
        "status": "signal" if recommended else "no_signal",
        "discarded": [
            {"market": m["market"], "prob": m["prob"],
             "threshold": m["threshold"], "reason": m["reason"]}
            for m in markets if not m["passed"]
        ],
    }


def _collect_seleccion_matches() -> list[tuple]:
    """(league, home, away, hd, ad, neutral) para Mundial + amistosos de hoy."""
    out = []
    wc = gp.worldcup_fixtures()
    if wc:
        wc_stats = gp.load("worldcup_stats.json")
        for home, away, neutral in wc:
            hd = gp.find(wc_stats, home)
            ad = gp.find(wc_stats, away)
            if not hd or not ad:
                continue
            out.append((gp.WORLD_CUP_LEAGUE, home, away, hd, ad, neutral))
    fr = gp.friendlies_fixtures()
    if fr:
        sel_stats = {**gp.load("worldcup_stats.json"),
                     **gp.load("friendlies_stats.json")}
        for home, away, neutral in fr:
            hd = gp.find(sel_stats, home)
            ad = gp.find(sel_stats, away)
            if not hd or not ad:
                continue
            out.append((gp.FRIENDLY_LEAGUE, home, away, hd, ad, neutral))
    return out


def _render_report(results: list[dict]) -> str:
    lines = [
        "# Radar estadístico — selección de mercado por probabilidad",
        "",
        f"Generado: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Motor probability-first. Busca el mercado donde la estadística apoya "
        "una probabilidad alta. **No usa EV, cuotas ni Betplay.** Alcance: "
        "Mundial/selecciones. **No conectado a publicación premium** — radar/shadow.",
        "",
        "Umbrales: Victoria directa ≥ "
        f"{RADAR_WIN_MIN}%, Over 1.5 ≥ {RADAR_OVER15_MIN}%, "
        f"DNB(selección) ≥ {RADAR_DNB_MIN}%, Doble oportunidad(selección) ≥ {RADAR_DC_MIN}%.",
        "",
    ]
    if not results:
        lines += ["_No hay partidos de selección hoy._", ""]
        return "\n".join(lines)

    signals = [r for r in results if r["status"] == "signal"]
    lines += [
        f"- Partidos evaluados: **{len(results)}**",
        f"- Con señal: **{len(signals)}**",
        "",
        "| Partido | Liga | Mercado recomendado | Prob | Fuente | Nivel | Razón / descarte |",
        "|---|---|---|---:|---|---|---|",
    ]
    for r in results:
        if r["recommended"]:
            rec = r["recommended"]
            pick = f" ({rec['pick']})" if rec["pick"] else ""
            mercado = f"{rec['market']}{pick}"
            prob = f"{rec['prob']}%"
            tier = "oficial-elegible" if rec["tier"] == "official_eligible" else "radar"
            razon = "supera umbral"
        else:
            mercado = "— sin señal —"
            prob = "—"
            tier = "—"
            razon = "; ".join(f"{d['market']} {d['prob']}%<{d['threshold']}%"
                              for d in r["discarded"]) or "—"
        lines.append(
            f"| {r['match']} | {r['league']} | {mercado} | {prob} | "
            f"{r['source']} | {tier} | {razon} |"
        )
    lines.append("")

    # Detalle por partido (todos los mercados evaluados)
    lines += ["## Detalle por partido", ""]
    for r in results:
        lines.append(f"### {r['match']} ({r['league']})")
        lines.append("")
        lines.append("| Mercado | Pick | Prob | Umbral | ¿Pasa? | Nivel |")
        lines.append("|---|---|---:|---:|---|---|")
        for m in r["markets"]:
            pick = m["pick"] or "—"
            ok = "✓" if m["passed"] else "✗"
            tier = "oficial-elegible" if m["tier"] == "official_eligible" else "radar"
            lines.append(
                f"| {m['market']} | {pick} | {m['prob']}% | {m['threshold']}% | {ok} | {tier} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    matches = _collect_seleccion_matches()
    results = [evaluate_match_radar(*m[:5], neutral=m[5]) for m in matches]

    artifact = {
        "is_radar": True,
        "note": ("Radar estadístico probability-first (Mundial/selecciones). "
                 "No usa EV/cuotas/Betplay. NO conectado a publicación premium; "
                 "el motor de publicación no lee este archivo."),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "thresholds": {
            "win": RADAR_WIN_MIN, "over_1_5": RADAR_OVER15_MIN,
            "dnb_seleccion": RADAR_DNB_MIN, "dc_seleccion": RADAR_DC_MIN,
        },
        "matches": results,
    }
    RADAR_JSON.write_text(json.dumps(artifact, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    RADAR_REPORT.write_text(_render_report(results), encoding="utf-8")

    n_sig = sum(1 for r in results if r["status"] == "signal")
    print(f"Radar JSON:   {RADAR_JSON}")
    print(f"Radar report: {RADAR_REPORT}")
    print(f"partidos={len(results)} con_senal={n_sig}")
    for r in results:
        rec = r["recommended"]
        tag = f"{rec['market']} {rec['prob']}%" if rec else "sin señal"
        print(f"  {r['match']:30} → {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
