#!/usr/bin/env python3
"""
Scraper del Mundial 2026 (selecciones) vía API-Football.

A diferencia de las ligas de clubes, las selecciones NO tienen una tabla de
posiciones útil antes/durante la fase de grupos del Mundial. Por eso la fuerza
de cada selección se deriva de su FORMA RECIENTE en partidos internacionales
reales (eliminatorias, amistosos, Nations League, torneos continentales):

  - ataque/defensa  →  goles a favor/contra en sus últimos N partidos jugados.
  - Elo de selección →  se calcula procesando cronológicamente el histórico
                        internacional de las 48 selecciones, reusando la misma
                        fórmula FIFA-Elo de scrapers/elo_ratings.py.

Salidas:
  static/worldcup_stats.json                       (formato compatible con el motor)
  static/api_football/elo_ratings.json["World Cup"] (Elo por selección)

API-Football (verificado jun-2026):
  liga FIFA World Cup → id=1, season=2026, 48 equipos, 104 partidos.
  Endpoints usados:
    /teams?league=1&season=2026               → las 48 selecciones
    /fixtures?team={id}&last={N}              → forma reciente (todas las comp.)

Carga estimada: 48 equipos × 1 request (forma) + 1 (teams) ≈ 50 requests/run.
Para Elo con histórico profundo (last≈40) sigue siendo <60 requests. Holgado
sobre el plan Pro (7.500/día).

Uso:
  python -m scrapers.worldcup                 # stats + elo, escribe los JSON
  python -m scrapers.worldcup --form-last 15  # ventana de forma personalizada
  python -m scrapers.worldcup --dry-run       # imprime sin escribir
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.api_football.client import (  # noqa: E402
    APIFootballClient,
    APIFootballError,
    APIFootballRateLimitError,
)
from scrapers.elo_ratings import calculate_elo_update, ELO_BASE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATS_OUTPUT = ROOT / "static" / "worldcup_stats.json"
FIXTURES_OUTPUT = ROOT / "static" / "worldcup_fixtures.json"
FRIENDLIES_STATS_OUTPUT = ROOT / "static" / "friendlies_stats.json"
FRIENDLIES_FIXTURES_OUTPUT = ROOT / "static" / "friendlies_fixtures.json"
ELO_OUTPUT = ROOT / "static" / "api_football" / "elo_ratings.json"

# Identificadores del Mundial en API-Football
WORLD_CUP_LEAGUE_ID = 1
WORLD_CUP_SEASON = 2026
ELO_KEY = "World Cup"

# Amistosos de selecciones absolutas (masculinas) en API-Football
FRIENDLIES_LEAGUE_ID = 10
FRIENDLIES_SEASON = 2026
FRIENDLIES_WINDOW_DAYS = 12   # cuántos días hacia adelante cubrir
# Patrones que marcan un equipo NO absoluto (juvenil/femenino) → se excluye.
import re as _re
_NON_SENIOR_RE = _re.compile(r"(?:\bU-?\d{2}\b|\bU\d{2}\b|\bWomen\b|\bW\b|Olympic|\bB\b|\bXI\b)", _re.I)

# Sedes anfitrionas: estas selecciones SÍ juegan con localía real.
# El resto de partidos del Mundial son en cancha neutral.
HOST_NATIONS = {"USA", "United States", "Canada", "Mexico"}

# Ventanas por defecto (nº de partidos internacionales hacia atrás).
DEFAULT_FORM_LAST = 12   # forma reciente para ataque/defensa
DEFAULT_ELO_LAST = 40    # histórico para asentar el Elo de selección

# Estados de partido considerados "jugado".
FINISHED_STATUSES = {"FT", "AET", "PEN"}

# ── Elo real de selecciones (World Football Elo / eloratings.net) ──────────
# Fuente: Wikipedia "Module:SportsRankings/data/World_Football_Elo_Ratings",
# valores actualizados 2026-06-01. Es el estándar de oro para fuerza de
# selecciones (a diferencia de los clubes, API-Football NO expone Elo, y
# derivarlo arrancando todos en 1500 produce ordenamientos falsos por sesgo
# regional). Keyed por el nombre EXACTO que devuelve API-Football (league=1).
# Revisar/actualizar al inicio del Mundial corriendo otra vez la captura.
ELO_SEED: Dict[str, float] = {
    "Spain": 2165, "Argentina": 2113, "France": 2081, "England": 2020,
    "Brazil": 1988, "Portugal": 1984, "Colombia": 1977, "Netherlands": 1961,
    "Ecuador": 1935, "Croatia": 1930, "Germany": 1925, "Norway": 1917,
    "Türkiye": 1906, "Japan": 1906, "Switzerland": 1894, "Uruguay": 1892,
    "Mexico": 1868, "Belgium": 1866, "Senegal": 1866, "Italy": 1856,
    "Paraguay": 1833, "Austria": 1830, "Morocco": 1822, "Canada": 1793,
    "Australia": 1775, "Scotland": 1770, "Iran": 1764, "South Korea": 1756,
    "Algeria": 1743, "Panama": 1733, "Czech Republic": 1733, "USA": 1733,
    "Uzbekistan": 1718, "Sweden": 1714, "Egypt": 1699, "Jordan": 1685,
    "Ivory Coast": 1676, "Congo DR": 1655, "Tunisia": 1633, "Iraq": 1608,
    "Bosnia & Herzegovina": 1591, "New Zealand": 1585, "Cape Verde Islands": 1576,
    "Saudi Arabia": 1566, "Haiti": 1532, "South Africa": 1517, "Ghana": 1503,
    "Curaçao": 1433, "Qatar": 1423,
}
# Default conservador para una selección sin seed (debería ser raro: todas las
# del Mundial están arriba). Media-baja del pool de selecciones.
ELO_DEFAULT = 1500.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("worldcup")


# ──────────────────────────────────────────────────────────────────────────
#  Funciones puras (testeables sin red)
# ──────────────────────────────────────────────────────────────────────────
def is_finished(fx: Dict[str, Any]) -> bool:
    status = fx.get("fixture", {}).get("status", {}).get("short")
    return status in FINISHED_STATUSES


def extract_match(fx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normaliza un fixture de API-Football a un dict plano, o None si inválido.

    Devuelve: {fixture_id, ts, home_id, home, away_id, away, gh, ga}
    """
    teams = fx.get("teams", {})
    home = teams.get("home", {}) or {}
    away = teams.get("away", {}) or {}
    goals = fx.get("goals", {}) or {}
    gh, ga = goals.get("home"), goals.get("away")
    home_name, away_name = home.get("name"), away.get("name")
    if not home_name or not away_name or gh is None or ga is None:
        return None
    return {
        "fixture_id": fx.get("fixture", {}).get("id"),
        "ts": fx.get("fixture", {}).get("timestamp", 0) or 0,
        "home_id": home.get("id"),
        "home": home_name,
        "away_id": away.get("id"),
        "away": away_name,
        "gh": int(gh),
        "ga": int(ga),
    }


