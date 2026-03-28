#!/usr/bin/env python3
"""
Intento con requests directo a FlashScore API
"""

import requests
import json

def get_from_flashscore_api():
    """Intenta obtener datos de FlashScore mediante API"""
    
    print("📡 Intentando acceso a FlashScore...\n")
    
    # Headers más realistas
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'es-CO,es;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }
    
    try:
        url = "https://www.flashscore.co/clasificacion/tYhlmBUI/I7rbp1up/#/I7rbp1up/clasificacion/general/"
        
        print(f"  Accediendo a: {url}")
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar tablas
            tables = soup.find_all('table')
            print(f"  Encontradas {len(tables)} tablas")
            
            # Buscar datos en cualquier elemento
            standings = []
            
            # Intenta buscar filas con estructura común
            for row in soup.find_all('tr'):
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 8:
                    try:
                        texts = [col.get_text(strip=True) for col in cols]
                        print(f"    Fila: {texts[:5]}")
                    except:
                        pass
            
            return response.text
        else:
            print(f"  Error: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")
        return None

# Resultado
if __name__ == '__main__':
    html = get_from_flashscore_api()
    if html:
        print("\n✅ Conexión exitosa")
        print(f"📄 Longitud HTML: {len(html)} caracteres")
    else:
        print("\n❌ No se pudo conectar")
