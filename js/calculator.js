/**
 * CALCULATOR MODULE
 * Responsable de calcular predicciones basadas en estadísticas.
 *
 * IMPORTANTE — paridad con Python:
 * Los resultados de predictWinner() coinciden 1:1 con prob_futbol() en
 * scrapers/generate_predictions.py. Si modificás constantes acá, hay que
 * sincronizarlas allá también. Ver tests/test_consistency.py.
 */

// ── Constantes del modelo (espejo de generate_predictions.py) ──
const MODEL = {
    POSITION_RANGE:        21,    // = max_posicion + 1
    WEIGHT_POSITION:       0.4,
    WEIGHT_WIN_RATE:       0.3,
    WEIGHT_GOAL_DIFF:      0.2,
    LOGISTIC_K:            0.10,  // pendiente sigmoide (Python: MODEL_LOGISTIC_K)
    HOME_ADVANTAGE_SCORE:  3.0,   // ventaja local aditiva (Python: HOME_ADVANTAGE_SCORE)
    MIN_PROB:             15.0,   // cap inferior (Python: MODEL_MIN_PROB)
    MAX_PROB:             85.0,   // cap superior (Python: MODEL_MAX_PROB)
    DRAW_DIFF_THRESHOLD:  10.0,   // empate técnico (Python: MODEL_DRAW_DIFF)
    DRAW_PCT_MIN:         20.0,
    DRAW_PCT_MAX:         30.0,
    DRAW_DIFF_FACTOR:      0.20,
};

// Score compuesto de un equipo — espejo de _team_score() en Python.
// Score compuesto de un equipo — espejo de _team_score() en Python.
// Mantenido por retrocompatibilidad, aunque el modelo use Poisson directo.
function teamScore(pos) {
    let s = (MODEL.POSITION_RANGE - pos.posicion) * MODEL.WEIGHT_POSITION * 5;
    const games = pos.partidos || 1;
    s += ((pos.ganados / games) * 100) * MODEL.WEIGHT_WIN_RATE;
    s += (pos.diferencia || 0) * MODEL.WEIGHT_GOAL_DIFF;
    return s;
}

