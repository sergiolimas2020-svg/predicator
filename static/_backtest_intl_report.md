# Backtest internacional (point-in-time) — modelo selecciones
- Partidos en el pool: **1911** (warmup descartado: 573)
- Muestras evaluadas: **1160**
- **Hit-rate 1X2** (argmax acierta L/E/V): **56.7%**
- **Hit-rate DNB** (sin empates, n=871): **75.2%**
- Baseline 'gana mayor Elo' (DNB): 75.7%
- **Brier** multiclase: **0.6066** (menor = mejor; azar 3-way ≈ 0.667)
- **Log-loss**: **1.0887** (azar 3-way ≈ 1.099)
## Calibración del favorito (prob predicha vs acierto real)
| Bucket prob | n | acierto |
|---|---|---|
| 30-40% | 68 | 38.2% |
| 40-50% | 160 | 43.8% |
| 50-60% | 153 | 43.8% |
| 60-70% | 157 | 52.9% |
| 70-80% | 139 | 59.0% |
| 80-90% | 176 | 60.2% |
| 90-100% | 307 | 73.0% |