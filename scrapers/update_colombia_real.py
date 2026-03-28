#!/usr/bin/env python3
"""
Scraper para obtener datos REALES de la Liga Colombiana 2026
Usando FootyStats como fuente principal
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

def get_colombia_2026_from_footystats():
    """Obtiene datos reales de Colombia 2026 desde FootyStats"""
    
    print("🔍 Buscando datos de Liga Colombiana 2026 en FootyStats...")
    
    try:
        # Usar urllib en lugar de requests en algunos casos
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        # Intenta acceder a FootyStats
        url = "https://www.footystats.org/league/LG/colombia-liga-dimayor"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"⚠️ FootyStats no accesible (status: {response.status_code})")
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Buscar tabla de standings
        tables = soup.find_all('table')
        print(f"📊 Encontradas {len(tables)} tablas")
        
        if not tables:
            return None
        
        standings = []
        
        for table in tables:
            rows = table.find_all('tr')[1:]  # Saltar header
            
            for rank, row in enumerate(rows, 1):
                cols = row.find_all('td')
                
                if len(cols) >= 10:
                    try:
                        team_name = cols[1].get_text(strip=True)
                        matches = int(cols[2].get_text(strip=True))
                        wins = int(cols[3].get_text(strip=True))
                        draws = int(cols[4].get_text(strip=True))
                        losses = int(cols[5].get_text(strip=True))
                        goals_for = int(cols[6].get_text(strip=True))
                        goals_against = int(cols[7].get_text(strip=True))
                        points = int(cols[9].get_text(strip=True))
                        
                        standings.append({
                            'position': rank,
                            'team': team_name,
                            'matches': matches,
                            'wins': wins,
                            'draws': draws,
                            'losses': losses,
                            'goals_for': goals_for,
                            'goals_against': goals_against,
                            'points': points,
                            'goal_diff': goals_for - goals_against
                        })
                    except (ValueError, IndexError):
                        continue
        
        if standings:
            print(f"✅ Encontrados {len(standings)} equipos")
            return standings
        
    except Exception as e:
        print(f"❌ Error con FootyStats: {e}")
    
    return None

def scrape_with_selenium():
    """Intenta scrapear con Selenium si es necesario"""
    
    print("🤖 Intentando con Selenium...")
    
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get("https://www.footystats.org/league/LG/colombia-liga-dimayor")
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "table"))
        )
        
        html = driver.page_source
        driver.quit()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        standings = []
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')[1:]
            
            for rank, row in enumerate(rows, 1):
                cols = row.find_all('td')
                
                if len(cols) >= 10:
                    try:
                        team_name = cols[1].get_text(strip=True)
                        matches = int(cols[2].get_text(strip=True))
                        wins = int(cols[3].get_text(strip=True))
                        draws = int(cols[4].get_text(strip=True))
                        losses = int(cols[5].get_text(strip=True))
                        goals_for = int(cols[6].get_text(strip=True))
                        goals_against = int(cols[7].get_text(strip=True))
                        points = int(cols[9].get_text(strip=True))
                        
                        standings.append({
                            'position': rank,
                            'team': team_name,
                            'partidos': matches,
                            'ganados': wins,
                            'empates': draws,
                            'perdidos': losses,
                            'goles_favor': goals_for,
                            'goles_contra': goals_against,
                            'puntos': points,
                            'diferencia': goals_for - goals_against
                        })
                    except (ValueError, IndexError):
                        continue
        
        if standings:
            print(f"✅ Selenium encontró {len(standings)} equipos")
            return standings
        
    except Exception as e:
        print(f"❌ Error con Selenium: {e}")
    
    return None

def update_colombia_with_real_data(standings):
    """Actualiza colombia_stats.json con datos reales"""
    
    print(f"\n📝 Actualizando datos con {len(standings)} equipos reales...")
    
    try:
        with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json', 'r') as f:
            current_data = json.load(f)
    except:
        current_data = {}
    
    # Crear mapping entre nombres de FootyStats y nombres en el JSON actual
    mapping = {}
    for team in current_data.keys():
        for standing in standings:
            standing_name = standing['team'].lower()
            team_lower = team.lower()
            
            if (team_lower in standing_name or standing_name in team_lower or
                len(team_lower) > 3 and team_lower in standing_name[:20]):
                mapping[team] = standing
                break
    
    print(f"✅ Mapeo encontrado para {len(mapping)} equipos")
    
    # Actualizar datos
    updated_data = {}
    for team, stats in current_data.items():
        updated_data[team] = stats.copy()
        
        if team in mapping:
            standing = mapping[team]
            updated_data[team]['position'] = {
                'posicion': standing['position'],
                'partidos': standing['partidos'],
                'ganados': standing['ganados'],
                'empates': standing['empates'],
                'perdidos': standing['perdidos'],
                'goles_favor': standing['goles_favor'],
                'goles_contra': standing['goles_contra'],
                'diferencia': standing['diferencia'],
                'puntos': standing['puntos']
            }
            print(f"  ✓ {team}: Pos {standing['position']}, {standing['goles_favor']} GF, {standing['puntos']} pts")
    
    # Guardar
    with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json', 'w') as f:
        json.dump(updated_data, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ Archivo actualizado: {len(mapping)} equipos con datos reales")

if __name__ == '__main__':
    # Intentar con requests primero
    standings = get_colombia_2026_from_footystats()
    
    # Si falla, intentar con Selenium
    if not standings:
        standings = scrape_with_selenium()
    
    # Si obtuvimos datos, actualizar
    if standings:
        update_colombia_with_real_data(standings)
        print("\n🎉 Datos de Colombia ACTUALIZADOS correctamente")
    else:
        print("\n⚠️ No se pudieron obtener datos reales. Usando datos existentes.")
