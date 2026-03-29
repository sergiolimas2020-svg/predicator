import requests
from bs4 import BeautifulSoup
import json
import os
import logging
from datetime import datetime

# NUEVO (AdamChoi)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

# Configurar logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def safe_request(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.warning(f"Error en la solicitud (intento {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise

def safe_convert(value, type_func, default=0):
    try:
        return type_func(str(value).replace(',', '.')) if value else default
    except ValueError:
        return default

# ------------------ SOCCERSTATS ------------------

def scrape_corners_data(url):
    try:
        response = safe_request(url)
        corner_data = {}
        
        soup = BeautifulSoup(response.content, 'html.parser')
        tables = soup.find_all('table')

        for t in tables:
            home_header = t.find('th', string=lambda text: text and ("home" in text.lower() or "hogar" in text.lower()))
            away_header = t.find('th', string=lambda text: text and ("away" in text.lower() or "lejos" in text.lower()))
            
            if home_header:
                tipo = "local"
            elif away_header:
                tipo = "visitante"
            else:
                continue

            rows = t.find_all('tr')[2:]
            for row in rows:
                columns = row.find_all('td')
                if len(columns) < 7:
                    continue
                
                equipo = columns[0].text.strip()
                if "average" in equipo.lower():
                    continue

                if equipo not in corner_data:
                    corner_data[equipo] = {
                        "local": {"partidos": 0, "corners_favor": 0.0, "corners_contra": 0.0},
                        "visitante": {"partidos": 0, "corners_favor": 0.0, "corners_contra": 0.0}
                    }

                corner_data[equipo][tipo]["partidos"] = safe_convert(columns[1].text.strip(), int)
                corner_data[equipo][tipo]["corners_favor"] = safe_convert(columns[2].text.strip(), float)
                corner_data[equipo][tipo]["corners_contra"] = safe_convert(columns[3].text.strip(), float)

        logger.info(f"✅ Corners extraídos: {len(corner_data)} equipos")
        return corner_data
    except Exception as e:
        logger.error(f"Error en scrape_corners_data: {e}")
        return {}

def scrape_goals_data(url):
    try:
        response = safe_request(url)
        goals_data = {}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'id': 'btable'})
        
        if not table:
            logger.warning("Tabla de goles no encontrada")
            return goals_data

        rows = table.find_all('tr')[1:]
        for row in rows:
            columns = row.find_all('td')
            if len(columns) < 10:
                continue
            
            team = columns[0].get_text(strip=True)
            goals_data[team] = {
                'over_1_5': columns[4].get_text(strip=True),
                'over_2_5': columns[5].get_text(strip=True),
                'over_3_5': columns[6].get_text(strip=True),
                'bts': columns[9].get_text(strip=True)
            }

        logger.info(f"✅ Goals extraídos: {len(goals_data)} equipos")
        return goals_data
    except Exception as e:
        logger.error(f"Error en scrape_goals_data: {e}")
        return {}

def scrape_positions_data(url):
    try:
        response = safe_request(url)
        positions_data = {}
        
        soup = BeautifulSoup(response.content, 'html.parser')
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 15:
                continue
                
            position = 1
            teams_found = 0
            
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 8:
                    continue
                    
                cell_texts = [cell.get_text().strip() for cell in cells]
                
                for i, text in enumerate(cell_texts):
                    if (text and len(text) > 2 and 
                        not text.isdigit() and 
                        any(c.isalpha() for c in text)):

                        remaining = cell_texts[i+1:]
                        numbers = [x for x in remaining if x.isdigit()]
                        
                        if len(numbers) >= 6:
                            try:
                                mp, w, d, l, gf, ga = [int(x) for x in numbers[:6]]
                                
                                if mp > 0 and w + d + l == mp:
                                    positions_data[text] = {
                                        "posicion": position,
                                        "puntos": w * 3 + d,
                            "partidos": mp,
                            "ganados": w,
                            "empatados": d,
                            "perdidos": l,
                            "goles_favor": gf,
                            "goles_contra": ga,
                            "diferencia": gf - ga
                                    }
                                    
                                    position += 1
                                    teams_found += 1
                                    break
                            except:
                                continue
                
                if teams_found >= 20:
                    break
            
            if teams_found >= 15:
                return positions_data
        
        return {}
        
    except Exception as e:
        logger.error(f"Error en posiciones: {e}")
        return {}

# ------------------ ADAM CHOI ------------------

def scrape_adamchoi_data(url):
    try:
        options = Options()
        options.add_argument("--headless")
        
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        
        time.sleep(5)
        
        matches = []
        elements = driver.find_elements(By.CSS_SELECTOR, "div")
        
        for el in elements:
            text = el.text.strip()
            if "vs" in text.lower():
                matches.append(text)
        
        driver.quit()
        
        logger.info(f"✅ AdamChoi: {len(matches)} partidos")
        return matches
    
    except Exception as e:
        logger.error(f"Error AdamChoi: {e}")
        return []

# ------------------ MAIN ------------------

def main(league="germany"):
    try:
        corners_url = f"https://www.soccerstats.com/table.asp?league={league}&tid=cr"
        goals_url = f"https://www.soccerstats.com/table.asp?league={league}&tid=c"
        positions_url = f"https://www.soccerstats.com/latest.asp?league={league}"
        adamchoi_url = f"https://www.adamchoi.co.uk/fixtures/{league}"

        logger.info(f"🔥 Liga: {league}")

        positions_data = scrape_positions_data(positions_url)
        corners_data = scrape_corners_data(corners_url)
        goals_data = scrape_goals_data(goals_url)
        adamchoi_data = scrape_adamchoi_data(adamchoi_url)

        combined_data = {}
        all_teams = set(list(corners_data.keys()) + list(goals_data.keys()) + list(positions_data.keys()))
        
        for team in all_teams:
            combined_data[team] = {
                "corners": corners_data.get(team, {}),
                "goals": goals_data.get(team, {}),
                "position": positions_data.get(team, {})
            }

        combined_data['_external'] = {
            "adamchoi_matches": adamchoi_data
        }

        os.makedirs('static', exist_ok=True)
        file_path = f'static/{league}_stats.json'

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, indent=4, ensure_ascii=False)

        print(f"\n✅ Archivo generado: {file_path}")
        return combined_data

    except Exception as e:
        logger.error(f"Error general: {e}")

if __name__ == "__main__":
    main("brazil" \
    "")