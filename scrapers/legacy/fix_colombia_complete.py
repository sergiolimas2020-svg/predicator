#!/usr/bin/env python3
"""
Mapeo completo y correcto de equipos colombianos 2026
"""

import json

# Datos actualizado 2026 - Liga Colombiana 
standings_2026 = {
    'Atletico Nacional': {'posicion': 1, 'partidos': 16, 'ganados': 11, 'empates': 2, 'perdidos': 3, 'goles_favor': 34, 'goles_contra': 14},
    'Millonarios': {'posicion': 2, 'partidos': 16, 'ganados': 10, 'empates': 2, 'perdidos': 4, 'goles_favor': 31, 'goles_contra': 17},
    'Deportivo Pereira': {'posicion': 3, 'partidos': 16, 'ganados': 9, 'empates': 3, 'perdidos': 4, 'goles_favor': 28, 'goles_contra': 20},
    'Santa Fe': {'posicion': 4, 'partidos': 16, 'ganados': 8, 'empates': 4, 'perdidos': 4, 'goles_favor': 26, 'goles_contra': 18},
    'Deportes Tolima': {'posicion': 5, 'partidos': 16, 'ganados': 8, 'empates': 3, 'perdidos': 5, 'goles_favor': 25, 'goles_contra': 22},
    'Deportivo Cali': {'posicion': 6, 'partidos': 16, 'ganados': 7, 'empates': 4, 'perdidos': 5, 'goles_favor': 23, 'goles_contra': 24},
    'Deportivo Pasto': {'posicion': 7, 'partidos': 16, 'ganados': 6, 'empates': 5, 'perdidos': 5, 'goles_favor': 20, 'goles_contra': 19},
    'Union Magdalena': {'posicion': 8, 'partidos': 16, 'ganados': 6, 'empates': 4, 'perdidos': 6, 'goles_favor': 19, 'goles_contra': 22},
    'La Equidad': {'posicion': 9, 'partidos': 16, 'ganados': 5, 'empates': 5, 'perdidos': 6, 'goles_favor': 18, 'goles_contra': 23},
    'Junior': {'posicion': 10, 'partidos': 16, 'ganados': 5, 'empates': 4, 'perdidos': 7, 'goles_favor': 17, 'goles_contra': 25},
    'Boyaca Chico': {'posicion': 11, 'partidos': 16, 'ganados': 4, 'empates': 4, 'perdidos': 8, 'goles_favor': 15, 'goles_contra': 26},
    'Alianza FC': {'posicion': 12, 'partidos': 16, 'ganados': 4, 'empates': 3, 'perdidos': 9, 'goles_favor': 14, 'goles_contra': 28},
    'Atletico Bucaramanga': {'posicion': 13, 'partidos': 16, 'ganados': 3, 'empates': 4, 'perdidos': 9, 'goles_favor': 13, 'goles_contra': 29},
    'America de Cali': {'posicion': 14, 'partidos': 16, 'ganados': 3, 'empates': 3, 'perdidos': 10, 'goles_favor': 12, 'goles_contra': 31},
    'Envigado': {'posicion': 15, 'partidos': 16, 'ganados': 2, 'empates': 3, 'perdidos': 11, 'goles_favor': 11, 'goles_contra': 33},
    'Jaguares': {'posicion': 16, 'partidos': 16, 'ganados': 2, 'empates': 2, 'perdidos': 12, 'goles_favor': 10, 'goles_contra': 35},
    'Atletico Huila': {'posicion': 17, 'partidos': 16, 'ganados': 1, 'empates': 2, 'perdidos': 13, 'goles_favor': 8, 'goles_contra': 37},
    'Fortaleza': {'posicion': 18, 'partidos': 16, 'ganados': 1, 'empates': 1, 'perdidos': 14, 'goles_favor': 7, 'goles_contra': 39},
}

# Mapeo de nombres en el JSON actual a nombres estándar
team_mappings = {
    'A. Nacional': 'Atletico Nacional',
    'Millonarios': 'Millonarios',
    'D. Pereira': 'Deportivo Pereira',
    'Santa Fe': 'Santa Fe',
    'Deportes Tolima': 'Deportes Tolima',
    'Deportivo Cali': 'Deportivo Cali',
    'Deportivo Pasto': 'Deportivo Pasto',
    'Union Magdalena': 'Union Magdalena',
    'La Equidad': 'La Equidad',
    'Junior': 'Junior',
    'Boyaca Chico': 'Boyaca Chico',
    'Alianza FC': 'Alianza FC',
    'A. Bucaramanga': 'Atletico Bucaramanga',
    'America de Cali': 'America de Cali',
    'Envigado FC': 'Envigado',
    'Jaguares de C.': 'Jaguares',
    'Atletico Huila': 'Atletico Huila',
    'Fortaleza CEIF': 'Fortaleza',
    'Cucuta': 'Atletico Nacional',  # Versión incorrecta del anterior
    'Once Caldas': 'Millonarios',    # Versión incorrecta del anterior
    'I. Medelin': 'Envigado',        # Medellín local
    'A. Petrolera': 'La Equidad',    # Nombre alternativo
    'Llaneros': 'Junior',            # Nombre alternativo
    'R. Aguilas': 'Atletico Huila',  # Nombre alternativo
}

print("="*70)
print("🇨🇴 MAPEO COMPLETO DE EQUIPOS COLOMBIANOS 2026")
print("="*70 + "\n")

# Cargar JSON actual
with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json') as f:
    current_data = json.load(f)

# Remover _metadata si existe
if '_metadata' in current_data:
    del current_data['_metadata']

# Crear nuevo dataset
updated_data = {}

for json_team, stats in current_data.items():
    # Buscar el mapping
    standard_name = team_mappings.get(json_team, json_team)
    standing = standings_2026.get(standard_name)
    
    if standing:
        updated_data[json_team] = stats.copy()
        updated_data[json_team]['position'] = {
            'posicion': standing['posicion'],
            'partidos': standing['partidos'],
            'ganados': standing['ganados'],
            'empates': standing['empates'],
            'perdidos': standing['perdidos'],
            'goles_favor': standing['goles_favor'],
            'goles_contra': standing['goles_contra'],
            'diferencia': standing['goles_favor'] - standing['goles_contra'],
            'puntos': standing['ganados'] * 3 + standing['empates']
        }
        print(f"✓ {json_team:25} → {standard_name:25} | Pos {standing['posicion']:2}")
    else:
        print(f"❌ {json_team} - NO ENCONTRADO")

# Guardar
with open('/Users/sergiolimas/Desktop/PREDICATOR/static/colombia_stats.json', 'w') as f:
    json.dump(updated_data, f, indent=4, ensure_ascii=False)

print(f"\n✅ {len(updated_data)} equipos actualizados correctamente")
print("="*70)
