#!/usr/bin/env python3
"""
Scraper Universal - Extrae Corners, Over/Under, BTTS
Usa FootyStats API con Selenium para las ligas europeas
"""

import json
import time
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"

# URLs de FootyStats para cada liga
LIGAS = {
    'england': 'https://footystats.org/england/premier-league',
    'spain': 'https://footystats.org/spain/laliga',
    'germany': 'https://footystats.org/germany/bundesliga',
    'italy': 'https://footystats.org/italy/serie-a',
    'france': 'https://footystats.org/france/ligue-1',
    'argentina': 'https://footystats.org/argentina/liga_profesional',
    'brazil': 'https://footystats.org/brazil/campeonato-brasileiro',
    'colombia': 'https://footystats.org/colombia/liga-dimayor',
    'turkey': 'https://footystats.org/turkey/super-lig',
}

def setup_selenium():
    """Configura Selenium con Chrome"""
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    return webdriver.Chrome(service=service, options=options)

def scrape_footystats(liga_url, liga_name):
    """Extrae datos de FootyStats usando Selenium"""
    logger.info(f"🌐 Scrapeando FootyStats: {liga_url}")
    
    driver = setup_selenium()
    teams_data = {}
    
    try:
        driver.get(liga_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "table"))
        )
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all('tr')
        
        logger.info(f"📊 Encontradas {len(rows)} filas en {liga_name}")
        
        for row in rows[1:]:  # Saltar header
            cells = row.find_all('td')
            if len(cells) < 5:
                continue
            
            try:
                # Nombre del equipo
                team_name = cells[0].get_text(strip=True)
                if not team_name or team_name.startswith('Team'):
                    continue
                
                # Corners
                corners_text = cells[1].get_text(strip=True)
                corners = int(corners_text) if corners_text.isdigit() else 0
                
                # Over 2.5
                over_text = cells[2].get_text(strip=True)
                over = int(over_text.replace('%', '')) if '%' in over_text else 50
                
                # BTTS
                btts_text = cells[3].get_text(strip=True)
                btts = int(btts_text.replace('%', '')) if '%' in btts_text else 50
                
                if team_name and corners > 0:
                    teams_data[team_name] = {
                        'corners': {'partidos': corners, 'promedio': round(corners/10, 1)},
                        'footystats': {'over_2_5': over, 'btts': btts}
                    }
                    logger.info(f"  ✅ {team_name}: {corners} corners | O2.5: {over}% | BTTS: {btts}%")
            
            except (IndexError, ValueError) as e:
                logger.debug(f"  ⚠️ Error parseando fila: {e}")
                continue
        
    except Exception as e:
        logger.error(f"❌ Error con FootyStats en {liga_name}: {e}")
    
    finally:
        driver.quit()
    
    return teams_data

def scrape_liga(liga_name, liga_url):
    """Scrape completo de una liga"""
    logger.info(f"\n{'='*65}")
    logger.info(f"🏆 LIGA: {liga_name.upper()}")
    logger.info(f"{'='*65}")
    
    teams_data = scrape_footystats(liga_url, liga_name)
    
    # Guardar JSON
    output_file = STATIC_DIR / f"{liga_name}_stats.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(teams_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"💾 Guardado: {output_file}")
    logger.info(f"📈 Total equipos: {len(teams_data)}")
    
    return teams_data

def main():
    """Ejecuta scraping universal"""
    logger.info("\n" + "="*65)
    logger.info("🚀 SCRAPER UNIVERSAL - EXTRAYENDO CORNERS REALES")
    logger.info("="*65 + "\n")
    
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    
    resultados = {}
    
    for liga_name, liga_url in LIGAS.items():
        try:
            datos = scrape_liga(liga_name, liga_url)
            resultados[liga_name] = len(datos)
            time.sleep(2)  # Esperar entre ligas para no sobrecargar
        except Exception as e:
            logger.error(f"❌ Error crítico en {liga_name}: {e}")
            resultados[liga_name] = 0
    
    # Resumen final
    logger.info(f"\n{'='*65}")
    logger.info("📊 RESUMEN FINAL:")
    logger.info(f"{'='*65}")
    
    for liga, equipos in sorted(resultados.items()):
        status = "✅" if equipos > 0 else "⚠️ "
        logger.info(f"{status} {liga.upper():20s} | {equipos:3d} equipos")
    
    total = sum(resultados.values())
    logger.info(f"\n{'='*65}")
    logger.info(f"✅ TOTAL: {total} equipos con datos de corners reales")
    logger.info(f"{'='*65}\n")

if __name__ == "__main__":
    main()
