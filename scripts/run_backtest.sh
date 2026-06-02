#!/bin/bash
# ============================================================
# PREDIKTOR — Ejecutar Backtesting de Poisson + Elo
# ============================================================

set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO="$( cd "$SCRIPT_DIR/.." && pwd )"
PYTHON="$REPO/.venv/bin/python3"

cd "$REPO"

# Cargar API key desde .env si existe
if [ -f "$REPO/.env" ]; then
    export $(grep -v '^#' "$REPO/.env" | xargs)
fi

if [ -z "$API_FOOTBALL_KEY" ]; then
    echo "⚠️  ADVERTENCIA: API_FOOTBALL_KEY no está configurada."
    echo "Por favor, introduce tu API-Football key para correr el backtest online:"
    read -r -p "API Key: " USER_KEY
    if [ -n "$USER_KEY" ]; then
        export API_FOOTBALL_KEY="$USER_KEY"
    else
        echo "❌ Error: API key requerida para el backtesting."
        exit 1
    fi
fi

echo "🚀 1. Iniciando simulación de Backtest Point-In-Time con cuotas dinámicas..."
$PYTHON "$REPO/scripts/backtest_poisson_pit.py"

echo ""
echo "🚀 2. Iniciando análisis empírico sobre el log real de producción..."
$PYTHON "$REPO/scripts/backtest_log_real.py"

echo ""
echo "======================================================================"
echo "📊 REPORTES GENERADOS CON ÉXITO:"
echo "======================================================================"
echo "1. Backtest Point-In-Time (Ligas): static/_backtest_poisson_report.md"
echo "2. Rendimiento Real en Vivo (Log): static/_backtest_log_real_report.md"
echo "======================================================================"
echo "Puedes abrir estos archivos en formato markdown para ver los detalles."
