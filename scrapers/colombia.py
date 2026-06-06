#!/usr/bin/env python3
"""
Scraper de estadísticas de la Liga BetPlay (Colombia).

Usa el scraper canónico de soccerstats (scrapers/premier.py) para goles y
posiciones. IMPORTANTE: soccerstats NO publica tabla de CÓRNERS para Colombia
(league=colombia&tid=cr devuelve 0 equipos), así que este paso deja
`corners_disponibles: false` y registra un WARNING claro — NUNCA guarda `{}` en
silencio. Los córners reales se obtienen aparte con scrapers/colombia_corners.py
(fuente RapidAPI, liga 274), que se ejecuta DESPUÉS y los fusiona en este JSON.

Uso:  python3 scrapers/colombia.py  &&  python3 scrapers/colombia_corners.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from premier import main  # scraper canónico de soccerstats (genérico por liga)

if __name__ == "__main__":
    main("colombia")
