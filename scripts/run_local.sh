#!/usr/bin/env bash
# PREDIKTOR — Ejecutar el pipeline diario localmente.
# Reproduce los mismos pasos del workflow de GitHub Actions.
# Útil para debuggear sin esperar al cron.
#
# Uso:
#   ./scripts/run_local.sh                   # corrida normal
#   ./scripts/run_local.sh --skip-telegram   # no publicar en Telegram
#   ./scripts/run_local.sh --dry-run         # no ejecuta nada, solo lista pasos
#
# Requisitos:
#   - .env con secrets (ODDS_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID)
#   - python3 instalado
#   - Dependencias instaladas: pip install -r requirements.txt

set -euo pipefail

# ── Colores ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RESET='\033[0m'

# ── Flags ──
SKIP_TELEGRAM=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --skip-telegram) SKIP_TELEGRAM=true ;;
    --dry-run)       DRY_RUN=true ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
  esac
done

# ── Posicionarse en raíz del proyecto ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo -e "${BLUE}════════════════════════════════════════════════════════════${RESET}"
echo -e "${BLUE}  PREDIKTOR — Pipeline local${RESET}"
echo -e "${BLUE}  Directorio: $PROJECT_ROOT${RESET}"
[[ "$DRY_RUN" == "true"     ]] && echo -e "${YELLOW}  Modo: DRY RUN (no ejecuta)${RESET}"
[[ "$SKIP_TELEGRAM" == "true" ]] && echo -e "${YELLOW}  Telegram: DESHABILITADO${RESET}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${RESET}"

# ── Cargar .env si existe ──
if [[ -f ".env" ]]; then
  echo -e "${GREEN}✓${RESET} Cargando .env"
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
else
  echo -e "${YELLOW}⚠${RESET}  No existe .env — usando solo variables de entorno actuales"
fi

# ── Helper: ejecutar paso con manejo de error ──
step() {
  local name="$1"
  local cmd="$2"
  local critical="${3:-false}"

  echo ""
  echo -e "${BLUE}━━ $name ━━${RESET}"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}[DRY] $cmd${RESET}"
    return 0
  fi

  if eval "$cmd"; then
    echo -e "${GREEN}✓ $name OK${RESET}"
    return 0
  else
    echo -e "${RED}✗ $name FALLÓ${RESET}"
    if [[ "$critical" == "true" ]]; then
      echo -e "${RED}━━ Step crítico falló — abortando ━━${RESET}"
      exit 1
    fi
    return 1
  fi
}

# ── Step 0: Verificar secrets ──
step "0/7 Verificar secrets" "python3 scripts/verify_secrets.py" "true"

# ── Step 1: Validar imports críticos ──
step "1/7 Validar imports Python" \
  "python3 -c 'import requests, bs4, lxml; import nba_api.stats.endpoints; import telegram; print(\"Imports OK\")'" \
  "true"

# ── Step 2: Registrar resultados de ayer ──
step "2/7 Registrar resultados de ayer" \
  "python3 scrapers/update_results.py" \
  "false"

# ── Step 3: Fetch odds (CRÍTICO) ──
step "3/7 Fetch cuotas bookmakers" \
  "python3 scrapers/fetch_odds.py" \
  "true"

# ── Step 4: Stats por liga (no crítico — si falla una, las otras siguen) ──
echo ""
echo -e "${BLUE}━━ 4/7 Actualizar stats por liga ━━${RESET}"
declare -a SCRAPERS=(
  "scrapers/colombia.py:Colombia"
  "scrapers/argentina.py:Argentina"
  "scrapers/premier.py:Premier"
  "scrapers/españa.py:La Liga"
  "scrapers/italia.py:Serie A"
  "scrapers/bundesliga.py:Bundesliga"
  "scrapers/francia.py:Ligue 1"
  "scrapers/brazil.py:Brasileirao"
  "scrapers/champions.py:Champions"
  "scrapers/nba_scraper.py:NBA"
)
for entry in "${SCRAPERS[@]}"; do
  script="${entry%%:*}"
  name="${entry##*:}"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}  [DRY] python3 $script${RESET}"
    continue
  fi
  if python3 "$script" >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${RESET} $name"
  else
    echo -e "  ${YELLOW}⚠${RESET}  $name falló (no crítico)"
  fi
done

# ── Step 5: Generar predicciones (CRÍTICO) ──
step "5/7 Generar predicciones del día" \
  "python3 scrapers/generate_predictions.py --force" \
  "true"

# ── Step 6: Validar que se generó el JSON del día ──
echo ""
echo -e "${BLUE}━━ 6/7 Validar JSON generado ━━${RESET}"
TODAY=$(date "+%Y-%m-%d")
if [[ "$DRY_RUN" == "true" ]]; then
  echo -e "${YELLOW}  [DRY] verificar daily_picks.json fecha=$TODAY${RESET}"
else
  JSON_DATE=$(python3 -c "import json; print(json.load(open('static/predictions/daily_picks.json'))['date'])" 2>/dev/null || echo "ERROR")
  if [[ "$JSON_DATE" == "$TODAY" ]]; then
    echo -e "${GREEN}✓${RESET} daily_picks.json tiene fecha de hoy: $JSON_DATE"
  else
    echo -e "${RED}✗${RESET} daily_picks.json fecha=$JSON_DATE, esperaba $TODAY"
    exit 1
  fi
fi

# ── Step 7: Publicar Telegram ──
if [[ "$SKIP_TELEGRAM" == "true" ]]; then
  echo ""
  echo -e "${YELLOW}━━ 7/7 Telegram OMITIDO (--skip-telegram) ━━${RESET}"
else
  step "7/7 Publicar en Telegram" \
    "python3 -m bot.publish --force" \
    "false"
fi

# ── Resumen ──
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}  Pipeline completado${RESET}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${RESET}"

if [[ "$DRY_RUN" == "false" ]]; then
  PICKS=$(python3 -c "
import json
d = json.load(open('static/predictions/daily_picks.json'))
n = (1 if d.get('pick_dia') else 0) + (1 if d.get('pick_gratuito') else 0) + len(d.get('picks_suscripcion', []))
print(n)
" 2>/dev/null || echo "?")
  echo -e "  Picks generados hoy: ${BLUE}$PICKS${RESET}"
  echo -e "  Para subir a producción: ${BLUE}git add -A && git commit -m '...' && git push${RESET}"
fi
