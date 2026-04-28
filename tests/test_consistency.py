"""
Test de paridad — Python (prob_futbol/prob_futbol_3way) vs JavaScript
(Calculator.predictWinner/predictWinner3Way).

Ejecuta los mismos casos en ambos lenguajes y verifica que las
probabilidades coincidan dentro de TOLERANCE_PCT.

Uso:
    pytest tests/test_consistency.py -v
    # o desde la raíz:
    python3 -m pytest tests/test_consistency.py

Requisitos:
    - Python 3.11+
    - Node 20+ (usado vía subprocess)
    - pytest

CI: este test corre en .github/workflows/prediktor-daily.yml después de
instalar dependencias y antes de generate_predictions.py. Si la paridad
se rompe (alguien edita calculator.js o prob_futbol() y diverge), el
workflow falla inmediatamente y notifica al admin.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Permitir importar generate_predictions desde scrapers/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))

from generate_predictions import prob_futbol, prob_futbol_3way  # noqa: E402


# ── Configuración ──────────────────────────────────────────────
TOLERANCE_PCT       = 0.1   # Diferencia máxima permitida (%)
NODE_TIMEOUT_SEC    = 5     # Timeout por caso
TEST_CASES_PATH     = Path(__file__).parent / "test_cases.json"
JS_RUNNER_PATH      = Path(__file__).parent / "run_calculator.js"
# Determinismo: el algoritmo es puramente determinista — no hay random ni I/O.


# ── Utilidades ─────────────────────────────────────────────────

def _node_available() -> bool:
    """Detecta si Node.js está instalado en el sistema."""
    return shutil.which("node") is not None


def _load_cases() -> list:
    """Carga los casos de prueba compartidos con el wrapper Node."""
    with TEST_CASES_PATH.open(encoding="utf-8") as f:
        return json.load(f)["cases"]


def _run_node(case: dict) -> dict:
    """
    Invoca el wrapper Node con un caso y captura su salida JSON.
    Retorna {predictWinner: {...}, predictWinner3Way: {...}}.
    """
    payload = json.dumps({"home": case["home"], "away": case["away"]})
    proc = subprocess.run(
        ["node", str(JS_RUNNER_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=NODE_TIMEOUT_SEC,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Node fallo (rc={proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout)


# ── Casos cargados a nivel módulo (uno por test) ───────────────
CASES = _load_cases()


# ══════════════════════════════════════════════════════════════
#  TESTS
# ══════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _node_available(),
                    reason="Node no instalado — ver SECRETS.md o tests/README")
@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_predictWinner_python_vs_js(case):
    """
    Paridad Python prob_futbol(hd, ad) vs JS Calculator.predictWinner().

    Compara homeWinProb (hp) y awayWinProb (ap). Diferencia permitida:
    TOLERANCE_PCT (0.1%). Si esto falla, alguien rompió la paridad
    entre los modelos — revisar generate_predictions.py o calculator.js.
    """
    # Python: prob_futbol retorna (hp, ap) en porcentajes
    py_hp, py_ap = prob_futbol(case["home"], case["away"])

    # Node: predictWinner retorna {homeWinProb: "X.X", awayWinProb: "Y.Y"} (strings)
    js_result = _run_node(case)
    js_hp = float(js_result["predictWinner"]["homeWinProb"])
    js_ap = float(js_result["predictWinner"]["awayWinProb"])

    # Comparación
    assert abs(py_hp - js_hp) <= TOLERANCE_PCT, (
        f"hp diverge en '{case['name']}': "
        f"Python={py_hp}, JS={js_hp}, diff={abs(py_hp - js_hp):.3f}"
    )
    assert abs(py_ap - js_ap) <= TOLERANCE_PCT, (
        f"ap diverge en '{case['name']}': "
        f"Python={py_ap}, JS={js_ap}, diff={abs(py_ap - js_ap):.3f}"
    )


@pytest.mark.skipif(not _node_available(),
                    reason="Node no instalado — ver SECRETS.md o tests/README")
@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_predictWinner3Way_python_vs_js(case):
    """
    Paridad Python prob_futbol_3way(hd, ad) vs JS predictWinner3Way().

    Compara win/draw/lose. Diferencia permitida: TOLERANCE_PCT.
    Suma debe dar 100 ± 0.2% (acumulación de redondeos en 3 valores).
    """
    py_win, py_draw, py_lose = prob_futbol_3way(case["home"], case["away"])

    js_result = _run_node(case)["predictWinner3Way"]
    js_win, js_draw, js_lose = js_result["win"], js_result["draw"], js_result["lose"]

    assert abs(py_win - js_win) <= TOLERANCE_PCT, (
        f"win diverge en '{case['name']}': PY={py_win}, JS={js_win}"
    )
    assert abs(py_draw - js_draw) <= TOLERANCE_PCT, (
        f"draw diverge en '{case['name']}': PY={py_draw}, JS={js_draw}"
    )
    assert abs(py_lose - js_lose) <= TOLERANCE_PCT, (
        f"lose diverge en '{case['name']}': PY={py_lose}, JS={js_lose}"
    )

    # Suma debe estar cerca de 100% (acumula errores de redondeo de 3 valores)
    assert abs(sum([py_win, py_draw, py_lose]) - 100) <= 0.2, \
        f"Python suma != 100: {py_win + py_draw + py_lose}"
    assert abs(sum([js_win, js_draw, js_lose]) - 100) <= 0.2, \
        f"JS suma != 100: {js_win + js_draw + js_lose}"


# ── Test sin Node (sanity check) ───────────────────────────────

@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_python_alone_does_not_crash(case):
    """
    Sanity check: prob_futbol() y prob_futbol_3way() no crashean
    con ningún caso (incluso edge cases como partidos=0).
    Corre siempre, no requiere Node.
    """
    hp, ap = prob_futbol(case["home"], case["away"])
    assert 0 <= hp <= 100
    assert 0 <= ap <= 100
    assert abs(hp + ap - 100) <= 0.2

    win, draw, lose = prob_futbol_3way(case["home"], case["away"])
    assert all(0 <= v <= 100 for v in (win, draw, lose))
    assert abs(win + draw + lose - 100) <= 0.2
