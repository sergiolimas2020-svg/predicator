#!/usr/bin/env python3
"""
Web scraping desde FlashScore - Liga Colombiana 2026
FlashScore es más confiable que otras fuentes
"""

import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def scrape_flashscore_colombia():
    """Obtiene datos de FlashScore para Liga Colombiana"""
    
    print("📡 Intentando FlashScore.com...")
    print("⏳ Cargando página... (puede tomar 15-30 segundos)\n")
    
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # URL de FlashScore para Liga Colombiana
        url = "https://www.flashscore.com/baseball/colombia/liga-bdb/standings/"
        
        print(f"  Accediendo a: {url}")
        driver.get(url)
        
        # Esperar que cargue la tabla
        print("  Esperando tabla de posiciones...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, "//table//tr"))
        )
        
        time.sleep(3)
        
        html = driver.page_source
        driver.quit()
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        standings = []
        
        # Buscar filas de tabla
        rows = soup.find_all('tr')
        print(f"  Encontradas {len(rows)} filas\n")
        
        for idx, row in enumerate(rows[1:], 1):  # Saltar header
            try:
                cols = row.find_all('td')
                
                if len(cols) >= 9:
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
                    
                    print(f"  ✓ {pos:2}. {team_name:30} | {partidos:2} PJ | {puntos:2} Pts | GF:{goles_favor:2} GC:{goles_contra:2}")
            
            except (ValueError, IndexError) as e:
                continue
        
        if standings:
            print(f"\n✅ FlashScore: {len(standings)} equipos encontrados")
            return standings
        else:
            print("⚠️  No se encontraron datos en tabla")
            return None
    
    except Exception as e:
        print(f"❌ Error FlashScore: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return None

def update_colombia_from_flashscore(standings):
    """Actualiza JSON con datos de FlashScore"""
    
    print(f"\n📝 Actualizando Colombia desde FlashScore ({len(standings)} equipos)...\n")
    
    # Cargar JSON actual
    with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json') as f:
        current_data = json.load(f)
    
    # Remover _metadata si existe
    if '_metadata' in current_data:
        del current_data['_metadata']
    
    # Mapeo de nombres
    team_mappings = {
        'A. Nacional': 'Atletico Nacional',
        'Atletico Nacional': 'Atletico Nacional',
        'Cucuta': 'Atletico Nacional',
        
        'Deportivo Pasto': 'Deportivo Pasto',
        'Pasto': 'Deportivo Pasto',
        
        'Once Caldas': 'Once Caldas',
        
        'Millonarios': 'Millonarios',
        
        'Deportes Tolima': 'Tolima',
        'Tolima': 'Tolima',
        
        'Santa Fe': 'Santa Fe',
        
        'Deportivo Cali': 'Deportivo Cali',
        
        'Junior': 'Junior',
        'Llaneros': 'Junior',
        
        'La Equidad': 'La Equidad',
        'A. Petrolera': 'La Equidad',
        
        'America de Cali': 'America de Cali',
        
        'Boyaca Chico': 'Boyaca Chico',
        'Boyaca Chicó': 'Boyaca Chico',
        
        'Envigado FC': 'Envigado',
        'Envigado': 'Envigado',
        'I. Medelin': 'Envigado',
        
        'A. Bucaramanga': 'Bucaramanga',
        'Atletico Bucaramanga': 'Bucaramanga',
        
        'Fortaleza CEIF': 'Fortaleza',
        'Fortaleza': 'Fortaleza',
        
        'Jaguares de C.': 'Jaguares',
        'Jaguares FC': 'Jaguares',
        
        'Union Magdalena': 'Union Magdalena',
        
        'Atletico Huila': 'Atletico Huila',
        
        'Alianza FC': 'Alianza FC',
        
        'R. Aguilas': 'R. Aguilas',
        
        'D. Pereira': 'Deportivo Pereira',
        'Deportivo Pereira': 'Deportivo Pereira',
    }
    
    mapping = {}
    for team in current_data.keys():
        team_lower = team.lower().replace(' ', '').replace('.', '')
        
        for standing in standings:
            standing_name = standing['equipo'].lower().replace(' ', '').replace('.', '')
            
            if (team_lower in standing_name or standing_name in team_lower or
                team_lower.replace('á', 'a').replace('é', 'e') == 
                standing_name.replace('á', 'a').replace('é', 'e')):
                mapping[team] = standing
                break
    
    # Actualizar datos
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
            
            print(f"  ✓ {team:25} | Pos {standing['posicion']:2} | {standing['partidos']} PJ | {standing['puntos']} Pts | GF:{standing['goles_favor']:2} GC:{standing['goles_contra']:2}")
    
    # Guardar
    with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json', 'w') as f:
        json.dump(current_data, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ {updated} equipos actualizados correctamente")
    print("💾 Archivo guardado: static/colombia_stats.json")
    
    return updated > 0

if __name__ == '__main__':
    print("="*90)
    print("🇨🇴 WEB SCRAPING DESDE FLASHSCORE - LIGA COLOMBIANA 2026")
    print("="*90 + "\n")
    
    standings = scrape_flashscore_colombia()
    
    if standings:
        update_colombia_from_flashscore(standings)
        print("\n🎉 ¡DATOS ACTUALIZADOS DESDE FLASHSCORE!")
    else:
        print("❌ No se pudieron obtener datos de FlashScore")
    
    print("="*90 + "\n")
