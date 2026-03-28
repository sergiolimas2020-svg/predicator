#!/usr/bin/env python3
"""
Scraper con múltiples fuentes: SofaScore, 365Score, APIs públicas
"""

import requests
import json
import time
from bs4 import BeautifulSoup

def get_from_sofascore():
    """Intenta obtener datos de SofaScore"""
    
    print("📡 Intentando SofaScore...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        # API de SofaScore para Liga Colombiana
        url = "https://www.sofascore.com/api/v1/unique-tournament/33678/seasons/67893/standings/total"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Conectado a SofaScore")
            return data
        else:
            print(f"  ❌ Status: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:80]}")
        return None

def get_from_api_sports():
    """Intenta API-Sports (rapidapi)"""
    
    print("📡 Intentando API-Sports...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        }
        
        # Intenta sin key primero
        url = "https://api.api-football.com/v3/standings?league=141&season=2026"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Conectado a API-Sports")
            return data
        else:
            print(f"  ❌ Status: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:80]}")
        return None

def get_from_football_data():
    """Intenta Football-Data.org"""
    
    print("📡 Intentando Football-Data.org...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        }
        
        # Liga Colombiana
        url = "https://api.football-data.org/v4/competitions/CL1/standings"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Conectado a Football-Data.org")
            return data
        elif response.status_code == 429:
            print(f"  ⏱️  Rate limit (necesita API key)")
        else:
            print(f"  ❌ Status: {response.status_code}")
        return None
    
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:80]}")
        return None

def get_from_espn_api():
    """Intenta ESPN API"""
    
    print("📡 Intentando ESPN API...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        }
        
        # ESPN tiene una API pública
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/col.1/standings"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Conectado a ESPN API")
            return data
        else:
            print(f"  ❌ Status: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:80]}")
        return None

def parse_sofascore_data(data):
    """Parsear datos de SofaScore"""
    
    if not data:
        return None
    
    try:
        standings = []
        
        for group in data.get('standings', []):
            for row in group.get('rows', []):
                team = row.get('team', {})
                standings.append({
                    'posicion': row.get('position'),
                    'equipo': team.get('name'),
                    'partidos': row.get('matches', 0),
                    'ganados': row.get('wins', 0),
                    'empates': row.get('draws', 0),
                    'perdidos': row.get('losses', 0),
                    'goles_favor': row.get('scoresFor', 0),
                    'goles_contra': row.get('scoresAgainst', 0),
                    'puntos': row.get('points', 0)
                })
        
        return standings if standings else None
    
    except Exception as e:
        print(f"  Error parsing: {str(e)[:50]}")
        return None

def parse_espn_data(data):
    """Parsear datos de ESPN API"""
    
    if not data:
        return None
    
    try:
        standings = []
        
        for league in data.get('standings', {}).get('groups', []):
            for idx, team_data in enumerate(league.get('standings', []), 1):
                stats = team_data.get('stats', {})
                
                # Buscar valores por nombre de clave
                wins = 0
                draws = 0
                losses = 0
                gf = 0
                ga = 0
                
                for stat in stats:
                    if stat.get('name') == 'wins':
                        wins = stat.get('value', 0)
                    elif stat.get('name') == 'draws':
                        draws = stat.get('value', 0)
                    elif stat.get('name') == 'losses':
                        losses = stat.get('value', 0)
                    elif stat.get('name') == 'goalsFor':
                        gf = stat.get('value', 0)
                    elif stat.get('name') == 'goalsAgainst':
                        ga = stat.get('value', 0)
                
                standings.append({
                    'posicion': idx,
                    'equipo': team_data.get('team', {}).get('name'),
                    'partidos': team_data.get('matches', 0),
                    'ganados': wins,
                    'empates': draws,
                    'perdidos': losses,
                    'goles_favor': gf,
                    'goles_contra': ga,
                    'puntos': team_data.get('points', 0)
                })
        
        return standings if standings else None
    
    except Exception as e:
        print(f"  Error parsing ESPN: {str(e)[:50]}")
        return None

def update_colombia_json(standings):
    """Actualizar JSON con datos reales"""
    
    print(f"\n📝 Actualizando Colombia con {len(standings)} equipos...\n")
    
    with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json') as f:
        current_data = json.load(f)
    
    if '_metadata' in current_data:
        del current_data['_metadata']
    
    # Mapeo flexible
    mapping = {}
    
    for team in current_data.keys():
        team_lower = team.lower().replace(' ', '').replace('.', '')
        
        for standing in standings:
            if not standing.get('equipo'):
                continue
            
            standing_name = standing['equipo'].lower().replace(' ', '').replace('.', '')
            
            if (team_lower in standing_name or standing_name in team_lower or
                team_lower.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o') == 
                standing_name.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o')):
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
    
    return updated > 0

def print_standings(standings):
    """Mostrar tabla"""
    
    print("\n📊 TABLA DE POSICIONES:")
    print("="*90)
    print(f"{'Pos':>3} {'Equipo':30} {'J':>2} {'G':>2} {'E':>2} {'P':>2} {'GF':>2} {'GC':>2} {'Pts':>3}")
    print("="*90)
    
    for s in sorted(standings, key=lambda x: x['posicion'])[:20]:
        print(f"{s['posicion']:3} {s['equipo'][:30]:30} {s['partidos']:2} {s['ganados']:2} {s['empates']:2} {s['perdidos']:2} {s['goles_favor']:2} {s['goles_contra']:2} {s['puntos']:3}")

if __name__ == '__main__':
    print("="*90)
    print("🇨🇴 SCRAPING MÚLTIPLES FUENTES - LIGA COLOMBIANA 2026")
    print("="*90 + "\n")
    
    standings = None
    source = None
    
    # Intentar múltiples fuentes en orden
    sources = [
        ('SofaScore', get_from_sofascore, parse_sofascore_data),
        ('ESPN API', get_from_espn_api, parse_espn_data),
        ('Football-Data', get_from_football_data, None),
        ('API-Sports', get_from_api_sports, None),
    ]
    
    for source_name, fetcher, parser in sources:
        data = fetcher()
        
        if data:
            if parser:
                standings = parser(data)
            else:
                standings = data
            
            if standings and len(standings) >= 15:
                print(f"\n🎯 Usando datos de: {source_name}\n")
                break
        
        time.sleep(1)  # Respetar rate limits
    
    if standings and len(standings) >= 15:
        print_standings(standings)
        update_colombia_json(standings)
        print("\n🎉 ¡ACTUALIZACIÓN COMPLETADA CON DATOS REALES!")
    else:
        print("\n❌ No se obtuvieron datos suficientes de ninguna fuente")
    
    print("="*90 + "\n")
