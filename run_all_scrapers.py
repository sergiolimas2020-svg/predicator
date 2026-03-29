#!/usr/bin/env python3
"""
run_all_scrapers.py — Orquestador maestro PREDIKTOR
Ejecuta todos los scrapers en orden, con backup, validación JSON y sincronización.
"""

import subprocess
import sys
import os
import json
import shutil
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.resolve()
BACKUP_DIR = ROOT / "static" / "_backup"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

SCRAPERS_CONFIG = [
    ("colombia.py",    "static/colombia_stats.json",           10, 120),
    ("italia.py",      "scrapers/static/italy_stats.json",     15, 120),
    ("premier.py",     "scrapers/static/england_stats.json",   15, 120),
    ("españa.py",      "scrapers/static/spain_stats.json"


