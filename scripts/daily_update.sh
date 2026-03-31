#!/bin/bash
# ============================================================
# PREDIKTOR — Actualización diaria automática
# Corre scrapers → genera predicciones → hace push a GitHub
# Vercel redespliega automáticamente tras el push
# ============================================================

set -e

REPO="/Users/sergiolimas/Desktop/PREDICATOR"
LOG="$REPO/scripts/daily_update.log"
PYTHON="python3"

cd "$REPO"

echo "" >> "$LOG"
echo "============================================" >> "$LOG"
echo "  PREDIKTOR daily update — $(date '+%Y-%m-%d %H:%M')" >> "$LOG"
echo "============================================" >> "$LOG"

# ── 1. Actualizar stats de todas las ligas ──
echo "[1/3] Actualizando estadísticas..." >> "$LOG"

run_scraper() {
    local name="$1"
    local script="$2"
    echo "  → $name..." >> "$LOG"
    $PYTHON "$script" >> "$LOG" 2>&1 && echo "    OK" >> "$LOG" || echo "    WARN: $name falló, continuando" >> "$LOG"
}

run_scraper "Colombia"      "scrapers/colombia.py"
run_scraper "Argentina"     "scrapers/argentina.py"
run_scraper "Premier"       "scrapers/premier.py"
run_scraper "La Liga"       "scrapers/españa.py"
run_scraper "Serie A"       "scrapers/italia.py"
run_scraper "Bundesliga"    "scrapers/bundesliga.py"
run_scraper "Ligue 1"       "scrapers/francia.py"
run_scraper "Brasil"        "scrapers/brazil.py"
run_scraper "Champions"     "scrapers/champions.py"

# NBA scraper es lento (~2 min) — corre en paralelo
echo "  → NBA (background)..." >> "$LOG"
$PYTHON scrapers/nba_scraper.py >> "$LOG" 2>&1 &
NBA_PID=$!

# Esperar NBA (máximo 3 min)
wait $NBA_PID && echo "    NBA OK" >> "$LOG" || echo "    NBA WARN: usará stats anteriores" >> "$LOG"

# ── 2. Generar predicciones del día ──
echo "[2/3] Generando predicciones..." >> "$LOG"
$PYTHON scrapers/generate_predictions.py >> "$LOG" 2>&1
echo "  OK" >> "$LOG"

# ── 3. Push a GitHub → Vercel redespliega ──
echo "[3/3] Publicando en GitHub..." >> "$LOG"
git add -A >> "$LOG" 2>&1
git diff --cached --quiet && echo "  Sin cambios nuevos" >> "$LOG" || {
    git commit -m "chore: actualización automática $(date '+%Y-%m-%d')" >> "$LOG" 2>&1
    git push >> "$LOG" 2>&1
    echo "  Push OK — Vercel redesplegando..." >> "$LOG"
}

echo "✅ Completado — $(date '+%H:%M:%S')" >> "$LOG"
