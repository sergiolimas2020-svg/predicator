#!/usr/bin/env python3
"""
Web scraping REAL de Liga Colombiana 2026 desde fuentes actuales
"""

import json
import requests
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def scrape_futbolred():
    """Obtiene datos de FutbolRed.com"""
    
    print("📡 Intentando FutbolRed.com...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        # FutbolRed página de posiciones Colombia
        url = "https://www.futbolred.com/liga-betplay/posiciones-tabla-posiciones"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar tabla
            tables = soup.find_all('table')
            
            if tables:
                standings = []
                
                for table in tables:
                    rows = table.find_all('tr')[1:]  # Saltar header
                    
                    for row in rows:
                        cols = row.find_all('td')
                        
                        if len(cols) >= 9:
                            try:
                                pos = int(cols[0].get_text(strip=True))
                                team_name = cols[1].get_text(strip=True)
                                partidos = int(cols[2].get_text(strip=True))
                                ganados = int(cols[3].get_text(strip=True))
                                empates = int(cols[4].get_text(strip=True))
                                perdidos = int(cols[5].get_text(strip=True))
                                goles_favor = int(cols[6].get_text(strip=True))
                                goles_contra = int(cols[7].get_text(strip=True))
                                puntos = int(cols[8].get_text(strip=True))
                                
                                standings.append({
                                    'posicion': pos,
                                    'equipo': team_name,
                                    'partidos': partidos,
                                    'ganados': ganados,
                                    'empates': empates,
                                    'perdidos': perdidos,
                                    'goles_favor': goles_favor,
                                    'goles_contra': goles_contra,
                                    'puntos': puntos
                                })
                                
                                print(f"  ✓ {pos:2}. {team_name:30} J:{partidos:2} Pts:{puntos:2}")
                            except (ValueError, IndexError) as e:
                                continue
                
                if standings:
                    print(f"✅ FutbolRed: {len(standings)} equipos encontrados")
                    return standings
    
    except Exception as e:
        print(f"❌ FutbolRed: {str(e)[:80]}")
    
    return None

def scrape_dimayor():
    """Obtiene datos desde sitio oficial Dimayor con Selenium"""
    
    print("📡 Intentando Dimayor.com (sitio oficial)...")
    
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get("https://www.dimayor.com.co/estadisticas/")
        
        # Esperar tabla
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "table"))
        )
        
        time.sleep(2)
        
        html = driver.page_source
        driver.quit()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        standings = []
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')[1:]  # Saltar header
            
            for row in rows:
                cols = row.find_all(['td', 'th'])
                
                if len(cols) >= 9:
                    try:
                        text_values = [col.get_text(strip=True) for col in cols]
                        
                        pos = int(text_values[0])
                        team_name = text_values[1]
                        partidos = int(text_values[2])
                        ganados = int(text_values[3])
                        empates = int(text_values[4])
                        perdidos = int(text_values[5])
                        goles_favor = int(text_values[6])
                        goles_contra = int(text_values[7])
                        puntos = int(text_values[8])
                        
                        standings.append({
                            'posicion': pos,
                            'equipo': team_name,
                            'partidos': partidos,
                            'ganados': ganados,
                            'empates': empates,
                            'perdidos': perdidos,
                            'goles_favor': goles_favor,
                            'goles_contra': goles_contra,
                            'puntos': puntos
                        })
                        
                        print(f"  ✓ {pos:2}. {team_name:30} J:{partidos:2} Pts:{puntos:2}")
                    except (ValueError, IndexError):
                        continue
        
        if standings:
            print(f"✅ Dimayor: {len(standings)} equipos encontrados")
            return standings
    
    except Exception as e:
        print(f"❌ Dimayor: {str(e)[:80]}")
    
    return None

