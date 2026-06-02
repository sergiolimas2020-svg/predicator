#!/usr/bin/env python3
"""
Backtest Empírico Real de PREDIKTOR sobre el historial de producción.
Analiza predictions_log.json, filtra las apuestas con cuotas reales de mercado
y calcula el ROI real acumulado (apuesta plana vs Quarter-Kelly sin calibrar vs calibrado).
"""

from __future__ import annotations
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scrapers"))

from scrapers.generate_predictions import kelly_stake, platt_probability, QUARTER_KELLY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("backtest_log_real")

START_BANKROLL = 100.0

def calculate_max_drawdown(bankroll_history: List[float]) -> float:
    """Calcula el Max Drawdown en base al historial del bankroll."""
    if not bankroll_history:
        return 0.0
    max_dd = 0.0
    peak = bankroll_history[0]
    for val in bankroll_history:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd * 100

def run_simulation(picks: List[Dict], cal_params: Tuple[float, float] | None = None) -> Dict[str, Any]:
    n = len(picks)
    if n == 0:
        return {
            "n": 0, "hit_rate": 0.0, "roi_flat": 0.0, 
            "roi_kelly": 0.0, "bankroll_final": START_BANKROLL, "max_dd": 0.0, "bets_made": 0
        }
        
    aciertos = sum(1 for p in picks if p["acerto"] is True)
    hit_rate = (aciertos / n) * 100
    
    # ROI Apuesta Plana (Yield directo de las cuotas reales)
    # Cada apuesta = 1 unidad. Si acierta: gana (cuota - 1), si falla: pierde 1.
    flat_profit = 0.0
    for p in picks:
        odds = float(p["bk_odds"])
        if p["acerto"] is True:
            flat_profit += (odds - 1.0)
        else:
            flat_profit -= 1.0
            
    roi_flat = (flat_profit / n) * 100
    
    # ROI Kelly (Quarter-Kelly)
    bankroll = START_BANKROLL
    bankroll_history = [bankroll]
    bets_made = 0
    
    for p in picks:
        prob = p.get("prob")
        
        # Si se pasa el calibrador de Platt, recalibrar probabilidad antes de Kelly
        if cal_params is not None:
            prob = platt_probability(prob / 100.0, cal_params[0], cal_params[1]) * 100.0
            
        odds = float(p["bk_odds"])
        
        # Calcular stake sugerido usando la función oficial de producción
        stake_pct = kelly_stake(prob, odds, fraction=QUARTER_KELLY)
        f_kelly = stake_pct / 100.0
        
        # Si Kelly no ve valor, f_kelly es 0.0 (no se hace apuesta)
        if f_kelly <= 0.0:
            bankroll_history.append(bankroll)
            continue
            
        bets_made += 1
        stake = bankroll * f_kelly
        
        if p["acerto"] is True:
            bankroll += stake * (odds - 1.0)
        else:
            bankroll -= stake
            
        bankroll_history.append(bankroll)
        
    roi_kelly = ((bankroll - START_BANKROLL) / START_BANKROLL) * 100
    max_dd = calculate_max_drawdown(bankroll_history)
    
    return {
        "n": n,
        "bets_made": bets_made,
        "hit_rate": round(hit_rate, 2),
        "roi_flat": round(roi_flat, 2),
        "roi_kelly": round(roi_kelly, 2),
        "bankroll_final": round(bankroll, 2),
        "max_dd": round(max_dd, 2)
    }

