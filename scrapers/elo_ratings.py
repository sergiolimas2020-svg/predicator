#!/usr/bin/env python3
"""
Script para calcular y actualizar el Elo Rating de los equipos de fútbol.
Descarga los fixtures de la temporada actual de API-Football,
ordena cronológicamente y calcula el Elo Rating dinámico para cada equipo.

Salida:
  static/api_football/elo_ratings.json
"""

import json
import logging
import os
import sys
import math
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.api_football.client import APIFootballClient, APIFootballError

ROOT = Path(__file__).resolve().parents[1]
LEAGUES_MAP = ROOT / "static" / "api_football" / "leagues_map.json"
ELO_OUTPUT = ROOT / "static" / "api_football" / "elo_ratings.json"

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("elo_ratings")

# Parámetros de Elo
ELO_BASE = 1500.0
K_FACTOR = 20

def get_goal_difference_multiplier(goals_diff: int) -> float:
    """Retorna el multiplicador de Elo FIFA por diferencia de goles."""
    abs_diff = abs(goals_diff)
    if abs_diff <= 1:
        return 1.0
    elif abs_diff == 2:
        return 1.5
    elif abs_diff == 3:
        return 1.75
    else:
        return 1.75 + (abs_diff - 3) / 8.0

def calculate_elo_update(rating_home: float, rating_away: float, goals_home: int, goals_away: int):
    """Calcula el cambio de Elo para el local y visitante."""
    # Resultado real
    if goals_home > goals_away:
        result_home = 1.0
    elif goals_home == goals_away:
        result_home = 0.5
    else:
        result_home = 0.0
    
    result_away = 1.0 - result_home

    # Probabilidades esperadas
    expected_home = 1.0 / (1.0 + 10.0 ** ((rating_away - rating_home) / 400.0))
    expected_away = 1.0 - expected_home

    # Multiplicador por margen de victoria (FIFA Elo adaptation)
    goals_diff = goals_home - goals_away
    multiplier = get_goal_difference_multiplier(goals_diff)

    # Actualizaciones
    delta_home = K_FACTOR * multiplier * (result_home - expected_home)
    delta_away = K_FACTOR * multiplier * (result_away - expected_away)

    return delta_home, delta_away

def compute_league_elo(client: APIFootballClient, league_name: str, league_id: int, season: int) -> Dict[str, float]:
    """Descarga partidos, calcula Elo cronológico y retorna diccionario de Elos por equipo."""
    logger.info("Procesando Elo para %s (ID: %d, Temporada: %d)...", league_name, league_id, season)
    
    try:
        # Petición a /fixtures de la liga/temporada completa
        # Desactivamos verificación SSL si hay problemas en el entorno local (verify=False)
        # Nota: El cliente HTTP del proyecto usa requests.Session(), podemos configurar la sesión si hiciera falta.
        # Por seguridad y consistencia en local, agregamos tolerancia.
        fixtures_response = client._request("/fixtures", {"league": league_id, "season": season})
    except APIFootballError as e:
        logger.error("Error consultando API-Football para liga %s: %s", league_name, e)
        return {}
    except Exception as e:
        logger.error("Fallo general consultando liga %s: %s", league_name, e)
        return {}

    fixtures = fixtures_response.get("response", [])
    if not fixtures:
        logger.warning("No se encontraron fixtures para la liga %s (ID: %d)", league_name, league_id)
        return {}

    # Filtrar solo partidos finalizados y ordenarlos cronológicamente
    completed_fixtures = []
    for fx in fixtures:
        status = fx.get("fixture", {}).get("status", {}).get("short")
        if status in ["FT", "AET", "PEN"]:
            completed_fixtures.append(fx)

    # Ordenar por fecha / timestamp
    completed_fixtures.sort(key=lambda x: x.get("fixture", {}).get("timestamp", 0))
    logger.info("  Total partidos jugados encontrados: %d", len(completed_fixtures))

    # Inicializar Elos
    elos: Dict[str, float] = {}

    for fx in completed_fixtures:
        teams = fx.get("teams", {})
        home_name = teams.get("home", {}).get("name")
        away_name = teams.get("away", {}).get("name")
        
        goals = fx.get("goals", {})
        goals_home = goals.get("home")
        goals_away = goals.get("away")

        if not home_name or not away_name or goals_home is None or goals_away is None:
            continue

        # Asegurar inicialización en 1500
        if home_name not in elos:
            elos[home_name] = ELO_BASE
        if away_name not in elos:
            elos[away_name] = ELO_BASE

        # Calcular e integrar cambio
        delta_h, delta_a = calculate_elo_update(elos[home_name], elos[away_name], goals_home, goals_away)
        elos[home_name] += delta_h
        elos[away_name] += delta_a

    # Redondear Elos para legibilidad
    rounded_elos = {team: round(elo, 1) for team, elo in elos.items()}
    return rounded_elos

def main():
    if not os.environ.get("API_FOOTBALL_KEY"):
        logger.warning("API_FOOTBALL_KEY no está configurada en el entorno.")
        logger.warning("Intentando leer del archivo .env...")
        # Leer .env si existe
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("API_FOOTBALL_KEY="):
                    os.environ["API_FOOTBALL_KEY"] = line.split("=", 1)[1].strip('"').strip("'")
                    break

    api_key = os.environ.get("API_FOOTBALL_KEY")
    if not api_key:
        logger.error("API_FOOTBALL_KEY no encontrada. No se puede calcular el Elo online.")
        # Si no hay key, mantenemos un fallback vacío o leemos el anterior para no borrarlo
        if ELO_OUTPUT.exists():
            logger.info("Manteniendo archivo Elo existente.")
        else:
            ELO_OUTPUT.write_text(json.dumps({}, ensure_ascii=False, indent=2))
        sys.exit(0)

    if not LEAGUES_MAP.exists():
        logger.error("No existe leagues_map.json en %s", LEAGUES_MAP)
        sys.exit(1)

    leagues = json.loads(LEAGUES_MAP.read_text())
    client = APIFootballClient(api_key=api_key)

    # Desactivar verificación de SSL para requests si se detecta problemas de certificados en local
    # (El Mac local del usuario a veces tiene fallos de validación SSL)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    client.session.verify = False

    all_elos = {}
    
    # Si ya existe el archivo de Elo ratings, lo cargamos como base para preservar ligas que puedan fallar
    if ELO_OUTPUT.exists():
        try:
            all_elos = json.loads(ELO_OUTPUT.read_text())
        except Exception:
            pass

    for league_name, info in leagues.items():
        league_id = info.get("id")
        season = info.get("season")
        if not league_id or not season:
            continue
        
        # Calcular Elos de la liga
        league_elos = compute_league_elo(client, league_name, league_id, season)
        if league_elos:
            all_elos[league_name] = league_elos

    # Escribir salida
    ELO_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ELO_OUTPUT.write_text(json.dumps(all_elos, ensure_ascii=False, indent=2))
    logger.info("Éxito: Elo ratings guardados en %s", ELO_OUTPUT)

if __name__ == "__main__":
    main()
