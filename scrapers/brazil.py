#!/usr/bin/env python3
"""
Scraper de estadísticas del Brasileirão.

ANTES: este archivo era un script viejo que solo extraía goles y posiciones y
escribía `"corners": {}` para todos los equipos (metadata mínima, sin
`fuente_datos` ni `equipos_extraidos`). soccerstats SÍ provee córners para
Brasil (league=brazil&tid=cr, ~20 equipos), así que el dato existía pero nunca
se pedía.

AHORA: reutiliza el scraper canónico de soccerstats (scrapers/premier.py), que
extrae córners + goles + posiciones y escribe el formato unificado
(con `fuente_datos`, `equipos_extraidos` y `corners_disponibles`). Esto corrige
los córners vacíos y unifica el formato con el resto de ligas.

Uso:  python3 scrapers/brazil.py
"""
import os
import sys

# Permitir `import premier` al ejecutar como `python3 scrapers/brazil.py`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from premier import main  # scraper canónico de soccerstats (genérico por liga)

if __name__ == "__main__":
    main("brazil")