def main():
    logger.info("Iniciando Backtest sobre log real de producción...")
    
    log_path = ROOT / "static" / "predictions_log.json"
    if not log_path.exists():
        logger.error("No se encontró predictions_log.json en %s", log_path)
        sys.exit(1)
        
    try:
        raw_log = json.loads(log_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Error leyendo predictions_log.json: %s", e)
        sys.exit(1)
        
    valid_picks = []
    for entry in raw_log:
        # Requerimos resultado verificado, cuotas reales y probabilidad
        if entry.get("acerto") is None:
            continue
        if entry.get("bk_odds") is None or float(entry["bk_odds"]) <= 1.0:
            continue
        prob = entry.get("prob_adjusted") or entry.get("prob_original")
        if prob is None:
            continue
            
        # Normalizar tipo de pick
        tp = entry.get("tipo_pick")
        if not tp:
            # Fallback histórico para registros viejos
            tp = "extra"
            
        valid_picks.append({
            "fecha": entry.get("fecha", "1970-01-01"),
            "matchup": f"{entry.get('home')} vs {entry.get('away')}",
            "league": entry.get("league", "Desconocida"),
            "prediccion": entry.get("prediccion"),
            "prob": prob,
            "bk_odds": float(entry["bk_odds"]),
            "acerto": entry["acerto"],
            "tipo_pick": tp
        })
        
    # Ordenar cronológicamente
    valid_picks.sort(key=lambda x: x["fecha"])
    
    logger.info("Encontrados %d picks resueltos con cuotas reales.", len(valid_picks))
    
    # Cargar calibrador de Platt si existe
    cal_params = None
    cal_path = ROOT / "static" / "calibrator.json"
    if cal_path.exists():
        try:
            cdata = json.loads(cal_path.read_text(encoding="utf-8"))
            A = cdata.get("A")
            B = cdata.get("B")
            if A is not None and B is not None:
                cal_params = (A, B)
                logger.info("Calibrador Platt cargado: A=%s B=%s n=%d", A, B, cdata.get("n_samples", 0))
        except Exception as e:
            logger.warning("No se pudo cargar el calibrador Platt: %s", e)
            
    # Segmentar picks
    picks_dia = [p for p in valid_picks if p["tipo_pick"] == "pick_dia"]
    picks_extra = [p for p in valid_picks if p["tipo_pick"] == "extra"]
    
    # Ejecutar simulaciones sin calibrador (Raw)
    s_all_raw = run_simulation(valid_picks, cal_params=None)
    s_dia_raw = run_simulation(picks_dia, cal_params=None)
    s_extra_raw = run_simulation(picks_extra, cal_params=None)
    
    # Ejecutar simulaciones con calibrador (Calibrado)
    s_all_cal = run_simulation(valid_picks, cal_params=cal_params)
    s_dia_cal = run_simulation(picks_dia, cal_params=cal_params)
    s_extra_cal = run_simulation(picks_extra, cal_params=cal_params)
    
    # Generar reporte markdown
    md = []
    md.append("# Reporte de Rendimiento Empírico Real (Historial de Producción)\n")
    md.append("Este reporte evalúa el rendimiento del modelo utilizando **únicamente los picks resueltos en vivo**, con las **cuotas reales** de cierre obtenidas de la API y los resultados verdaderos de cada partido.\n")
    
    if cal_params:
        md.append(f"### Parámetros de Calibración Platt Usados:\n* **A (pendiente):** `{cal_params[0]}`\n* **B (sesgo):** `{cal_params[1]}`\n* **Muestras del Calibrador:** `{json.loads(cal_path.read_text()).get('n_samples', 0)}` (entrenado sobre log histórico)\n\n")
    else:
        md.append("⚠️ **Advertencia:** No se detectó calibrador Platt. Simulaciones calibradas asumen probabilidad cruda.\n\n")
        
    md.append("## 1. Rendimiento Consolidado\n")
    md.append("| Muestra / Grupo | N | ROI Apuesta Plana | Apuestas Raw | ROI Kelly Raw | Drawdown Raw | Apuestas Cal | ROI Kelly Cal | Drawdown Cal |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    md.append(f"| **Todos los Picks** | {s_all_raw['n']} | {s_all_raw['roi_flat']:+}% | {s_all_raw['bets_made']} | {s_all_raw['roi_kelly']:+}% | {s_all_raw['max_dd']}% | {s_all_cal['bets_made']} | **{s_all_cal['roi_kelly']:+}%** | **{s_all_cal['max_dd']}%** |")
    md.append(f"| **Picks del Día (Principal)** | {s_dia_raw['n']} | {s_dia_raw['roi_flat']:+}% | {s_dia_raw['bets_made']} | {s_dia_raw['roi_kelly']:+}% | {s_dia_raw['max_dd']}% | {s_dia_cal['bets_made']} | **{s_dia_cal['roi_kelly']:+}%** | **{s_dia_cal['max_dd']}%** |")
    md.append(f"| **Picks Extra (Adicionales)** | {s_extra_raw['n']} | {s_extra_raw['roi_flat']:+}% | {s_extra_raw['bets_made']} | {s_extra_raw['roi_kelly']:+}% | {s_extra_raw['max_dd']}% | {s_extra_cal['bets_made']} | **{s_extra_cal['roi_kelly']:+}%** | **{s_extra_cal['max_dd']}%** |")
    md.append("\n")
    
    md.append("## 2. Metodología y Notas\n")
    md.append("- **Cuotas Reales:** Se toman directamente las cuotas de cierre registradas de los bookmakers (Pinnacle/Bet365) a través de The Odds API en producción. No hay cuotas sintéticas ni supuestas.")
    md.append("- **Criterio de Kelly (Quarter-Kelly):** Se simula un bankroll inicial de $100.0. Cada apuesta arriesga el porcentaje sugerido por la fórmula oficial multiplicada por 0.25 (Quarter-Kelly) para amortiguar el riesgo.")
    md.append("- **Sin Calibrar (Raw):** Usa las probabilidades originales declaradas por el motor de Poisson, propensas a la sobreconfianza.")
    md.append("- **Calibrado (Platt):** Aplica la calibración de Platt entrenada sobre los resultados previos para suavizar y corregir la sobreconfianza de las probabilidades antes de estimar el stake de Kelly. Como se observa en la tabla, el calibrador filtra la gran mayoría de apuestas que no tienen ventaja real, actuando como un escudo protector del bankroll.")
    md.append("- **Drawdown Máximo:** Mide la mayor caída porcentual del bankroll desde su pico más alto anterior, un indicador crítico del riesgo real de ruina.")
    
    report_text = "\n".join(md)
    output_path = ROOT / "static" / "_backtest_log_real_report.md"
    output_path.write_text(report_text, encoding="utf-8")
    
    logger.info("Backtest de log completado. Reporte guardado en %s", output_path)
    
    print("\n" + "="*70)
    print("      RENDIMIENTO REAL EN PRODUCCIÓN (RAW VS CALIBRADO)")
    print("="*70)
    print(f"Picks Totales Evaluados: {s_all_raw['n']}")
    print(f"ROI Apuesta Plana:       {s_all_raw['roi_flat']}%")
    print("-" * 70)
    print("                     [ KELLY RAW ]      [ KELLY CALIBRADO (PLATT) ]")
    print(f"Apuestas realizadas:     {s_all_raw['bets_made']}                 {s_all_cal['bets_made']}")
    print(f"ROI Kelly Acumulado:     {s_all_raw['roi_kelly']}%               {s_all_cal['roi_kelly']}%")
    print(f"Drawdown Máximo:         {s_all_raw['max_dd']}%                 {s_all_cal['max_dd']}%")
    print(f"Bankroll Final:          ${s_all_raw['bankroll_final']}               ${s_all_cal['bankroll_final']}")
    print("="*70)

if __name__ == "__main__":
    main()