def compute_team_form(
    matches: List[Dict[str, Any]], team_id: int, team_name: str, max_matches: int
) -> Dict[str, Any]:
    """Calcula goles a favor/contra y récord de una selección desde sus partidos.

    `matches` = lista de matches normalizados (cualquier orden); se toman los
    `max_matches` más recientes en los que participa `team_id`.
    Función PURA — sin red, testeable con fixtures mock.
    """
    mine = [m for m in matches if team_id in (m.get("home_id"), m.get("away_id"))]
    mine.sort(key=lambda m: m.get("ts", 0), reverse=True)
    mine = mine[:max_matches]

    gf = gc = ganados = empatados = perdidos = 0
    for m in mine:
        is_home = m.get("home_id") == team_id
        scored = m["gh"] if is_home else m["ga"]
        conceded = m["ga"] if is_home else m["gh"]
        gf += scored
        gc += conceded
        if scored > conceded:
            ganados += 1
        elif scored == conceded:
            empatados += 1
        else:
            perdidos += 1

    n = len(mine)
    return {
        "corners": {},
        "goals": {},
        "position": {
            "posicion": 0,            # sin tabla en fase de grupos
            "partidos": n,
            "ganados": ganados,
            "empatados": empatados,
            "perdidos": perdidos,
            "goles_favor": gf,
            "goles_contra": gc,
            "diferencia": gf - gc,
            "puntos": ganados * 3 + empatados,
        },
        "_source": "api_football:form",
        "_team_id": team_id,
        "_team_name": team_name,
    }


def is_neutral_venue(home_name: str, host_nations=HOST_NATIONS) -> bool:
    """En el Mundial todo partido es en cancha neutral SALVO cuando el equipo
    designado 'local' es una selección anfitriona (USA/Canadá/México) jugando
    en su país. Aproximación: neutral salvo que el local sea anfitrión.
    """
    return home_name not in host_nations


