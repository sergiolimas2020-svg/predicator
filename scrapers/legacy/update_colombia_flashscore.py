#!/usr/bin/env python3
"""
Update colombia_stats.json with accurate Flashscore data from March 27, 2026
"""
import json
import os

# Datos extraídos directamente de la imagen de Flashscore
datos_liga_colombia = {
    'Equipo': [
        'Atl. Nacional', 'Dep. Pasto', 'Once Caldas', 'Junior', 'América de Cali',
        'Inter Bogotá', 'Millonarios', 'Tolima', 'Atl. Bucaramanga', 'Águilas Doradas',
        'Deportivo Cali', 'Llaneros', 'Ind. Santa Fe', 'Fortaleza', 'Ind. Medellín',
        'Jaguares de Córdoba', 'Alianza', 'Cúcuta', 'Boyacá Chicó', 'Pereira'
    ],
    'PJ': [12, 13, 13, 13, 12, 13, 13, 12, 12, 13, 13, 13, 12, 13, 12, 13, 13, 13, 12, 12],
    'G': [9, 8, 6, 7, 6, 5, 6, 5, 4, 5, 4, 3, 3, 3, 3, 3, 2, 1, 2, 0],
    'E': [0, 3, 5, 1, 3, 6, 2, 5, 7, 4, 4, 7, 6, 5, 4, 2, 5, 5, 2, 6],
    'P': [3, 2, 2, 5, 3, 2, 5, 2, 1, 4, 5, 3, 3, 5, 5, 8, 6, 7, 8, 6],
    'Goles': ['26:9', '20:15', '24:17', '19:18', '16:8', '17:18', '23:14', '15:9', '16:8', '13:12', '14:12', '14:13', '14:15', '14:20', '16:17', '11:23', '7:20', '18:27', '10:20', '12:24'],
    'DG': [17, 5, 7, 1, 8, -1, 9, 6, 8, 1, 2, 1, -1, -6, -1, -12, -13, -9, -10, -12],
    'PTS': [27, 27, 23, 22, 21, 21, 20, 20, 19, 19, 16, 16, 15, 14, 13, 11, 11, 8, 8, 6],
    'Corners_Prom': [5.8, 4.5, 5.2, 6.1, 5.4, 4.1, 6.3, 5.1, 5.2, 4.3, 4.9, 4.0, 5.7, 4.2, 5.3, 3.8, 3.7, 4.4, 3.9, 4.6]
}

# Conversión de nombres a claves JSON (mapeo a los nombres en el JSON actual)
team_name_mapping = {
    'Atl. Nacional': 'Atlético Nacional',
    'Dep. Pasto': 'Deportivo Pasto',
    'Once Caldas': 'Once Caldas',
    'Junior': 'Junior',
    'América de Cali': 'América',
    'Inter Bogotá': 'Inter',
    'Millonarios': 'Millonarios',
    'Tolima': 'Tolima',
    'Atl. Bucaramanga': 'Bucaramanga',
    'Águilas Doradas': 'R. Aguilas',
    'Deportivo Cali': 'Cali',
    'Llaneros': 'Llaneros',
    'Ind. Santa Fe': 'Santa Fe',
    'Fortaleza': 'Fortaleza',
    'Ind. Medellín': 'Medellín',
    'Jaguares de Córdoba': 'Jaguares',
    'Alianza': 'Alianza',
    'Cúcuta': 'Cucuta',
    'Boyacá Chicó': 'Boyacá',
    'Pereira': 'Pereira'
}

def extract_goals(goles_str):
    """Extract Goal For and Goal Against from 'GF:GC' format"""
    parts = goles_str.split(':')
    return int(parts[0]), int(parts[1])

def create_colombia_json():
    """Create updated colombia_stats.json with Flashscore data"""
    
    colombia_data = {}
    
    for idx in range(len(datos_liga_colombia['Equipo'])):
        equipo_original = datos_liga_colombia['Equipo'][idx]
        equipo_json_key = team_name_mapping[equipo_original]
        
        # Extract goals
        gf, gc = extract_goals(datos_liga_colombia['Goles'][idx])
        
        # Calculate position (idx + 1 since we're 0-indexed)
        position = idx + 1
        
        # Create team data structure
        colombia_data[equipo_json_key] = {
            "corners": {
                "partidos": 0,
                "promedio": datos_liga_colombia['Corners_Prom'][idx]
            },
            "footystats": {
                "over_2_5": "Calculate",  # These will need to be calculated separately
                "btts": "Calculate"
            },
            "position": {
                "posicion": position,
                "partidos": datos_liga_colombia['PJ'][idx],
                "ganados": datos_liga_colombia['G'][idx],
                "empates": datos_liga_colombia['E'][idx],
                "perdidos": datos_liga_colombia['P'][idx],
                "goles_favor": gf,
                "goles_contra": gc,
                "diferencia": datos_liga_colombia['DG'][idx],
                "puntos": datos_liga_colombia['PTS'][idx]
            },
            "goals": {
                "over_1_5": "Calculate",
                "over_2_5": "Calculate",
                "over_3_5": "Calculate",
                "btts": "Calculate",
                "bts": "Calculate"
            }
        }
    
    return colombia_data

# Main execution
if __name__ == "__main__":
    # Get workspace root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(script_dir)
    json_path = os.path.join(workspace_root, 'static', 'colombia_stats.json')
    
    # Create new data
    new_data = create_colombia_json()
    
    # Save to JSON file
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, indent=4, ensure_ascii=False)
    
    print(f"✅ Colombia stats updated successfully!")
    print(f"📍 File: {json_path}")
    print(f"📊 Teams updated: {len(new_data)}")
    print("\n✨ Top 3 Teams:")
    for team, data in list(new_data.items())[:3]:
        pos = data['position']
        print(f"  {pos['posicion']}. {team} - {pos['puntos']} pts ({pos['ganados']}-{pos['empates']}-{pos['perdidos']})")
    print(f"\n⚠️ Last Place:")
    last_team = list(new_data.items())[-1]
    pos = last_team[1]['position']
    print(f"  {pos['posicion']}. {last_team[0]} - {pos['puntos']} pts ({pos['ganados']}-{pos['empates']}-{pos['perdidos']})")
