import requests
import json, os, logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Aliases vistos en torneos CONMEBOL (key = nombre que viene de odds API,
# value = nombre canónico en ESPN). El scraper duplica entries en el JSON
# para que ambos nombres apunten al mismo dict de stats.
TEAM_ALIASES = {
    "LDU Quito": "Liga de Quito",
    "L.D.U. Quito": "Liga de Quito",
    "Liga Deportiva Universitaria": "Liga de Quito",
    "U. Católica (Quito)": "Universidad Católica (Quito)",
    "Universidad Catolica Quito": "Universidad Católica (Quito)",
}


def fetch_standings():
    """Standings de la Serie A de Ecuador desde ESPN."""
    try:
        r = requests.get(
            'https://site.api.espn.com/apis/v2/sports/soccer/ecu.1/standings',
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        data = r.json()

        all_entries = []
        for child in data.get('children', []):
            entries = child.get('standings', {}).get('entries', [])
            all_entries.extend(entries)

        positions_data = {}
        for pos, entry in enumerate(all_entries, 1):
            team_name = entry['team']['displayName']
            stats = {s['name']: s['value'] for s in entry.get('stats', []) if 'value' in s}
            gp  = int(stats.get('gamesPlayed', 0))
            w   = int(stats.get('wins', 0))
            d   = int(stats.get('ties', 0))
            l   = int(stats.get('losses', 0))
            gf  = int(stats.get('pointsFor', 0))
            ga  = int(stats.get('pointsAgainst', 0))
            pts = int(stats.get('points', w * 3 + d))
            positions_data[team_name] = {
                "posicion": pos, "partidos": gp,
                "ganados": w, "empatados": d, "perdidos": l,
                "goles_favor": gf, "goles_contra": ga,
                "diferencia": gf - ga, "puntos": pts
            }
            logger.info(f"✅ {pos}. {team_name} - {pts} pts")

        logger.info(f"✅ Posiciones: {len(positions_data)} equipos")
        return positions_data
    except Exception as e:
        logger.error(f"Error standings: {e}")
        return {}


def fetch_goals():
    """Intenta obtener Over stats desde soccerstats. Si no hay, devuelve {}."""
    for league_name in ['ecuador', 'ecuserieA', 'ecudivA']:
        try:
            url = f"https://www.soccerstats.com/table.asp?league={league_name}&tid=c"
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            from bs4 import BeautifulSoup
            table = BeautifulSoup(r.text, 'html.parser').find('table', {'id': 'btable'})
            if not table:
                continue
            goals_data = {}
            for row in table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) < 10:
                    continue
                team = cols[0].get_text(strip=True)
                goals_data[team] = {
                    'over_1_5': cols[4].get_text(strip=True),
                    'over_2_5': cols[5].get_text(strip=True),
                    'over_3_5': cols[6].get_text(strip=True),
                    'bts':      cols[9].get_text(strip=True),
                }
            if goals_data:
                logger.info(f"✅ Goals: {len(goals_data)} equipos (soccerstats/{league_name})")
                return goals_data
        except Exception:
            continue
    logger.warning("Goals no disponibles en soccerstats para Ecuador — usando defaults")
    return {}


def main():
    logger.info("🔥 Liga: Serie A Ecuador (via ESPN)")
    positions_data = fetch_standings()
    goals_data     = fetch_goals()

    combined_data = {}
    for team in set(list(positions_data.keys()) + list(goals_data.keys())):
        combined_data[team] = {
            "corners":  {},
            "goals":    goals_data.get(team, {}),
            "position": positions_data.get(team, {}),
        }

    # Aliases CONMEBOL: nombres alternativos vistos en odds API apuntan al
    # mismo dict de stats que el nombre canónico. Si el alias YA existe en
    # combined_data (porque soccerstats lo devolvió con goals pero sin
    # position), mergeamos sus campos no-vacíos al canónico antes de
    # sobrescribirlo, así no perdemos info.
    for alias, canonical in TEAM_ALIASES.items():
        if canonical not in combined_data:
            continue
        canonical_dict = combined_data[canonical]
        if alias in combined_data:
            alias_dict = combined_data[alias]
            if not canonical_dict.get("goals") and alias_dict.get("goals"):
                canonical_dict["goals"] = alias_dict["goals"]
            if not canonical_dict.get("position") and alias_dict.get("position"):
                canonical_dict["position"] = alias_dict["position"]
        combined_data[alias] = canonical_dict
        logger.info(f"  alias: {alias} → {canonical}")

    combined_data['_metadata'] = {
        'fecha_actualizacion': datetime.now().isoformat(),
        'liga': 'ecuador',
        'fuente': 'ESPN API'
    }

    os.makedirs('static', exist_ok=True)
    with open('static/ecuador_stats.json', 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Archivo generado: static/ecuador_stats.json")
    print(f"   📊 Posiciones: {len(positions_data)} | ⚽ Goals: {len(goals_data)}")


if __name__ == "__main__":
    main()
