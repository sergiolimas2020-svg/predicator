#!/usr/bin/env python3
"""
Obtener datos de Dimayor.com.co directamente
"""

import requests
import json
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
}

print("Intentando sitio oficial Dimayor...\n")

try:
    url = "https://www.dimayor.com.co/estadisticas/"
    
    print(f"Accediendo a: {url}")
    response = requests.get(url, headers=headers, timeout=10, verify=False)
    
    print(f"Status: {response.status_code}\n")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Buscar tablas
        tables = soup.find_all('table')
        print(f"Encontradas {len(tables)} tablas\n")
        
        if tables:
            print("Primeras 5 filas de la primera tabla:\n")
            table = tables[0]
            rows = table.find_all('tr')
            
            for idx, row in enumerate(rows[:6]):
                cols = row.find_all(['td', 'th'])
                texts = [col.get_text(strip=True)[:20] for col in cols[:9]]
                print(f"Fila {idx}: {texts}")
        
        # Guardar HTML
        with open('/tmp/dimayor.html', 'w') as f:
            f.write(response.text[:5000])
        
        print("\n✅ HTML guardado en /tmp/dimayor.html")

except Exception as e:
    print(f"❌ Error: {str(e)}")
