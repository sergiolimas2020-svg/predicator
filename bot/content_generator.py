"""
Content generator — PREDIKTOR
Genera contenido mínimo diario cuando el motor no publica picks.

Regla: el canal y la web NUNCA deben quedar mudos. Si no hay picks de
valor, publicamos información útil sobre la jornada sin inventar apuestas.

Tipos de contenido generados:
  A) ANÁLISIS DEL DÍA — partidos destacados con info estadística (sin cuotas)
  B) AGENDA DEL DÍA — lista simple de partidos por liga
  C) JORNADA CERRADA — explicación honesta de por qué no hay picks

La elección del tipo depende del volumen de fixtures disponibles.
NO usa cuotas, NO calcula EV, NO recomienda apuestas.
"""
import json
import logging
from collections import defaultdict
from pathlib import Path

log = logging.getLogger("content_generator")

# Ruta a odds.json (la usamos solo para obtener fixtures, NO las cuotas)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ODDS_PATH = _PROJECT_ROOT / "static" / "odds.json"
_DAILY_CONTENT_PATH = _PROJECT_ROOT / "static" / "predictions" / "daily_content.json"

# Umbrales para decidir qué tipo de contenido generar
_MIN_FIXTURES_AGENDA  = 10  # ≥10 partidos → Tipo B (agenda)
_MIN_FIXTURES_ANALYSIS = 4  # ≥4 partidos → Tipo A (análisis)
# <4 partidos → Tipo C (explicación honesta)

# Ligas "destacadas" para el análisis — priorizar partidos de estas
_TOP_LEAGUES = {
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
    "Champions League", "Copa Libertadores", "Copa Sudamericana",
    "Liga Colombiana", "Liga Argentina", "Brasileirao", "NBA",
}


# ══════════════════════════════════════════════════════════════
#  LECTURA DE FIXTURES
# ══════════════════════════════════════════════════════════════

