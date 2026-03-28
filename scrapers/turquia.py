import requests
from bs4 import BeautifulSoup
import json
import os
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def safe_request(url, max_retries=3):
    """Realizar solicitud HTTP con reintento y manejo de errores"""
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
    """Conversión segura de tipos"""
    try:
        return type_func(str(value).replace(',', '.')) if value else default
    except ValueError:
        return default

def scrape_corners_data(url):
    """TU CÓDIGO - Extrae datos de córners (FUNCIONA PERFECTO)"""
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
    """TU CÓDIGO - Extrae datos de goles (FUNCIONA PERFECTO)"""
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
    """MI CÓDIGO - Extrae posiciones (FUNCIONA PERFECTO)"""
    try:
        response = safe_request(url)
        positions_data = {}
        
        soup = BeautifulSoup(response.content, 'html.parser')
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 15:  # Necesitamos tabla con suficientes equipos
                continue
                
            position = 1
            teams_found = 0
            
            for row in rows[1:]:  # Saltar header
                cells = row.find_all(['td', 'th'])
                if len(cells) < 8:
                    continue
                    
                cell_texts = [cell.get_text().strip() for cell in cells]
                
                # Buscar nombre del equipo y estadísticas
                for i, text in enumerate(cell_texts):
                    if (text and len(text) > 2 and 
                        not text.isdigit() and 
                        any(c.isalpha() for c in text) and
                        text.upper() not in ['LEAGUES', 'MATCHES', 'STATS', 'HOME', 'AWAY']):
                        
                        # Buscar números después del nombre
                        remaining = cell_texts[i+1:]
                        numbers = [x for x in remaining if x.isdigit()]
                        
                        if len(numbers) >= 6:
                            try:
                                mp, w, d, l, gf, ga = [int(x) for x in numbers[:6]]
                                
                                # Validar datos
                                if mp > 0 and w + d + l == mp and gf >= 0 and ga >= 0:
                                    positions_data[text] = {
                                        "posicion": position,
                                        "partidos": mp,
                                        "ganados": w,
                                        "empatados": d,
                                        "perdidos": l,
                                        "goles_favor": gf,
                                        "goles_contra": ga,
                                        "diferencia": gf - ga,
                                        "puntos": w * 3 + d
                                    }
                                    
                                    logger.info(f"✅ {position}. {text} - {w * 3 + d} pts")
                                    position += 1
                                    teams_found += 1
                                    break
                                    
                            except (ValueError, IndexError):
                                continue
                
                if teams_found >= 20:  # Suficientes equipos
                    break
            
            if teams_found >= 15:  # Tabla válida encontrada
                logger.info(f"✅ Posiciones extraídas: {teams_found} equipos")
                return positions_data
        
        logger.warning("No se encontró tabla de posiciones válida")
        return {}
        
    except Exception as e:
        logger.error(f"Error en scrape_positions_data: {e}")
        return {}

def main(league="brazil"):
    """Función principal fusionada"""
    try:
        # URLs dinámicas para cualquier liga
        corners_url = f"https://www.soccerstats.com/table.asp?league={league}&tid=cr"
        goals_url = f"https://www.soccerstats.com/table.asp?league={league}&tid=c"
        positions_url = f"https://www.soccerstats.com/latest.asp?league={league}"
        
        logger.info(f"🔥 Iniciando extracción completa para liga: {league.upper()}")
        
        # Obtener todos los datos usando LO MEJOR de ambos códigos
        logger.info("📊 Extrayendo datos de posiciones...")
        positions_data = scrape_positions_data(positions_url)
        
        logger.info("🚩 Extrayendo datos de córners...")
        corners_data = scrape_corners_data(corners_url)
        
        logger.info("⚽ Extrayendo datos de goles...")
        goals_data = scrape_goals_data(goals_url)
        
        # Combinar todos los datos en TU estructura
        combined_data = {}
        all_teams = set(list(corners_data.keys()) + list(goals_data.keys()) + list(positions_data.keys()))
        
        for team in all_teams:
            combined_data[team] = {
                "corners": corners_data.get(team, {}),
                "goals": goals_data.get(team, {}),
                "position": positions_data.get(team, {})
            }
        
        # Agregar metadatos
        combined_data['_metadata'] = {
            'fecha_actualizacion': datetime.now().isoformat(),
            'liga': league,
            'fuente_datos': {
                'corners': corners_url,
                'goals': goals_url,
                'positions': positions_url
            },
            'equipos_extraidos': {
                'corners': len(corners_data),
                'goals': len(goals_data), 
                'positions': len(positions_data)
            }
        }
        
        # Crear directorio static si no existe
        static_folder = 'static'
        os.makedirs(static_folder, exist_ok=True)
        
        # Guardar archivo
        file_path = os.path.join(static_folder, f'{league}_stats.json')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, ensure_ascii=False, indent=4)
        
        logger.info(f"🎉 Datos completos guardados en {file_path}")
        
        # Mostrar resumen
        print(f"\n📋 RESUMEN FINAL:")
        print(f"   📊 Posiciones: {len(positions_data)} equipos")
        print(f"   🚩 Corners: {len(corners_data)} equipos")
        print(f"   ⚽ Goals: {len(goals_data)} equipos")
        print(f"   📁 Archivo: {file_path}")
        
        # Mostrar top 5 con TODOS los datos
        print(f"\n🏆 TOP 5 COMPLETO:")
        teams_with_positions = [(team, data['position']) for team, data in combined_data.items() 
                               if data.get('position') and 'posicion' in data['position']]
        
        teams_with_positions.sort(key=lambda x: x[1]['posicion'])
        
        for team, pos_data in teams_with_positions[:5]:
            team_data = combined_data[team]
            
            print(f"\n{pos_data['posicion']}. {team} - {pos_data['puntos']} pts")
            
            # Corners
            if team_data.get('corners'):
                corners = team_data['corners']
                if 'local' in corners:
                    print(f"   🚩 Corners Local: {corners['local'].get('corners_favor', 'N/A')}")
                if 'visitante' in corners:
                    print(f"   🚩 Corners Visitante: {corners['visitante'].get('corners_favor', 'N/A')}")
            
            # Goals
            if team_data.get('goals'):
                goals = team_data['goals']
                print(f"   ⚽ Over 1.5: {goals.get('over_1_5', 'N/A')}")
                print(f"   ⚽ Over 2.5: {goals.get('over_2_5', 'N/A')}")
                print(f"   ⚽ BTS: {goals.get('bts', 'N/A')}")
        
        return combined_data
    
    except Exception as e:
        logger.error(f"Error general en la actualización: {e}")
        raise

if __name__ == "__main__":
    # Brasil por defecto
    main("turkey" \
    "")
    
    # Para otras ligas:
    # main("england")
    # main("spain") 
    # main("italy")