const Calculator = {

    /**
     * Calcula la distribución de Poisson 3-way en bruto.
     * Espejo de prob_futbol_3way_raw() en Python.
     */
    predictWinner3WayRaw(homeStats, awayStats, danger = null) {
        const homePos = homeStats.position || {};
        const awayPos = awayStats.position || {};

        const parseFloatSafe = (v, def = 0.0) => {
            const f = parseFloat(v);
            return isNaN(f) ? def : f;
        };

        const h_gf = parseFloatSafe(homePos.goles_favor, 0);
        const h_gc = parseFloatSafe(homePos.goles_contra, 0);
        const h_games = parseFloatSafe(homePos.partidos, 0);

        const a_gf = parseFloatSafe(awayPos.goles_favor, 0);
        const a_gc = parseFloatSafe(awayPos.goles_contra, 0);
        const a_games = parseFloatSafe(awayPos.partidos, 0);

        const AVG_LEAGUE_GOALS = 1.35;
        const HOME_ADVANTAGE_FACTOR = 1.15;

        let h_att = h_games > 0 ? h_gf / h_games : AVG_LEAGUE_GOALS;
        let h_def = h_games > 0 ? h_gc / h_games : AVG_LEAGUE_GOALS;
        let a_att = a_games > 0 ? a_gf / a_games : AVG_LEAGUE_GOALS;
        let a_def = a_games > 0 ? a_gc / a_games : AVG_LEAGUE_GOALS;

        h_att = Math.max(0.3, Math.min(3.0, h_att));
        h_def = Math.max(0.3, Math.min(3.0, h_def));
        a_att = Math.max(0.3, Math.min(3.0, a_att));
        a_def = Math.max(0.3, Math.min(3.0, a_def));

        let lambda_h = (h_att * a_def / AVG_LEAGUE_GOALS) * HOME_ADVANTAGE_FACTOR;
        let lambda_a = (a_att * h_def / AVG_LEAGUE_GOALS) / HOME_ADVANTAGE_FACTOR;

        if (danger && typeof danger === 'object') {
            const home_sot = danger.home_sot;
            const away_sot = danger.away_sot;
            const SOT_AVG = 4.5;

            if (home_sot !== undefined && home_sot !== null) {
                const adj_h = 1.0 + 0.15 * ((parseFloatSafe(home_sot) - SOT_AVG) / SOT_AVG);
                lambda_h *= Math.max(0.7, Math.min(1.3, adj_h));
            }
            if (away_sot !== undefined && away_sot !== null) {
                const adj_a = 1.0 + 0.15 * ((parseFloatSafe(away_sot) - SOT_AVG) / SOT_AVG);
                lambda_a *= Math.max(0.7, Math.min(1.3, adj_a));
            }
        }

        // Ajuste por Elo Rating
        const elo_home = homeStats.elo;
        const elo_away = awayStats.elo;
        if (elo_home !== undefined && elo_home !== null && elo_away !== undefined && elo_away !== null) {
            const elo_diff = elo_home - elo_away;
            const adj_h = 1.0 + 0.0005 * elo_diff;
            const adj_a = 1.0 - 0.0005 * elo_diff;
            lambda_h *= Math.max(0.8, Math.min(1.2, adj_h));
            lambda_a *= Math.max(0.8, Math.min(1.2, adj_a));
        }

        lambda_h = Math.max(0.1, Math.min(6.0, lambda_h));
        lambda_a = Math.max(0.1, Math.min(6.0, lambda_a));

        let p_win = 0.0;
        let p_draw = 0.0;
        let p_lose = 0.0;

        const factorial = (n) => {
            let res = 1;
            for (let i = 2; i <= n; i++) res *= i;
            return res;
        };

        const poisson_h = [];
        const poisson_a = [];
        for (let x = 0; x <= 10; x++) {
            poisson_h.push((Math.pow(lambda_h, x) * Math.exp(-lambda_h)) / factorial(x));
            poisson_a.push((Math.pow(lambda_a, x) * Math.exp(-lambda_a)) / factorial(x));
        }

        // Dixon-Coles τ(x,y) — ESPEJO EXACTO de DIXON_COLES_RHO/_dc_tau en
        // scrapers/generate_predictions.py. Cualquier cambio debe replicarse allá
        // (el test de paridad Python↔JS lo verifica).
        const DIXON_COLES_RHO = -0.10;
        const dcTau = (x, y) => {
            if (x === 0 && y === 0) return 1.0 - lambda_h * lambda_a * DIXON_COLES_RHO;
            if (x === 0 && y === 1) return 1.0 + lambda_h * DIXON_COLES_RHO;
            if (x === 1 && y === 0) return 1.0 + lambda_a * DIXON_COLES_RHO;
            if (x === 1 && y === 1) return 1.0 - DIXON_COLES_RHO;
            return 1.0;
        };

        for (let x = 0; x <= 10; x++) {
            for (let y = 0; y <= 10; y++) {
                const p_xy = poisson_h[x] * poisson_a[y] * dcTau(x, y);
                if (x > y) {
                    p_win += p_xy;
                } else if (x === y) {
                    p_draw += p_xy;
                } else {
                    p_lose += p_xy;
                }
            }
        }

        const total = p_win + p_draw + p_lose;
        if (total > 0) {
            p_win /= total;
            p_draw /= total;
            p_lose /= total;
        } else {
            p_win = 0.37;
            p_draw = 0.26;
            p_lose = 0.37;
        }

        return { p_win, p_draw, p_lose };
    },

    /**
     * Calcula el ganador más probable.
     * Espejo de prob_futbol() en Python.
     *
     * @param {Object} homeStats - Estadísticas del equipo local
     * @param {Object} awayStats - Estadísticas del equipo visitante
     * @param {string} homeTeam - Nombre del equipo local
     * @param {string} awayTeam - Nombre del equipo visitante
     * @param {Object} danger - Opcional, datos de tiros a puerta
     * @returns {Object} {winner, confidence, probability, homeWinProb, awayWinProb, drawProb}
     */
    predictWinner(homeStats, awayStats, homeTeam, awayTeam, danger = null) {
        const { p_win, p_draw, p_lose } = this.predictWinner3WayRaw(homeStats, awayStats, danger);

        let hp, ap;
        const sum_wl = p_win + p_lose;
        if (sum_wl > 0) {
            hp = (p_win / sum_wl) * 100;
            ap = (p_lose / sum_wl) * 100;
        } else {
            hp = 50.0;
            ap = 50.0;
        }

        // Aplicar caps del modelo (espejo de Python MODEL_MAX_PROB / MODEL_MIN_PROB)
        const MODEL_MAX_PROB = 85.0;
        const MODEL_MIN_PROB = 15.0;
        const MODEL_DRAW_DIFF_THRESHOLD = 10.0;

        hp = Math.min(MODEL_MAX_PROB, Math.max(MODEL_MIN_PROB, hp));
        ap = Math.round((100.0 - hp) * 10) / 10;
        hp = Math.round(hp * 10) / 10;

        // Empate técnico
        if (Math.abs(hp - ap) < MODEL_DRAW_DIFF_THRESHOLD) {
            hp = 50.0;
            ap = 50.0;
        }

        const homeWinProbability = hp;
        const awayWinProbability = ap;
        const drawProbability = Math.max(0, 100 - hp - ap);

        // Lógica de presentación (winner + confidence label)
        let prediction = '';
        let confidence = '';
        let probability = 0;
        const diff = Math.abs(homeWinProbability - awayWinProbability);

        if (diff < MODEL_DRAW_DIFF_THRESHOLD) {
            // Empate técnico — coherente con Python (50/50)
            prediction = 'EMPATE TÉCNICO';
            probability = 50;
            confidence = 'media';
        } else if (homeWinProbability > awayWinProbability) {
            prediction = homeTeam;
            probability = homeWinProbability;
            confidence = diff > 25 ? 'alta' : diff > 15 ? 'media' : 'baja';
        } else {
            prediction = awayTeam;
            probability = awayWinProbability;
            confidence = diff > 25 ? 'alta' : diff > 15 ? 'media' : 'baja';
        }

        return {
            winner:      prediction,
            confidence:  confidence,
            probability: probability.toFixed(1),
            homeWinProb: homeWinProbability.toFixed(1),
            awayWinProb: awayWinProbability.toFixed(1),
            drawProb:    drawProbability.toFixed(1),
        };
    },

    /**
     * Predicción 3-way: probabilidades de win / draw / lose que SÍ suman 100%.
     * Espejo de prob_futbol_3way() en Python.
     *
     * @param {Object} homeStats - Estadísticas del equipo local
     * @param {Object} awayStats - Estadísticas del equipo visitante
     * @param {Object} danger - Opcional, datos de tiros a puerta
     * @returns {Object} {win, draw, lose} — porcentajes redondeados
     */
    predictWinner3Way(homeStats, awayStats, danger = null) {
        const { p_win, p_draw, p_lose } = this.predictWinner3WayRaw(homeStats, awayStats, danger);
        const win = Math.round(p_win * 100 * 10) / 10;
        const lose = Math.round(p_lose * 100 * 10) / 10;
        const draw = Math.round((100.0 - win - lose) * 10) / 10;
        return { win, draw, lose };
    },

    /**
     * Calcula predicciones de goles (Over/Under)
     * @param {Object} homeStats - Estadísticas del equipo local
     * @param {Object} awayStats - Estadísticas del equipo visitante
     * @returns {Object} Predicciones de goles
     */
    predictGoals(homeStats, awayStats) {
        const homeGoals = homeStats.goals;
        const awayGoals = awayStats.goals;
        
        // Parsear porcentajes
        const homeOver15 = DataLoader.parsePercentage(homeGoals.over_1_5);
        const homeOver25 = DataLoader.parsePercentage(homeGoals.over_2_5);
        const homeOver35 = DataLoader.parsePercentage(homeGoals.over_3_5);
        
        const awayOver15 = DataLoader.parsePercentage(awayGoals.over_1_5);
        const awayOver25 = DataLoader.parsePercentage(awayGoals.over_2_5);
        const awayOver35 = DataLoader.parsePercentage(awayGoals.over_3_5);
        
        // Calcular promedios
        const over15Prob = (homeOver15 + awayOver15) / 2;
        const over25Prob = (homeOver25 + awayOver25) / 2;
        const over35Prob = (homeOver35 + awayOver35) / 2;
        
        // Determinar mejor apuesta
        let bestBet = 'Over 1.5';
        let bestProb = over15Prob;
        
        if (over25Prob > 50 && over25Prob > bestProb) {
            bestBet = 'Over 2.5';
            bestProb = over25Prob;
        }
        
        if (over35Prob > 50 && over35Prob > bestProb) {
            bestBet = 'Over 3.5';
            bestProb = over35Prob;
        }
        
        return {
            over15: {
                probability: over15Prob.toFixed(1),
                recommended: over15Prob > 65
            },
            over25: {
                probability: over25Prob.toFixed(1),
                recommended: over25Prob > 55
            },
            over35: {
                probability: over35Prob.toFixed(1),
                recommended: over35Prob > 45
            },
            bestBet: bestBet,
            bestProbability: bestProb.toFixed(1)
        };
    },

    /**
     * Calcula predicción de ambos equipos anotan (BTTS)
     * @param {Object} homeStats - Estadísticas del equipo local
     * @param {Object} awayStats - Estadísticas del equipo visitante
     * @returns {Object} Predicción BTTS
     */
    predictBTTS(homeStats, awayStats) {
        const homeBTTS = DataLoader.parsePercentage(homeStats.goals.btts || homeStats.goals.bts);
        const awayBTTS = DataLoader.parsePercentage(awayStats.goals.btts || awayStats.goals.bts);
        
        // Promedio de ambos equipos
        const bttsProbability = (homeBTTS + awayBTTS) / 2;
        
        // Factores adicionales: goles favor y contra
        const homePos = homeStats.position;
        const awayPos = awayStats.position;
        
        const homeGoalsPerGame = homePos.goles_favor / homePos.partidos;
        const awayGoalsPerGame = awayPos.goles_favor / awayPos.partidos;
        
        const homeAllowsGoals = homePos.goles_contra / homePos.partidos;
        const awayAllowsGoals = awayPos.goles_contra / awayPos.partidos;
        
        // Ajustar probabilidad si ambos marcan y reciben muchos goles
        let adjustedProb = bttsProbability;
        if (homeGoalsPerGame > 1.2 && awayGoalsPerGame > 1.2) {
            adjustedProb += 5;
        }
        if (homeAllowsGoals > 1.2 && awayAllowsGoals > 1.2) {
            adjustedProb += 5;
        }
        
        adjustedProb = Math.min(adjustedProb, 95); // Cap al 95%
        
        const recommendation = adjustedProb > 50 ? 'SÍ' : 'NO';
        const confidence = adjustedProb > 60 ? 'alta' : adjustedProb > 45 ? 'media' : 'baja';
        
        return {
            prediction: recommendation,
            probability: adjustedProb.toFixed(1),
            confidence: confidence,
            reasoning: `Local BTTS: ${homeBTTS.toFixed(1)}% | Visitante BTTS: ${awayBTTS.toFixed(1)}%`
        };
    },

    /**
     * Calcula predicciones de corners
     * @param {Object} homeStats - Estadísticas del equipo local
     * @param {Object} awayStats - Estadísticas del equipo visitante
     * @returns {Object} Predicciones de corners
     */
    predictCorners(homeStats, awayStats) {
        const homeCorners = homeStats.corners;
        const awayCorners = awayStats.corners;
        
        // Corners a favor
        const homeCornersFor = homeCorners.corners_favor || 0;
        const awayCornersFor = awayCorners.corners_favor || 0;
        
        // Corners en contra
        const homeCornersAgainst = homeCorners.corners_contra || 0;
        const awayCornersAgainst = awayCorners.corners_contra || 0;
        
        // Predicción de corners totales
        // Fórmula: (Local a favor + Visitante contra) + (Visitante a favor + Local contra) / 2
        const expectedHomeCorners = (homeCornersFor + awayCornersAgainst) / 2;
        const expectedAwayCorners = (awayCornersFor + homeCornersAgainst) / 2;
        const totalExpectedCorners = expectedHomeCorners + expectedAwayCorners;
        
        // Predicciones de rangos
        const over75 = totalExpectedCorners > 7.5;
        const over85 = totalExpectedCorners > 8.5;
        const over95 = totalExpectedCorners > 9.5;
        const over105 = totalExpectedCorners > 10.5;
        
        return {
            totalExpected: totalExpectedCorners.toFixed(1),
            homeExpected: expectedHomeCorners.toFixed(1),
            awayExpected: expectedAwayCorners.toFixed(1),
            predictions: {
                over75: {
                    predicted: over75,
                    confidence: over75 ? 'alta' : 'baja'
                },
                over85: {
                    predicted: over85,
                    confidence: over85 ? 'media' : 'baja'
                },
                over95: {
                    predicted: over95,
                    confidence: over95 ? 'media' : 'baja'
                },
                over105: {
                    predicted: over105,
                    confidence: over105 ? 'alta' : 'baja'
                }
            },
            recommended: totalExpectedCorners > 9 ? 'Over 9.5' : 'Over 8.5'
        };
    },

    /**
     * Genera un análisis completo del partido
     * @param {string} homeTeam - Equipo local
     * @param {string} awayTeam - Equipo visitante
     * @returns {Object} Análisis completo
     */
    analyzeMatch(homeTeam, awayTeam) {
        const homeStats = DataLoader.getHomeStats(homeTeam);
        const awayStats = DataLoader.getAwayStats(awayTeam);
        
        if (!homeStats || !awayStats) {
            throw new Error('No se pudieron obtener las estadísticas de los equipos');
        }
        
        return {
            winner: this.predictWinner(homeStats, awayStats, homeTeam, awayTeam),
            goals: this.predictGoals(homeStats, awayStats),
            btts: this.predictBTTS(homeStats, awayStats),
            corners: this.predictCorners(homeStats, awayStats),
            homeStats: homeStats,
            awayStats: awayStats
        };
    }
};

// Exportar para uso global (navegador)
if (typeof window !== 'undefined') {
    window.Calculator = Calculator;
}

// Exportar para Node (tests de paridad — tests/test_consistency.py)
// No afecta el uso en navegador porque `module` solo existe en CommonJS.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Calculator, MODEL };
}
