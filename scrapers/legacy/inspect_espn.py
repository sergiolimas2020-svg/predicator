#!/usr/bin/env python3
"""
Inspeccionar respuesta de ESPN API
"""

import requests
import json

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
}

url = "https://site.api.espn.com/apis/site/v2/sports/soccer/col.1/standings"

print("Conectando a ESPN API...")
response = requests.get(url, headers=headers, timeout=10)

print(f"Status: {response.status_code}\n")

if response.status_code == 200:
    data = response.json()
    
    print("Estructura de datos:")
    print(json.dumps(data, indent=2)[:3000])
    print("\n...\n")
    
    # Guardar full response
    with open('/tmp/espn_response.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("✅ Respuesta completa guardada en /tmp/espn_response.json")
else:
    print(f"Error: {response.status_code}")
    print(response.text[:500])