def parse_schedule(fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normaliza la respuesta de /fixtures (calendario completo) a una lista
    ligera: [{date, home, away, venue, neutral, status}]. Función PURA.

    Incluye partidos NO jugados (el calendario es a futuro); por eso no exige
    goles, solo nombres y fecha.
    """
    out = []
    for fx in fixtures:
        teams = fx.get("teams", {}) or {}
        home = (teams.get("home") or {}).get("name")
        away = (teams.get("away") or {}).get("name")
        finfo = fx.get("fixture", {}) or {}
        date_iso = finfo.get("date")
        if not home or not away or not date_iso:
            continue
        venue = (finfo.get("venue") or {}).get("name")
        out.append({
            "date": date_iso,
            "home": home,
            "away": away,
            "venue": venue,
            "neutral": is_neutral_venue(home),
            "status": (finfo.get("status") or {}).get("short"),
            "round": (fx.get("league") or {}).get("round"),
        })
    return out


def _norm_team(name: str) -> str:
    """Normaliza un nombre de selección para emparejar contra ELO_SEED:
    minúsculas, sin tildes, alfanumérico. Tolera variantes de grafía."""
    import unicodedata
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _load_national_elo() -> Dict[str, float]:
    """Carga static/national_elo.json (Elo real ampliado, ~150 selecciones) y
    lo fusiona con ELO_SEED (las 48 del Mundial mandan). Cacheado por proceso."""
    table = dict(ELO_SEED)
    p = ROOT / "static" / "national_elo.json"
    if p.exists():
        try:
            data = json.loads(p.read_text())
            ratings = data.get("ratings", data)  # tolera formato plano
            for k, v in ratings.items():
                table.setdefault(k, float(v))  # WC seed tiene prioridad
        except Exception as e:
            logger.warning("national_elo.json no se pudo leer: %s", e)
    return table


_NATIONAL_ELO = _load_national_elo()
_NATIONAL_ELO_NORM = {_norm_team(k): v for k, v in _NATIONAL_ELO.items()}

# Alias API-Football ↔ World Football Elo (grafías que la normalización no cubre)
_ELO_ALIASES = {
    "turkey": "Türkiye", "drcongo": "Congo DR", "democraticrepublicofthecongo": "Congo DR",
    "capeverde": "Cape Verde Islands", "unitedstates": "USA", "usmnt": "USA",
    "southkorea": "South Korea", "korearepublic": "South Korea",
    "bosniaandherzegovina": "Bosnia & Herzegovina", "ivorycoast": "Ivory Coast",
    "cotedivoire": "Ivory Coast", "curacao": "Curaçao", "ireland": "Republic of Ireland",
    "kyrgyzrepublic": "Kyrgyzstan", "czechia": "Czech Republic", "uae": "United Arab Emirates",
}


def seed_elo_for(name: str) -> Optional[float]:
    """Elo real (World Football Elo) de una selección por nombre, o None.

    Empareja exacto → normalizado (sin tildes/espacios) → alias de grafía.
    Cubre ~150 selecciones (Mundial + amistosos), no solo las 48 del Mundial.
    """
    if name in _NATIONAL_ELO:
        return _NATIONAL_ELO[name]
    n = _norm_team(name)
    if n in _NATIONAL_ELO_NORM:
        return _NATIONAL_ELO_NORM[n]
    canon = _ELO_ALIASES.get(n)
    if canon:
        return _NATIONAL_ELO.get(canon) or _NATIONAL_ELO_NORM.get(_norm_team(canon))
    return None


def compute_elo_pool(matches: List[Dict[str, Any]]) -> Dict[str, float]:
    """Elo cronológico sobre un pool de partidos internacionales (todas las
    selecciones a la vez). Función PURA — reusa la fórmula FIFA-Elo del proyecto.

    Dedup por fixture_id (un partido entre dos selecciones del Mundial aparece
    en el histórico de ambas). Inicializa todas en ELO_BASE.

    NOTA: para el Mundial, build() prefiere ELO_SEED (Elo real) sobre esta
    derivación dinámica, que sólo se usa como respaldo de robustez.
    """
    seen = set()
    unique: List[Dict[str, Any]] = []
    for m in matches:
        fid = m.get("fixture_id")
        key = fid if fid is not None else (m["ts"], m["home"], m["away"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)

    unique.sort(key=lambda m: m.get("ts", 0))  # cronológico ascendente

    elos: Dict[str, float] = {}
    for m in unique:
        h, a = m["home"], m["away"]
        elos.setdefault(h, ELO_BASE)
        elos.setdefault(a, ELO_BASE)
        dh, da = calculate_elo_update(elos[h], elos[a], m["gh"], m["ga"])
        elos[h] += dh
        elos[a] += da
    return {team: round(v, 1) for team, v in elos.items()}


# ──────────────────────────────────────────────────────────────────────────
#  Acceso a red (API-Football)
# ──────────────────────────────────────────────────────────────────────────
def fetch_wc_teams(client: APIFootballClient) -> List[Dict[str, Any]]:
    """Las 48 selecciones del Mundial 2026: [{id, name}, ...]."""
    resp = client.get_teams(WORLD_CUP_LEAGUE_ID, WORLD_CUP_SEASON)
    out = []
    for item in resp.get("response", []):
        team = item.get("team", {}) or {}
        if team.get("id") and team.get("name"):
            out.append({"id": team["id"], "name": team["name"]})
    return out


def fetch_wc_schedule(client: APIFootballClient) -> List[Dict[str, Any]]:
    """Calendario completo del Mundial 2026 (104 partidos), normalizado.

    Una sola request a /fixtures de toda la temporada (mismo patrón que
    elo_ratings.compute_league_elo).
    """
    resp = client._request(
        "/fixtures", {"league": WORLD_CUP_LEAGUE_ID, "season": WORLD_CUP_SEASON}
    )
    return parse_schedule(resp.get("response", []))


def is_senior_national(name: str) -> bool:
    """True si el nombre es una selección ABSOLUTA masculina (no U17/U20/U23,
    no femenina, no 'B'/olímpica). Filtra ruido de los amistosos."""
    if not name:
        return False
    return _NON_SENIOR_RE.search(name) is None


def fetch_friendlies_raw(client: APIFootballClient) -> List[Dict[str, Any]]:
    """Fixtures crudos de amistosos de selecciones (league=10, season actual)."""
    resp = client._request(
        "/fixtures", {"league": FRIENDLIES_LEAGUE_ID, "season": FRIENDLIES_SEASON}
    )
    return resp.get("response", [])


FRIENDLY_STRONG_ELO = 1700  # umbral para considerar "fuerte" una selección sin Mundial

def select_upcoming_friendlies(raw, today: str, window_days: int,
                               wc_teams=None,
                               min_strong_elo: int = FRIENDLY_STRONG_ELO) -> List[Dict[str, Any]]:
    """Filtra amistosos jugables y RELEVANTES (preparación Mundial): por jugar,
    dentro de la ventana, AMBOS equipos absolutos y con Elo real, y además
    RELEVANTE = al menos una selección mundialista O ambas fuertes (Elo alto).
    Esto descarta amistosos de minnows tipo Vanuatu vs Fiji. Función PURA.

    `wc_teams`: set de nombres de selecciones del Mundial (None = solo filtra
    por Elo)."""
    wc_teams = wc_teams or set()
    t0 = datetime.strptime(today, "%Y-%m-%d").date()
    t1 = t0 + timedelta(days=window_days)
    out = []
    for fx in raw:
        finfo = fx.get("fixture", {}) or {}
        status = (finfo.get("status") or {}).get("short")
        if status not in ("NS", "TBD"):  # solo por jugar
            continue
        date_iso = finfo.get("date") or ""
        try:
            d = datetime.fromisoformat(date_iso.replace("Z", "+00:00")).date()
        except Exception:
            continue
        if not (t0 <= d <= t1):
            continue
        teams = fx.get("teams", {}) or {}
        home = teams.get("home", {}) or {}
        away = teams.get("away", {}) or {}
        hn, an = home.get("name"), away.get("name")
        if not hn or not an:
            continue
        if not (is_senior_national(hn) and is_senior_national(an)):
            continue
        eh, ea = seed_elo_for(hn), seed_elo_for(an)
        if eh is None or ea is None:
            continue  # sin Elo real en ambos → no es fidedigno, se omite
        # Relevancia: al menos un mundialista, o ambas selecciones fuertes.
        es_mundialista = hn in wc_teams or an in wc_teams
        ambas_fuertes = eh >= min_strong_elo and ea >= min_strong_elo
        if not (es_mundialista or ambas_fuertes):
            continue
        out.append({
            "date": date_iso, "home": hn, "home_id": home.get("id"),
            "away": an, "away_id": away.get("id"),
            "venue": (finfo.get("venue") or {}).get("name"),
        })
    return out


def build_friendlies(client: APIFootballClient, today: str,
                     form_last: int = DEFAULT_FORM_LAST,
                     window_days: int = FRIENDLIES_WINDOW_DAYS,
                     wc_stats: Optional[Dict[str, Any]] = None):
    """Stats + calendario de los amistosos de selecciones próximos.

    Reusa stats de equipos del Mundial si ya están en wc_stats; para el resto
    descarga su forma. Elo siempre real (national_elo). Venue tratado como
    NEUTRAL (conservador: no asumir localía que quizá no exista en un amistoso).
    """
    wc_stats = wc_stats or {}
    raw = fetch_friendlies_raw(client)
    fixtures = select_upcoming_friendlies(raw, today, window_days,
                                          wc_teams=set(wc_stats.keys()))
    logger.info("Amistosos de selecciones relevantes (ventana %dd): %d", window_days, len(fixtures))

    # Equipos únicos (id, name) que necesitan stats y no están ya en el Mundial
    need: Dict[int, str] = {}
    for fx in fixtures:
        for nm, tid in ((fx["home"], fx["home_id"]), (fx["away"], fx["away_id"])):
            if nm not in wc_stats and tid and nm not in {v for v in need.values()}:
                need[tid] = nm

    stats: Dict[str, Any] = {}
    for tid, nm in need.items():
        try:
            hist = fetch_team_history(client, tid, last=form_last)
        except APIFootballError as e:
            logger.warning("Sin forma para %s: %s", nm, e)
            hist = []
        form = compute_team_form(hist, tid, nm, form_last)
        form["elo"] = round(float(seed_elo_for(nm)), 1)
        form["elo_source"] = "world_football_elo"
        form["host"] = False
        stats[nm] = form
        logger.info("  %-22s Elo %.0f  (%d partidos forma)", nm, form["elo"], form["position"]["partidos"])

    schedule = [{
        "date": fx["date"], "home": fx["home"], "away": fx["away"],
        "venue": fx["venue"], "neutral": True, "status": "NS", "round": "Amistoso",
    } for fx in fixtures]
    return stats, schedule


def fetch_team_history(client: APIFootballClient, team_id: int, last: int) -> List[Dict[str, Any]]:
    """Últimos `last` partidos jugados de una selección (todas las competiciones)."""
    resp = client.get_team_last_fixtures(team_id, last=last)
    matches = []
    for fx in resp.get("response", []):
        if not is_finished(fx):
            continue
        m = extract_match(fx)
        if m:
            matches.append(m)
    return matches


def build(
    client: APIFootballClient,
    form_last: int = DEFAULT_FORM_LAST,
    elo_last: int = DEFAULT_ELO_LAST,
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """Construye stats y Elo de las 48 selecciones. Una sola pasada de red:
    descarga el histórico (elo_last) por equipo y reutiliza esos mismos
    partidos tanto para la forma (recortada a form_last) como para el Elo.
    """
    teams = fetch_wc_teams(client)
    logger.info("Selecciones del Mundial encontradas: %d", len(teams))
    if not teams:
        raise APIFootballError("API-Football no devolvió equipos para league=1 season=2026")

    history_by_team: Dict[int, List[Dict[str, Any]]] = {}
    pool: List[Dict[str, Any]] = []
    depth = max(form_last, elo_last)

    for t in teams:
        try:
            hist = fetch_team_history(client, t["id"], last=depth)
        except APIFootballRateLimitError:
            logger.error("Rate limit alcanzado en %s — abortando recolección.", t["name"])
            raise
        except APIFootballError as e:
            logger.warning("Sin histórico para %s: %s", t["name"], e)
            hist = []
        history_by_team[t["id"]] = hist
        pool.extend(hist)
        logger.info("  %-18s %d partidos", t["name"], len(hist))

    # Elo dinámico (respaldo) sobre el histórico real, por si falta algún seed.
    dynamic_elos = compute_elo_pool(pool)

    stats: Dict[str, Any] = {}
    wc_elos: Dict[str, float] = {}
    seeded = 0
    for t in teams:
        name = t["name"]
        form = compute_team_form(history_by_team[t["id"]], t["id"], name, form_last)
        # Prioridad: Elo REAL (World Football Elo) → dinámico → default.
        elo_val = seed_elo_for(name)
        if elo_val is not None:
            form["elo_source"] = "world_football_elo"
            seeded += 1
        else:
            elo_val = dynamic_elos.get(name, ELO_DEFAULT)
            form["elo_source"] = "dynamic" if name in dynamic_elos else "default"
            logger.warning("Sin seed de Elo para '%s' → %s (%.0f)",
                           name, form["elo_source"], elo_val)
        form["elo"] = round(float(elo_val), 1)
        form["host"] = name in HOST_NATIONS
        stats[name] = form
        wc_elos[name] = form["elo"]

    logger.info("Elo: %d/%d selecciones con valor real (World Football Elo)",
                seeded, len(teams))
    return stats, wc_elos


# ──────────────────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────────────────
def _load_api_key() -> Optional[str]:
    key = os.environ.get("API_FOOTBALL_KEY")
    if key:
        return key
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("API_FOOTBALL_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _write_elo(wc_elos: Dict[str, float]) -> None:
    """Fusiona el Elo de selecciones en elo_ratings.json bajo la clave 'World Cup'
    sin pisar las ligas de clubes ya calculadas."""
    all_elos: Dict[str, Any] = {}
    if ELO_OUTPUT.exists():
        try:
            all_elos = json.loads(ELO_OUTPUT.read_text())
        except Exception:
            all_elos = {}
    all_elos[ELO_KEY] = wc_elos
    ELO_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ELO_OUTPUT.write_text(json.dumps(all_elos, ensure_ascii=False, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(description="Scraper Mundial 2026 (selecciones)")
    ap.add_argument("--form-last", type=int, default=DEFAULT_FORM_LAST,
                    help="nº de partidos para la forma reciente (ataque/defensa)")
    ap.add_argument("--elo-last", type=int, default=DEFAULT_ELO_LAST,
                    help="nº de partidos por equipo para asentar el Elo")
    ap.add_argument("--dry-run", action="store_true", help="no escribe archivos")
    args = ap.parse_args()

    api_key = _load_api_key()
    if not api_key:
        logger.error("API_FOOTBALL_KEY no encontrada (ni en entorno ni en .env). "
                     "Agrega 'API_FOOTBALL_KEY=...' a %s/.env", ROOT)
        return 2

    client = APIFootballClient(api_key=api_key)
    # Workaround SSL local (igual que elo_ratings.py)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    client.session.verify = False

    try:
        stats, wc_elos = build(client, form_last=args.form_last, elo_last=args.elo_last)
    except APIFootballError as e:
        logger.error("Fallo construyendo datos del Mundial: %s", e)
        return 1

    logger.info("Stats de %d selecciones | Elo de %d selecciones", len(stats), len(wc_elos))
    if args.dry_run:
        top = sorted(wc_elos.items(), key=lambda kv: kv[1], reverse=True)[:10]
        logger.info("Top-10 Elo (preview): %s", top)
        return 0

    STATS_OUTPUT.write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    _write_elo(wc_elos)
    logger.info("Escrito: %s", STATS_OUTPUT)
    logger.info("Escrito: %s [%s]", ELO_OUTPUT, ELO_KEY)

    # Calendario completo del Mundial (para que el generador filtre el día sin red).
    try:
        schedule = fetch_wc_schedule(client)
        FIXTURES_OUTPUT.write_text(json.dumps(schedule, ensure_ascii=False, indent=2))
        logger.info("Escrito: %s (%d partidos)", FIXTURES_OUTPUT, len(schedule))
    except APIFootballError as e:
        logger.warning("No se pudo traer el calendario del Mundial: %s", e)

    # Amistosos de selecciones (preparación) — opcional, no crítico.
    try:
        today = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d")
        f_stats, f_sched = build_friendlies(client, today, form_last=args.form_last, wc_stats=stats)
        FRIENDLIES_STATS_OUTPUT.write_text(json.dumps(f_stats, ensure_ascii=False, indent=2))
        FRIENDLIES_FIXTURES_OUTPUT.write_text(json.dumps(f_sched, ensure_ascii=False, indent=2))
        logger.info("Escrito: %s (%d selecciones) | %s (%d amistosos)",
                    FRIENDLIES_STATS_OUTPUT, len(f_stats),
                    FRIENDLIES_FIXTURES_OUTPUT, len(f_sched))
    except APIFootballError as e:
        logger.warning("No se pudieron traer los amistosos: %s", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
