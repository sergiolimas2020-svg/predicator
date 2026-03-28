#!/bin/bash

# Script para iniciar servidor web
cd /Users/sergiolimas/Desktop/PREDICATOR
source .venv/bin/activate

echo "🚀 Iniciando servidor en http://localhost:8000"
echo "Presiona Ctrl+C para detener"
echo ""

python -m http.server 8000 --directory .
