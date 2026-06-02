#!/usr/bin/env python3
"""
Web Scraper avanzado usando CloudScraper y Playwright
CloudScraper es excelente para evadir protecciones Cloudflare y anti-bot
"""

import json
import time
from bs4 import BeautifulSoup

def scrape_flashscore_with_cloudscraper():
    """Usa CloudScraper para evadir protecciones anti-bot"""
    
    print("📡 Usando CloudScraper para FlashScore...")
    
    try:
        import cloudscraper
        
        scraper = cloudscraper.create_scraper()
        
        url = "https://www.flashscore.co/clasificacion/tYhlmBUI/I7rbp1up/#/I7rbp1up/clasificacion/general/"
        
        print(f"  Accediendo a: {url}")
        
        response = scraper.get(url, timeout=15)
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar tabla
            tables = soup.find_all('table')
            print(f"  Encontradas {len(tables)} tablas")
            
            standings = []
            
            for table_idx, table in enumerate(tables):
                print(f"  Analizando tabla {table_idx + 1}...")
                
                rows = table.find_all('tr')
                
                for row_idx, row in enumerate(rows[1:], 1):  # Saltar header
                    try:
                        cols = row.find_all(['td', 'th'])
                        
                        if len(cols) >= 8:
                            texts = [col.get_text(strip=True) for col in cols]
                            
                            # Intentar parsear
                            pos = int(texts[0])
                            team = texts[1]
                            pj = int(texts[2])
                            g = int(texts[3])
                            e = int(texts[4])
                            p = int(texts[5])
                            gf = int(texts[6])
                            gc = int(texts[7])
                            pts = int(texts[8]) if len(texts) > 8 else g*3 + e
                            
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
                            
                            print(f"    ✓ {pos:2}. {team:25} | {pj} PJ | {pts} Pts")
                    
                    except (ValueError, IndexError) as e:
                        continue
            
            if standings:
                print(f"\n✅ CloudScraper encontró {len(standings)} equipos")
                return standings
        
        return None
    
    except Exception as e:
        print(f"  ❌ Error CloudScraper: {str(e)[:100]}")
        return None

def scrape_with_playwright():
    """Usa Playwright como alternativa a Selenium"""
    
    print("📡 Intentando con Playwright...")
    
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            
            url = "https://www.flashscore.co/clasificacion/tYhlmBUI/I7rbp1up/#/I7rbp1up/clasificacion/general/"
            
            print(f"  Accediendo a: {url}")
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Esperar tabla
            page.wait_for_selector('table', timeout=10000)
            
            time.sleep(2)
            
            html = page.content()
            browser.close()
            
            soup = BeautifulSoup(html, 'html.parser')
            
            tables = soup.find_all('table')
            print(f"  Encontradas {len(tables)} tablas")
            
            standings = []
            
            for table in tables:
                rows = table.find_all('tr')[1:]
                
                for row in rows:
                    try:
                        cols = row.find_all(['td', 'th'])
                        
                        if len(cols) >= 8:
                            texts = [col.get_text(strip=True) for col in cols]
                            
                            pos = int(texts[0])
                            team = texts[1]
                            pj = int(texts[2])
                            g = int(texts[3])
                            e = int(texts[4])
                            p = int(texts[5])
                            gf = int(texts[6])
                            gc = int(texts[7])
                            pts = int(texts[8]) if len(texts) > 8 else g*3 + e
                            
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
                            
                            print(f"    ✓ {pos:2}. {team:25} | {pj} PJ | {pts} Pts")
                    
                    except (ValueError, IndexError):
                        continue
            
            if standings:
                print(f"\n✅ Playwright encontró {len(standings)} equipos")
                return standings
        
        return None
    
    except Exception as e:
        print(f"  ❌ Error Playwright: {str(e)[:100]}")
        return None

def update_colombia_json(standings):
    """Actualizar JSON"""
    
    print(f"\n📝 Actualizando Colombia con {len(standings)} equipos...\n")
    
    with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json') as f:
        current_data = json.load(f)
    
    if '_metadata' in current_data:
        del current_data['_metadata']
    
    # Mapeo
    mapping = {}
    
    for team in current_data.keys():
        team_lower = team.lower().replace(' ', '').replace('.', '')
        
        for standing in standings:
            standing_name = standing['equipo'].lower().replace(' ', '').replace('.', '')
            
            if (team_lower in standing_name or standing_name in team_lower or
                team_lower.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ü', 'u') == 
                standing_name.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ü', 'u')):
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
    
    with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json', 'w') as f:
        json.dump(current_data, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ {updated} equipos actualizados")
    
    return updated > 0

if __name__ == '__main__':
    print("="*90)
    print("🇨🇴 WEB SCRAPING AVANZADO - CLOUDSCRAPER + PLAYWRIGHT")
    print("="*90 + "\n")
    
    standings = None
    
    # Intentar CloudScraper primero
    standings = scrape_flashscore_with_cloudscraper()
    
    # Si falla, intentar Playwright
    if not standings or len(standings) < 15:
        print()
        standings = scrape_with_playwright()
    
    if standings and len(standings) >= 15:
        update_colombia_json(standings)
        print("\n🎉 ¡ACTUALIZACIÓN COMPLETADA!")
    else:
        print("\n❌ No se obtuvieron suficientes datos")
    
    print("="*90 + "\n")
