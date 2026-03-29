#!/usr/bin/env python3
import os, sys, json, shutil, subprocess
from pathlib import Path
from datetime import datetime

ROOT       = Path(__file__).parent
SCRAPERS   = ROOT / "scrapers"
STATIC     = ROOT / "static"
BACKUP_DIR = ROOT / "static" / "_backup"
BACKUP_DIR.mkdir(exist_ok=True)

SCRAPERS_LIST = [
    ("colombia.py",   "static/colombia_stats.json",                       10),
    ("italia.py",     "scrapers/static/italy_stats.json",                 15),
    ("premier.py",    "scrapers/static/england_stats.json",               15),
    ("españa.py",     "scrapers/static/spain_stats.json",                 15),
    ("francia.py",    "scrapers/static/france_stats.json",                15),
    ("bundesliga.py", "scrapers/static/germany_stats.json",               15),
    ("turquia.py",    "scrapers/static/turkey_stats.json",                15),
    ("champions.py",  "scrapers/static/uefa_champions_league_stats.json", 10),
    ("argentina.py",  "scrapers/static/argentina_stats.json",             15),
    ("brazil.py",     "scrapers/static/brazil_stats.json",                15),
    ("nba_scraper.py","static/nba_stats.json",                             5),
]

def validate_json(json_path, min_teams):
    p = ROOT / json_path
    if not p.exists(): return False, "No existe"
    try: data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e: return False, f"JSON invalido: {e}"
    teams = [k for k in data if not k.startswith("_")]
    if len(teams) < min_teams: return False, f"Solo {len(teams)} equipos (min {min_teams})"
    return True, f"{len(teams)} equipos OK"

def backup(json_path):
    p = ROOT / json_path
    if p.exists():
        name = p.stem + "_" + datetime.now().strftime("%Y%m%d") + ".json"
        shutil.copy(p, BACKUP_DIR / name)

def run_scraper(script, json_output, min_teams):
    script_path = SCRAPERS / script
    if not script_path.exists(): return False, "Script no encontrado"
    backup(json_output)
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return False, f"Codigo {result.returncode}: {result.stderr[:150]}"
    except subprocess.TimeoutExpired: return False, "Timeout 2min"
    except Exception as e: return False, str(e)
    ok, msg = validate_json(json_output, min_teams)
    if not ok:
        bk = BACKUP_DIR / (Path(json_output).stem + "_" + datetime.now().strftime("%Y%m%d") + ".json")
        if bk.exists(): shutil.copy(bk, ROOT / json_output)
        return False, f"{msg} — backup restaurado"
    return True, msg

def sync_to_static():
    src = SCRAPERS / "static"
    if not src.exists(): return
    n = 0
    for f in src.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if len([k for k in data if not k.startswith("_")]) >= 5:
                shutil.copy(f, STATIC / f.name); n += 1
        except: pass
    print(f"   {n} JSONs sincronizados a static/")

def main():
    print("\n" + "="*60)
    print("PREDIKTOR — Actualizacion de estadisticas")
    print(datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("="*60 + "\n")
    ok = fail = 0
    bad = []
    for script, json_output, min_teams in SCRAPERS_LIST:
        print(f"Ejecutando: {script}")
        success, msg = run_scraper(script, json_output, min_teams)
        print(f"  {'OK' if success else 'FALLO'}: {msg}\n")
        if success: ok += 1
        else: fail += 1; bad.append((script, msg))
    print("Sincronizando JSONs...")
    sync_to_static()
    print(f"\nResumen: {ok} exitosos, {fail} fallidos de {len(SCRAPERS_LIST)}")
    if bad:
        for s, m in bad: print(f"  - {s}: {m}")
    return fail == 0

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
