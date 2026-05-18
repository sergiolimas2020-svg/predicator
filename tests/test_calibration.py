"""
Tests del calibrador Platt scaling (motor v1.1).

Verifican que fit_platt_calibrator y platt_probability se comporten
correctamente. NO dependen de archivos del repo ni de red.
"""
from __future__ import annotations
import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers import generate_predictions as gp


class TestPlattProbability(unittest.TestCase):
    def test_identity_when_no_params(self):
        # Sin A/B → devuelve f sin tocar
        self.assertEqual(gp.platt_probability(0.6, None, None), 0.6)

    def test_in_unit_range(self):
        for f in (0.0, 0.15, 0.5, 0.85, 1.0):
            p = gp.platt_probability(f, -0.6, 0.3)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)

    def test_monotonic_increasing(self):
        # Con A negativo, mayor f → mayor probabilidad calibrada
        A, B = -1.5, 0.5
        probs = [gp.platt_probability(f / 10, A, B) for f in range(11)]
        for i in range(1, len(probs)):
            self.assertGreaterEqual(probs[i], probs[i - 1])

    def test_no_overflow_extremes(self):
        # No debe lanzar excepción con z muy grande/pequeño
        self.assertGreaterEqual(gp.platt_probability(1.0, 50.0, 50.0), 0.0)
        self.assertLessEqual(gp.platt_probability(0.0, -50.0, -50.0), 1.0)


class TestFitPlattCalibrator(unittest.TestCase):
    def test_none_when_insufficient_samples(self):
        pairs = [(0.6, 1), (0.4, 0)]  # menos que MIN_CALIBRATION_SAMPLES
        A, B = gp.fit_platt_calibrator(pairs)
        self.assertIsNone(A)
        self.assertIsNone(B)

    def test_none_when_single_class(self):
        pairs = [(0.6, 1)] * 30  # todos aciertos → sin clase negativa
        A, B = gp.fit_platt_calibrator(pairs)
        self.assertIsNone(A)

    def test_reduces_brier_on_overconfident_data(self):
        # Modelo sobreconfiado: declara 0.85 pero solo acierta ~55%.
        random.seed(42)
        pairs = []
        for _ in range(200):
            y = 1 if random.random() < 0.55 else 0
            pairs.append((0.85, y))  # f fijo y alto, realidad 55%
        for _ in range(200):
            y = 1 if random.random() < 0.35 else 0
            pairs.append((0.65, y))  # declara 0.65, realidad 35%

        A, B = gp.fit_platt_calibrator(pairs)
        self.assertIsNotNone(A)

        def brier(get_p):
            return sum((get_p(f) - y) ** 2 for f, y in pairs) / len(pairs)

        brier_raw = brier(lambda f: f)
        brier_cal = brier(lambda f: gp.platt_probability(f, A, B))
        # La calibración debe mejorar (reducir) el Brier
        self.assertLess(brier_cal, brier_raw)

    def test_calibrated_probs_near_real_rate(self):
        # Si f=0.80 pero la tasa real es 0.50, el calibrado debe acercarse a 0.50
        random.seed(7)
        pairs = [(0.80, 1 if random.random() < 0.50 else 0) for _ in range(300)]
        A, B = gp.fit_platt_calibrator(pairs)
        self.assertIsNotNone(A)
        cal = gp.platt_probability(0.80, A, B)
        self.assertAlmostEqual(cal, 0.50, delta=0.10)


if __name__ == "__main__":
    unittest.main()
