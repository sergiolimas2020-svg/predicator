import requests
from bs4 import BeautifulSoup
import json, os, logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def safe_request(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            r = requests.get(url, timeout=10, headers=HEADERS)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            logger.warning(f"Error (intento {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise

def scrape_goals_data(url):
    try:
        soup = BeautifulSoup(safe_request(url).text, 'html.parser')
        table = soup.find('table', {'id': 'btable'})
        if not table:
            logger.warning("Tabla de goles no encontrada")
            return {}
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
        logger.info(f"✅ Goals extraídos: {len(goals_data)} equipos")
        return goals_data
    except Exception as e:
        logger.error(f"Error goals: {e}")
        return {}

def scrape_positions_data(url):
    try:
        soup = BeautifulSoup(safe_request(url).content, 'html.parser')
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            if len(rows) < 15:
                continue
            position, teams_found, positions_data = 1, 0, {}
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 8:
                    continue
                cell_texts = [c.get_text().strip() for c in cells]
                for i, text in enumerate(cell_texts):
                    if text and len(text) > 2 and not text.isdigit() and any(c.isalpha() for c in text):
                        numbers = [x for x in cell_texts[i+1:] if x.isdigit()]
                        if len(numbers) >= 6:
                            try:
                                mp, w, d, l, gf, ga = [int(x) for x in numbers[:6]]
                                if mp > 0 and w + d + l == mp:
                                    positions_data[text] = {
                                        "posicion": position, "partidos": mp,
                                        "ganados": w, "empatados": d, "perdidos": l,
                                        "goles_favor": gf, "goles_contra": ga,
                                        "diferencia": gf - ga, "puntos": w * 3 + d
                                    }
                                    logger.info(f"✅ {position}. {text} - {w*3+d} pts")
                                    position += 1
                                    teams_found += 1
                                    break
                            except:
                                continue
                if teams_found >= 20:
                    break
            if teams_found >= 15:
                logger.info(f"✅ Posiciones: {teams_found} equipos")
                return positions_data
        return {}
    except Exception as e:
        logger.error(f"Error posiciones: {e}")
        return {}

def main():
    league = "brazil"
    logger.info(f"🔥 Liga: Brasileirao")
    positions_data = scrape_positions_data(f"https://www.soccerstats.com/latest.asp?league={league}")
    goals_data     = scrape_goals_data(f"https://www.soccerstats.com/table.asp?league={league}&tid=c")

    combined_data = {}
    for team in set(list(goals_data.keys()) + list(positions_data.keys())):
        combined_data[team] = {
            "corners":  {},
            "goals":    goals_data.get(team, {}),
            "position": positions_data.get(team, {}),
        }
    combined_data['_metadata'] = {'fecha_actualizacion': datetime.now().isoformat(), 'liga': league}

    os.makedirs('static', exist_ok=True)
    with open('static/brazil_stats.json', 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Archivo generado: static/brazil_stats.json")
    print(f"   📊 Posiciones: {len(positions_data)} | ⚽ Goals: {len(goals_data)}")

if __name__ == "__main__":
    main()