def _load_today_fixtures(date_str: str) -> list[dict]:
    """
    Obtiene los fixtures del día desde odds.json (solo nombres y ligas,
    NO extraemos cuotas porque no las vamos a mostrar).
    """
    if not _ODDS_PATH.exists():
        log.warning("odds.json no existe — no hay fixtures para contenido mínimo")
        return []
    try:
        data = json.loads(_ODDS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.error("Error leyendo odds.json: %s", e)
        return []

    fixtures = []
    for v in data.values():
        if v.get("date") != date_str:
            continue
        fixtures.append({
            "home": v.get("home", "?"),
            "away": v.get("away", "?"),
            "league": v.get("league", "?"),
        })
    log.info("Fixtures detectados para %s: %d partidos", date_str, len(fixtures))
    return fixtures


# ══════════════════════════════════════════════════════════════
#  GENERADORES DE CONTENIDO POR TIPO
# ══════════════════════════════════════════════════════════════

def _content_analisis(fixtures: list[dict], date_str: str) -> dict:
    """
    Tipo A: ANÁLISIS DEL DÍA
    Resalta partidos interesantes sin dar picks ni cuotas.
    Usa el ranking de ligas para priorizar los más relevantes.
    """
    # Agrupar por liga
    by_league = defaultdict(list)
    for f in fixtures:
        by_league[f["league"]].append(f)

    # Seleccionar los 3-5 partidos más destacados (ligas top primero)
    destacados = []
    for liga in sorted(by_league.keys(), key=lambda l: l not in _TOP_LEAGUES):
        for partido in by_league[liga]:
            destacados.append(partido)
            if len(destacados) >= 5:
                break
        if len(destacados) >= 5:
            break

    lineas = []
    for p in destacados:
        lineas.append(f"• {p['home']} vs {p['away']} ({p['league']})")

    body = (
        "Hoy el motor no detectó picks con valor estadístico claro, "
        "pero sí hay partidos interesantes en el calendario:\n\n"
        + "\n".join(lineas)
        + "\n\nEstos encuentros tienen probabilidades alineadas con el "
          "mercado — no hay diferencial aprovechable, pero son partidos "
          "para seguir."
    )

    return {
        "date": date_str,
        "type": "analisis",
        "title": "Análisis del día",
        "icon": "📝",
        "body": body,
        "fixtures": destacados,
        "total_fixtures": len(fixtures),
    }


def _content_agenda(fixtures: list[dict], date_str: str) -> dict:
    """
    Tipo B: AGENDA DEL DÍA
    Lista simple de partidos organizados por liga.
    """
    by_league = defaultdict(list)
    for f in fixtures:
        by_league[f["league"]].append(f)

    ligas_ordenadas = sorted(
        by_league.keys(),
        key=lambda l: (l not in _TOP_LEAGUES, l)
    )

    lineas = []
    for liga in ligas_ordenadas:
        partidos = by_league[liga]
        lineas.append(f"<b>{liga}</b> ({len(partidos)})")
        for p in partidos[:4]:  # máximo 4 por liga
            lineas.append(f"  • {p['home']} vs {p['away']}")
        if len(partidos) > 4:
            lineas.append(f"  · y {len(partidos) - 4} más")
        lineas.append("")  # separador

    body = (
        f"Jornada completa hoy con {len(fixtures)} partidos en "
        f"{len(by_league)} competiciones distintas:\n\n"
        + "\n".join(lineas).strip()
    )

    return {
        "date": date_str,
        "type": "agenda",
        "title": "Agenda del día",
        "icon": "📅",
        "body": body,
        "fixtures": fixtures,
        "total_fixtures": len(fixtures),
    }


def _content_sin_picks(fixtures: list[dict], date_str: str) -> dict:
    """
    Tipo C: POR QUÉ HOY NO HAY PICKS
    Explicación honesta para jornadas cortas o sin valor.
    """
    n = len(fixtures)
    if n == 0:
        razon = (
            "Hoy no hay partidos programados en las ligas que seguimos. "
            "El calendario es corto y la mayoría de competiciones descansan."
        )
    else:
        razon = (
            f"Hoy solo hay {n} partido{'s' if n != 1 else ''} en calendario, "
            "con cuotas muy ajustadas al modelo: las casas y nuestras "
            "probabilidades coinciden, y no hay diferencial aprovechable."
        )

    body = (
        f"<b>Por qué hoy no publicamos picks:</b>\n\n"
        f"{razon}\n\n"
        "No forzamos apuestas sin valor real. Preferimos un día sin picks "
        "a un día con picks inflados. Mañana volvemos con nuevas "
        "oportunidades cuando el mercado las ofrezca."
    )

    return {
        "date": date_str,
        "type": "sin_picks",
        "title": "Jornada sin valor claro",
        "icon": "📊",
        "body": body,
        "fixtures": fixtures,
        "total_fixtures": len(fixtures),
    }


# ══════════════════════════════════════════════════════════════
#  API PÚBLICA
# ══════════════════════════════════════════════════════════════

def generate_daily_content(date_str: str) -> dict:
    """
    Genera el contenido mínimo del día según la cantidad de fixtures
    disponibles. Siempre retorna un dict válido — nunca None.

    Uso:
        content = generate_daily_content("2026-04-24")
        telegram.send_message(format_content_for_telegram(content))
    """
    fixtures = _load_today_fixtures(date_str)
    n = len(fixtures)

    if n >= _MIN_FIXTURES_AGENDA:
        return _content_agenda(fixtures, date_str)
    elif n >= _MIN_FIXTURES_ANALYSIS:
        return _content_analisis(fixtures, date_str)
    else:
        return _content_sin_picks(fixtures, date_str)


def save_daily_content(content: dict) -> None:
    """Persiste el contenido mínimo en daily_content.json para la web."""
    _DAILY_CONTENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DAILY_CONTENT_PATH.write_text(
        json.dumps(content, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log.info("daily_content.json guardado: %s", _DAILY_CONTENT_PATH)


def format_content_for_telegram(content: dict) -> str:
    """Formatea el contenido para envío por Telegram (HTML)."""
    icon = content.get("icon", "📝")
    title = content.get("title", "Información del día")
    date = content.get("date", "—")
    body = content.get("body", "")

    return (
        f"{icon} <b>{title.upper()}</b>\n"
        f"📅 {date}\n"
        f"\n"
        f"{body}\n"
        f"\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 Volvemos a publicar picks cuando haya valor real"
    )
