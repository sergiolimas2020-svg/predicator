#!/usr/bin/env python3
import subprocess, sys, json, shutil, logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)
ROOT = Path(__file__).parent.resolve()
BACKUP_DIR = ROOT / "static" / "_backup"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

SCRAPERS_CONFIG = [
    ("colombia.py",   "static/colombia_stats.json",           10, 120),
    ("italia.py",     "scrapers/static/italy_stats.json",     15, 120),
    ("premier.py",    "scrapers/static/england_stats.json",   15, 120),
    ("espana.py",     "scrapers/static/spain_stats.json",     15, 120),
    ("francia.py",    "scrapers/static/france_stats.json",    15, 120),
    ("bundesliga.py", "scrapers/static/germany_stats.json",   15, 120),
    ("turquia.py",    "scrapers/static/turkey_stats.json",    15, 120),
    ("argentina.py",  "scrapers/static/argentina_stats.json", 15, 120),
    ("brazil.py",     "scrapers/static/brazil_stats.json",    15, 120),
    ("nba_scraper.py","static/nba_stats.json",                 5, 300),
]

def validate_json(path):
    if not path.exists(): return False
    try:
        data = json.load(open(path, encoding="utf-8"))
        teams = [k for k in data if not k.startswith("_")]
        if not teams: return False
        logger.info("  OK %d equipos - %s", len(teams), path.name)
        return True
    except: return False

def backup_file(path):
    if path.exists(): shutil.copy2(path, BACKUP_DIR / path.name)

def restore_backup(path):
    b = BACKUP_DIR / path.name
    if b.exists(): shutil.copy2(b, path)

def run_scraper(script, output_rel, retries, timeout):
    sp = ROOT / "scrapers" / script
    op = ROOT / output_rel
    if not sp.exists():
        logger.error("No existe: %s", sp)
        return False
    backup_file(op)
    for i in range(1, retries + 1):
        logger.info("Intento %d/%d - %s", i, retries, script)
        try:
            r = subprocess.run([sys.executable, str(sp)], cwd=str(ROOT),
                               timeout=timeout, capture_output=True, text=True)
            if r.returncode == 0 and validate_json(op):
                logger.info("EXITO: %s", script)
                return True
            if r.stderr: logger.warning(r.stderr[-200:])
        except subprocess.TimeoutExpired:
            logger.warning("Timeout en intento %d", i)
        except Exception as e:
            logger.warning("Error: %s", e)
    logger.error("FALLO: %s", script)
    restore_backup(op)
    return False

def sync():
    src = ROOT / "scrapers" / "static"
    dst = ROOT / "static"
    if not src.exists(): return
    n = 0
    for f in src.glob("*.json"):
        shutil.copy2(f, dst / f.name)
        n += 1
    logger.info("Sync: %d archivos copiados a static/", n)

def main():
    logger.info("PREDIKTOR - inicio %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    res = {}
    for s, o, r, t in SCRAPERS_CONFIG:
        logger.info("--- %s", s)
        res[s] = run_scraper(s, o, r, t)
    sync()
    ok = sum(1 for v in res.values() if v)
    logger.info("RESUMEN: %d/%d OK", ok, len(res))
    for s, v in res.items():
        logger.info("  [%s] %s", "OK" if v else "FALLO", s)

if __name__ == "__main__":
    main()
