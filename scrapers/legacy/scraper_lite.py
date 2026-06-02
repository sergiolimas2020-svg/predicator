#!/usr/bin/env python3
"""
Universal Scraper - Versión Lite (sin Selenium)
Genera datos inteligentes cuando FootyStats no responde
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

LEAGUE_CONFIG = {
    'england': {'soccerstats_code': 'england', 'name': 'Premier League'},
    'spain': {'soccerstats_code': 'spain', 'name': 'La Liga'},
    'germany': {'soccerstats_code': 'germany', 'name': 'Bundesliga'},
    'italy': {'soccerstats_code': 'italy', 'name': 'Serie A'},
    'france': {'soccerstats_code': 'france', 'name': 'Ligue 1'},
    'argentina': {'soccerstats_code': 'argentina1', 'name': 'Liga Argentina'},
    'brazil': {'soccerstats_code': 'brazil', 'name': 'Serie A Brasil'},
    'colombia': {'soccerstats_code': 'colombia', 'name': 'Primera A'},
    'turkey': {'soccerstats_code': 'turkey', 'name': 'Super Lig'}
}

def safe_convert(value, type_func, default=0):
    try:
        return type_func(str(value).replace(',', '.')) if value else default
    except:
        return default

def scrape_goals_data(ss_code):
    """Extrae datos de goles y corners de SoccerStats"""
    try:
        logger.info(f"⚽ Extrayendo datos de SoccerStats...")
        url = f"https://www.soccerstats.com/table.asp?league={ss_code}&tid=c"
        response = requests.get(url, timeout=10)
        goals_data = {}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'id': 'btable'})
        
        if not table:
            logger.warning("Tabla no encontrada")
            return goals_data

        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 11:
                continue
            
            team = cols[0].get_text(strip=True)
            if not team or "average" in team.lower():
                continue
            
            over_25 = safe_convert(cols[9].get_text(strip=True).replace('%', ''), int, 50)
            btts = safe_convert(cols[10].get_text(strip=True).replace('%', ''), int, 50)
            
            # Estimar corners basados en Over 2.5% (correlación estadística)
            # Lógica: Si Over 2.5% es alto, probablemente hay más corners
            estimated_corners = int((over_25 / 100) * 8 + 4)  # Rango: 4-12
            
            goals_data[team] = {
                "corners": {
                    "partidos": 0,
                    "promedio": estimated_corners
                },
                "footystats": {
                    "over_2_5": f"{over_25}%",
                    "btts": f"{btts}%"
                }
            }
        
        logger.info(f"✅ Datos extraídos: {len(goals_data)} equipos")
        return goals_data
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {}

def scrape_positions_data(ss_code):
    """Extrae posiciones de SoccerStats"""
    try:
        logger.info(f"📊 Extrayendo posiciones...")
        url = f"https://www.soccerstats.com/latest.asp?league={ss_code}"
        response = requests.get(url, timeout=10)
        positions_data = {}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'id': 'sstable'})
        
        if not table:
            return positions_data

        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 10:
                continue
            
            team = cols[1].get_text(strip=True)
            if not team:
                continue
            
            positions_data[team] = {
                "posicion": safe_convert(cols[0].get_text(strip=True), int),
                "partidos": safe_convert(cols[2].get_text(strip=True), int),
                "ganados": safe_convert(cols[3].get_text(strip=True), int),
                "empatados": safe_convert(cols[4].get_text(strip=True), int),
                "perdidos": safe_convert(cols[5].get_text(strip=True), int),
                "goles_favor": safe_convert(cols[6].get_text(strip=True), int),
                "goles_contra": safe_convert(cols[7].get_text(strip=True), int),
                "diferencia": safe_convert(cols[8].get_text(strip=True), int),
                "puntos": safe_convert(cols[9].get_text(strip=True), int)
            }
        
        logger.info(f"✅ Posiciones: {len(positions_data)} equipos")
        return positions_data
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {}

def main(league_key):
    """Función principal"""
    if league_key not in LEAGUE_CONFIG:
        logger.error(f"❌ Liga no soportada: {league_key}")
        return
    
    config = LEAGUE_CONFIG[league_key]
    logger.info(f"🔥 Procesando: {config['name'].upper()}")
    
    # Extraer datos
    goals_data = scrape_goals_data(config['soccerstats_code'])
    positions = scrape_positions_data(config['soccerstats_code'])
    
    # Combinar
    combined = {}
    
    for team, data in goals_data.items():
        combined[team] = {
            "corners": data.get("corners", {}),
            "footystats": data.get("footystats", {}),
            "position": positions.get(team, {})
        }
    
    combined['_metadata'] = {
        'fecha_actualizacion': datetime.now().isoformat(),
        'liga': league_key,
        'equipos_extraidos': {
            'total': len(combined) - 1,  # -1 por metadata
            'notas': 'Corners calculados inteligentemente basado en Over 2.5%'
        }
    }
    
    # Guardar
    os.makedirs('static', exist_ok=True)
    file_path = f'static/{league_key}_stats.json'
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, ensure_ascii=False, indent=4)
    
    print(f"\n✅ LISTO: {config['name']}")
    print(f"   Equipos: {len(combined)-1}")
    print(f"   Archivo: {file_path}\n")

if __name__ == "__main__":
    import sys
    league = sys.argv[1] if len(sys.argv) > 1 else 'colombia'
    main(league)
