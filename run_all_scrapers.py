#!/usr/bin/env python3
"""
Script para ejecutar todos los scrapers automáticamente
"""

import os
import subprocess
import sys
from pathlib import Path

def run_all_scrapers():
    # Obtener la ruta de la carpeta scrapers
    scrapers_dir = Path(__file__).parent / "scrapers"
    
    # Verificar que la carpeta existe
    if not scrapers_dir.exists():
        print(f"❌ La carpeta '{scrapers_dir}' no existe")
        sys.exit(1)
    
    # Obtener todos los archivos .py (excluyendo __pycache__ y similar)
    py_files = sorted([f for f in scrapers_dir.glob("*.py") if f.is_file()])
    
    if not py_files:
        print(f"❌ No se encontraron archivos .py en {scrapers_dir}")
        sys.exit(1)
    
    print(f"\n🚀 Ejecutando {len(py_files)} scrapers...\n")
    print("=" * 60)
    
    executed = 0
    failed = 0
    
    for script in py_files:
        script_name = script.name
        print(f"\n▶️  Ejecutando: {script_name}")
        print("-" * 60)
        
        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=scrapers_dir,
                capture_output=False,  # Mostrar la salida en tiempo real
                timeout=300  # Timeout de 5 minutos por script
            )
            
            if result.returncode == 0:
                print(f"✅ {script_name} completado exitosamente")
                executed += 1
            else:
                print(f"❌ {script_name} falló con código {result.returncode}")
                failed += 1
                
        except subprocess.TimeoutExpired:
            print(f"⏱️  {script_name} excedió el tiempo máximo (5 min)")
            failed += 1
        except Exception as e:
            print(f"❌ Error al ejecutar {script_name}: {str(e)}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"\n📊 Resumen:")
    print(f"   ✅ Exitosos: {executed}")
    print(f"   ❌ Fallidos: {failed}")
    print(f"   📦 Total: {len(py_files)}\n")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_scrapers()
    sys.exit(0 if success else 1)

# Sincronizar JSONs a static/ raiz
import shutil, glob
for f in glob.glob('scrapers/static/*.json'):
    shutil.copy(f, 'static/')
print('✅ JSONs sincronizados a static/')
