#!/bin/bash
# ============================================================
# PREDIKTOR — Ejecutar Backtesting de Poisson + Elo
# ============================================================

set -e
REPO="/Users/sergiolimas/PROYECTO_PREDICATOR"
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

echo "🚀 Iniciando simulación de Backtest Point-In-Time (esto puede tomar ~30s)..."
$PYTHON "$REPO/scripts/backtest_poisson_pit.py"

echo ""
echo "📊 Reporte generado con éxito en: static/_backtest_poisson_report.md"
echo "Para leer el reporte completo en formato markdown, puedes abrir el archivo."
