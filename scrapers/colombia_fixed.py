import requests
from bs4 import BeautifulSoup
import json
import os
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

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

def scrape_corners_footystats():
    """Extrae datos de corners de FootyStats para Colombia"""
    try:
        logger.info("⏳ Iniciando Selenium para FootyStats (Colombia)...")
        
        driver = webdriver.Chrome()
        url = "https://footystats.org/colombia/primera-a"
        
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "table"))
        )
        
        time.sleep(2)
        html = driver.page_source
        driver.quit()
        
        soup = BeautifulSoup(html, 'html.parser')
        corners_data = {}
        
        tables = soup.find_all('table')
        
        for tabla in tables:
            headers = tabla.find_all('th')
            header_text = [h.get_text(strip=True).lower() for h in headers]
            
            if 'team' not in header_text:
                continue
                
            rows = tabla.find_all('tr')[1:]
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 3:
                    continue
                
                team_name = cols[0].get_text(strip=True)
                
                if not team_name or "average" in team_name.lower():
                    continue
                
                try:
                    # Buscar columna de corners
                    corners_val = safe_convert(cols[1].get_text(strip=True), float, 0)
                    
                    corners_data[team_name] = {
                        "partidos": 0,
                        "promedio": corners_val if corners_val > 0 else 0
                    }
                except:
                    pass
        
        logger.info(f"✅ Corners extraídos: {len(corners_data)} equipos")
        return corners_data
    except Exception as e:
        logger.error(f"Error en scrape_corners_footystats: {e}")
        return {}

def scrape_goals_data(url):
    """Extrae datos de goles"""
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
            if not team or "average" in team.lower():
                continue
            
            goals_data[team] = {
                "over_1_5": columns[8].get_text(strip=True),
                "over_2_5": columns[9].get_text(strip=True),
                "bts": columns[10].get_text(strip=True) if len(columns) > 10 else "0%"
            }
        
        return goals_data
    except Exception as e:
        logger.error(f"Error en scrape_goals_data: {e}")
        return {}

def scrape_positions_data(url):
    """Extrae datos de posiciones/standings"""
    try:
        response = safe_request(url)
        positions_data = {}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'id': 'sstable'})
        
        if not table:
            logger.warning("Tabla de posiciones no encontrada")
            return positions_data

        rows = table.find_all('tr')[1:]
        for row in rows:
            columns = row.find_all('td')
            if len(columns) < 10:
                continue
            
            team = columns[1].get_text(strip=True)
            if not team:
                continue
            
            positions_data[team] = {
                "posicion": safe_convert(columns[0].get_text(strip=True), int),
                "partidos": safe_convert(columns[2].get_text(strip=True), int),
                "ganados": safe_convert(columns[3].get_text(strip=True), int),
                "empatados": safe_convert(columns[4].get_text(strip=True), int),
                "perdidos": safe_convert(columns[5].get_text(strip=True), int),
                "goles_favor": safe_convert(columns[6].get_text(strip=True), int),
                "goles_contra": safe_convert(columns[7].get_text(strip=True), int),
                "diferencia": safe_convert(columns[8].get_text(strip=True), int),
                "puntos": safe_convert(columns[9].get_text(strip=True), int)
            }
        
        return positions_data
    except Exception as e:
        logger.error(f"Error en scrape_positions_data: {e}")
        return {}

def main(league="colombia"):
    """Función principal mejorada"""
    try:
        positions_url = f"https://www.soccerstats.com/latest.asp?league={league}"
        goals_url = f"https://www.soccerstats.com/table.asp?league={league}&tid=c"
        
        logger.info(f"🔥 Iniciando extracción completa para liga: {league.upper()}")
        
        logger.info("📊 Extrayendo datos de posiciones...")
        positions_data = scrape_positions_data(positions_url)
        
        logger.info("🚩 Extrayendo datos de corners (FootyStats)...")
        corners_data = scrape_corners_footystats()
        
        logger.info("⚽ Extrayendo datos de goles...")
        goals_data = scrape_goals_data(goals_url)
        
        # Combinar datos
        combined_data = {}
        all_teams = set(list(corners_data.keys()) + list(goals_data.keys()) + list(positions_data.keys()))
        
        for team in all_teams:
            combined_data[team] = {
                "corners": corners_data.get(team, {}),
                "footystats": goals_data.get(team, {}),
                "position": positions_data.get(team, {})
            }
        
        combined_data['_metadata'] = {
            'fecha_actualizacion': datetime.now().isoformat(),
            'liga': league,
            'equipos_extraidos': {
                'corners': len(corners_data),
                'goals': len(goals_data), 
                'positions': len(positions_data)
            }
        }
        
        static_folder = 'static'
        os.makedirs(static_folder, exist_ok=True)
        
        file_path = os.path.join(static_folder, f'{league}_stats.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, ensure_ascii=False, indent=4)
        
        logger.info(f"🎉 Datos completos guardados en {file_path}")
        
        print(f"\n📋 RESUMEN FINAL:")
        print(f"   📊 Posiciones: {len(positions_data)} equipos")
        print(f"   🚩 Corners: {len(corners_data)} equipos")
        print(f"   ⚽ Goles: {len(goals_data)} equipos")
        print(f"   📁 Archivo: {file_path}")
        
    except Exception as e:
        logger.error(f"❌ Error crítico en main: {e}")
        raise

if __name__ == "__main__":
    main("colombia")
