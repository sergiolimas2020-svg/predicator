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
    HOME_ADVANTAGE_PCT:    0.1,
    MIN_PROB:             15.0,   // cap inferior (Python: MODEL_MIN_PROB)
    MAX_PROB:             85.0,   // cap superior (Python: MODEL_MAX_PROB)
    DRAW_DIFF_THRESHOLD:  10.0,   // empate técnico (Python: MODEL_DRAW_DIFF)
    DRAW_PCT_MIN:         20.0,
    DRAW_PCT_MAX:         30.0,
    DRAW_DIFF_FACTOR:      0.20,
};

const Calculator = {

    /**
     * Calcula el ganador más probable.
     * Espejo de prob_futbol() en Python.
     *
     * @param {Object} homeStats - Estadísticas del equipo local
     * @param {Object} awayStats - Estadísticas del equipo visitante
     * @param {string} homeTeam - Nombre del equipo local
     * @param {string} awayTeam - Nombre del equipo visitante
     * @returns {Object} {winner, confidence, probability, homeWinProb, awayWinProb, drawProb}
     */
    predictWinner(homeStats, awayStats, homeTeam, awayTeam) {
        const homePos = homeStats.position;
        const awayPos = awayStats.position;

        // Calcular puntuación basada en múltiples factores
        let homeScore = 0;
        let awayScore = 0;

        // Factor 1: Posición en la tabla (40% peso)
        homeScore += (MODEL.POSITION_RANGE - homePos.posicion) * MODEL.WEIGHT_POSITION * 5;
        awayScore += (MODEL.POSITION_RANGE - awayPos.posicion) * MODEL.WEIGHT_POSITION * 5;

        // Factor 2: Forma reciente - Win rate (30% peso)
        const homeGames = homePos.partidos || 1;
        const awayGames = awayPos.partidos || 1;
        const homeWinRate = (homePos.ganados / homeGames) * 100;
        const awayWinRate = (awayPos.ganados / awayGames) * 100;
        homeScore += homeWinRate * MODEL.WEIGHT_WIN_RATE;
        awayScore += awayWinRate * MODEL.WEIGHT_WIN_RATE;

        // Factor 3: Diferencia de goles (20% peso)
        homeScore += (homePos.diferencia || 0) * MODEL.WEIGHT_GOAL_DIFF;
        awayScore += (awayPos.diferencia || 0) * MODEL.WEIGHT_GOAL_DIFF;

        // Factor 4: Ventaja de local (10% adicional sobre el score local)
        homeScore += homeScore * MODEL.HOME_ADVANTAGE_PCT;

        // ── Cálculo 1X2 con caps [MIN_PROB, MAX_PROB] ──
        // Espejo de prob_futbol() en Python (que retorna hp, ap)
        const totalScore = (homeScore + awayScore) || 1;
        let hp = (homeScore / totalScore) * 100;
        hp = Math.min(MODEL.MAX_PROB, Math.max(MODEL.MIN_PROB, hp));
        hp = Math.round(hp * 10) / 10;
        let ap = Math.round((100 - hp) * 10) / 10;

        // Empate técnico: si diff < 10, ambos a 50/50 (igual que Python)
        if (Math.abs(hp - ap) < MODEL.DRAW_DIFF_THRESHOLD) {
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

        if (diff < MODEL.DRAW_DIFF_THRESHOLD) {
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
     * @returns {Object} {win, draw, lose} — porcentajes redondeados
     */
    predictWinner3Way(homeStats, awayStats) {
        const winner = this.predictWinner(homeStats, awayStats, 'home', 'away');
        const hp = parseFloat(winner.homeWinProb);
        const ap = parseFloat(winner.awayWinProb);
        const diff = Math.abs(hp - ap);
        const drawPct = Math.max(
            MODEL.DRAW_PCT_MIN,
            MODEL.DRAW_PCT_MAX - diff * MODEL.DRAW_DIFF_FACTOR
        );
        const scale = (100 - drawPct) / 100;
        const win  = Math.round(hp * scale * 10) / 10;
        const lose = Math.round(ap * scale * 10) / 10;
        const draw = Math.round((100 - win - lose) * 10) / 10;
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