def scrape_espn():
    """Obtiene datos de ESPN.com.co"""
    
    print("📡 Intentando ESPN.com.co...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        url = "https://www.espn.co/futbol/estadisticas?league=COL.1"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            tables = soup.find_all('table')
            
            if tables:
                standings = []
                
                for table in tables:
                    rows = table.find_all('tr')[1:]
                    
                    for row in rows:
                        cols = row.find_all('td')
                        
                        if len(cols) >= 9:
                            try:
                                pos = int(cols[0].get_text(strip=True))
                                team_name = cols[1].get_text(strip=True).strip()
                                partidos = int(cols[2].get_text(strip=True))
                                ganados = int(cols[3].get_text(strip=True))
                                empates = int(cols[4].get_text(strip=True))
                                perdidos = int(cols[5].get_text(strip=True))
                                goles_favor = int(cols[6].get_text(strip=True))
                                goles_contra = int(cols[7].get_text(strip=True))
                                puntos = int(cols[8].get_text(strip=True))
                                
                                standings.append({
                                    'posicion': pos,
                                    'equipo': team_name,
                                    'partidos': partidos,
                                    'ganados': ganados,
                                    'empates': empates,
                                    'perdidos': perdidos,
                                    'goles_favor': goles_favor,
                                    'goles_contra': goles_contra,
                                    'puntos': puntos
                                })
                                
                                print(f"  ✓ {pos:2}. {team_name:30} J:{partidos:2} Pts:{puntos:2}")
                            except (ValueError, IndexError):
                                continue
                
                if standings:
                    print(f"✅ ESPN: {len(standings)} equipos encontrados")
                    return standings
    
    except Exception as e:
        print(f"❌ ESPN: {str(e)[:80]}")
    
    return None

def update_colombia_json(standings):
    """Actualiza el JSON con datos de standings"""
    
    print(f"\n📝 Actualizando Colombia con {len(standings)} equipos reales...\n")
    
    # Cargar JSON actual
    with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json') as f:
        current_data = json.load(f)
    
    # Mapeo flexible de nombres
    mapping = {}
    
    for team in current_data.keys():
        team_lower = team.lower().replace(' ', '').replace('.', '')
        
        for standing in standings:
            standing_name = standing['equipo'].lower().replace(' ', '').replace('.', '')
            
            # Búsqueda flexible
            if (team_lower in standing_name or standing_name in team_lower or
                len(team_lower) > 3 and team_lower in standing_name[:25]):
                mapping[team] = standing
                break
    
    # Actualizar
    updated = 0
    for team, stats in current_data.items():
        if team in mapping:
            standing = mapping[team]
            current_data[team]['position'] = {
                'posicion': standing['posicion'],
                'partidos': standing['partidos'],
                'ganados': standing['ganados'],
                'empates': standing['empates'],
                'perdidos': standing['perdidos'],
                'goles_favor': standing['goles_favor'],
                'goles_contra': standing['goles_contra'],
                'diferencia': standing['goles_favor'] - standing['goles_contra'],
                'puntos': standing['puntos']
            }
            updated += 1
            
            print(f"  ✓ {team:25} → Pos {standing['posicion']:2} | {standing['partidos']} PJ | {standing['puntos']} Pts")
    
    # Guardar
    with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json', 'w') as f:
        json.dump(current_data, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ {updated} equipos actualizados")
    print("💾 Archivo guardado: static/colombia_stats.json")
    
    return updated > 0

if __name__ == '__main__':
    print("="*80)
    print("🇨🇴 WEB SCRAPING REAL - LIGA COLOMBIANA 2026")
    print("="*80 + "\n")
    
    standings = None
    
    # Intentar múltiples fuentes
    sources = [
        scrape_futbolred,
        scrape_espn,
        scrape_dimayor,
    ]
    
    for scraper in sources:
        standings = scraper()
        if standings:
            break
        print()
    
    if standings:
        update_colombia_json(standings)
        print("\n🎉 ¡ACTUALIZACIÓN COMPLETADA CON DATOS REALES!")
    else:
        print("\n❌ No se pudieron obtener datos de fuentes web")
    
    print("="*80 + "\n")
