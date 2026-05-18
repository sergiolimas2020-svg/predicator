"""
Entrena el calibrador Platt scaling del motor PREDIKTOR.

Lee static/predictions_log.json, extrae los pares (probabilidad del modelo,
resultado real) de los picks verificados, ajusta los parámetros A y B de
Platt scaling y los guarda en static/calibrator.json.

El motor (generate_predictions.py) carga ese JSON al arrancar y calibra
todas las probabilidades. Si el archivo no existe, el motor opera sin
calibrar (degradación segura).

Uso:  python scripts/train_calibrator.py

Se ejecuta en el cron ANTES de generate_predictions.py para que el
calibrador se mantenga fresco a medida que crece el log.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# El módulo del motor expone train_and_save_calibrator().
from scrapers.generate_predictions import train_and_save_calibrator


def main():
    print("── Entrenando calibrador Platt scaling ──")
    result = train_and_save_calibrator(
        log_path=str(ROOT / "static" / "predictions_log.json"),
        out_path=str(ROOT / "static" / "calibrator.json"),
    )
    if result is None:
        print("Calibrador NO generado (datos insuficientes o sin log).")
        print("El motor operará sin calibración hasta acumular más picks.")
        # Exit 0: no es un fallo crítico — el motor degrada con seguridad.
        sys.exit(0)
    print(f"Calibrador guardado en static/calibrator.json")
    print(f"  A={result['A']}  B={result['B']}  n={result['n_samples']}")
    print(f"  Brier in-sample: {result['brier_in_sample_before']} "
          f"→ {result['brier_in_sample_after']}")


if __name__ == "__main__":
    main()
