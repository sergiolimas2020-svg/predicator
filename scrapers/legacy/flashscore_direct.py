#!/usr/bin/env python3
"""
Web scraping desde FlashScore Colombia - URL específica proporcionada
"""

import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def scrape_flashscore_colombia_direct():
    """Obtiene tabla de FlashScore Colombia directamente de la URL"""
    
    print("📡 Scrapeando FlashScore Colombia (URL directa)...")
    print("⏳ Cargando página...\n")
    
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # URL específica de FlashScore Colombia
        url = "https://www.flashscore.co/clasificacion/tYhlmBUI/I7rbp1up/#/I7rbp1up/clasificacion/general/"
        
        print(f"  Accediendo a: {url}\n")
        driver.get(url)
        
        # Esperar que cargue la tabla
        print("  Esperando tabla de posiciones...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, "//table//tbody//tr"))
        )
        
        time.sleep(3)
        
        html = driver.page_source
        driver.quit()
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        standings = []
        
        # Buscar tabla
        tables = soup.find_all('table')
        print(f"  Encontradas {len(tables)} tablas")
        
        for table_idx, table in enumerate(tables):
            print(f"  Analizando tabla {table_idx + 1}...")
            
            rows = table.find_all('tr')[1:]  # Saltar header
            
            for row in rows:
                try:
                    cols = row.find_all(['td', 'th'])
                    
                    if len(cols) >= 9:
                        text_values = [col.get_text(strip=True) for col in cols]
                        
                        # Intentar extraer información (estructura puede variar)
                        pos = int(text_values[0])
                        team = text_values[1]
                        pj = int(text_values[2])
                        g = int(text_values[3])
                        e = int(text_values[4])
                        p = int(text_values[5])
                        gf = int(text_values[6])
                        gc = int(text_values[7])
                        pts = int(text_values[8])
                        
                        standings.append({
                            'posicion': pos,
                            'equipo': team,
                            'partidos': pj,
                            'ganados': g,
                            'empates': e,
                            'perdidos': p,
                            'goles_favor': gf,
                            'goles_contra': gc,
                            'puntos': pts
                        })
                        
                        print(f"    ✓ {pos:2}. {team:30} | {pj} PJ | {pts} Pts")
                
                except (ValueError, IndexError, AttributeError) as e:
                    continue
        
        if standings:
            print(f"\n✅ Encontrados {len(standings)} equipos")
            return standings
        else:
            print("\n⚠️  No se encontraron datos en la tabla")
            return None
    
    except Exception as e:
        print(f"❌ Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return None

def update_colombia_with_real_data(standings):
    """Actualiza JSON con datos reales de FlashScore"""
    
    print(f"\n📝 Actualizando Colombia con {len(standings)} equipos reales...\n")
    
    # Cargar JSON
    with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json') as f:
        current_data = json.load(f)
    
    if '_metadata' in current_data:
        del current_data['_metadata']
    
    # Mapeo
    team_mappings = {
        'A. Nacional': 'Atl. Nacional',
        'Atletico Nacional': 'Atl. Nacional',
        'Cucuta': 'Atl. Nacional',
        'Atl. Nacional': 'Atl. Nacional',
        'Nacional': 'Atl. Nacional',
        
        'Deportivo Pasto': 'Pasto',
        'Pasto': 'Pasto',
        'D. Pasto': 'Pasto',
        
        'Once Caldas': 'Once Caldas',
        
        'Millonarios': 'Millonarios',
        
        'Deportes Tolima': 'Tolima',
        'Tolima': 'Tolima',
        
        'Santa Fe': 'Santa Fe',
        
        'Deportivo Cali': 'Cali',
        'Cali': 'Cali',
        
        'Junior': 'Junior',
        'Llaneros': 'Junior',
        
        'La Equidad': 'La Equidad',
        'A. Petrolera': 'Petrolera',
        
        'America de Cali': 'América',
        
        'Boyaca Chico': 'Boyacá',
        'Boyaca Chicó': 'Boyacá',
        
        'Envigado FC': 'Envigado',
        'Envigado': 'Envigado',
        'I. Medelin': 'Envigado',
        
        'A. Bucaramanga': 'Bucaramanga',
        'Atletico Bucaramanga': 'Bucaramanga',
        
        'Fortaleza CEIF': 'Fortaleza',
        'Fortaleza': 'Fortaleza',
        
        'Jaguares de C.': 'Jaguares',
        'Jaguares': 'Jaguares',
        
        'Union Magdalena': 'Mag.',
        'Magdalena': 'Mag.',
        
        'Atletico Huila': 'Huila',
        
        'Alianza FC': 'Alianza',
        
        'R. Aguilas': 'Águilas',
        
        'D. Pereira': 'Pereira',
        'Deportivo Pereira': 'Pereira',
    }
    
    mapping = {}
    for team in current_data.keys():
        team_lower = team.lower().replace(' ', '').replace('.', '')
        
        for standing in standings:
            standing_name = standing['equipo'].lower().replace(' ', '').replace('.', '')
            
            # Búsqueda flexible con múltiples intentos
            if (team_lower in standing_name or standing_name in team_lower or
                team_lower.replace('á', 'a').replace('é', 'e').replace('í', 'i') == 
                standing_name.replace('á', 'a').replace('é', 'e').replace('í', 'i')):
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
    
    print(f"\n✅ {updated} equipos actualizados correctamente")
    print("💾 Archivo guardado: static/colombia_stats.json")
    
    return updated > 0

if __name__ == '__main__':
    print("="*90)
    print("🇨🇴 SCRAPING FLASHSCORE COLOMBIA - DATOS REALES")
    print("="*90 + "\n")
    
    standings = scrape_flashscore_colombia_direct()
    
    if standings and len(standings) >= 15:
        update_colombia_with_real_data(standings)
        print("\n🎉 ¡ACTUALIZACIÓN CON DATOS REALES DE FLASHSCORE COMPLETADA!")
    else:
        print("\n❌ No se pudieron obtener suficientes datos")
    
    print("="*90 + "\n")
