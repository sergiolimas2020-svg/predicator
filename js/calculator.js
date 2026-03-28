/**
 * CALCULATOR MODULE
 * Responsable de calcular predicciones basadas en estadísticas
 */

const Calculator = {
    
    /**
     * Calcula el ganador más probable
     * @param {Object} homeStats - Estadísticas del equipo local
     * @param {Object} awayStats - Estadísticas del equipo visitante
     * @param {string} homeTeam - Nombre del equipo local
     * @param {string} awayTeam - Nombre del equipo visitante
     * @returns {Object} Predicción del ganador
     */
    predictWinner(homeStats, awayStats, homeTeam, awayTeam) {
        const homePos = homeStats.position;
        const awayPos = awayStats.position;
        
        // Calcular puntuación basada en múltiples factores
        let homeScore = 0;
        let awayScore = 0;
        
        // Factor 1: Posición en la tabla (40% peso)
        const positionWeight = 0.4;
        homeScore += (21 - homePos.posicion) * positionWeight * 5;
        awayScore += (21 - awayPos.posicion) * positionWeight * 5;
        
        // Factor 2: Forma reciente - Win rate (30% peso)
        const formWeight = 0.3;
        const homeWinRate = (homePos.ganados / homePos.partidos) * 100;
        const awayWinRate = (awayPos.ganados / awayPos.partidos) * 100;
        homeScore += homeWinRate * formWeight;
        awayScore += awayWinRate * formWeight;
        
        // Factor 3: Diferencia de goles (20% peso)
        const goalDiffWeight = 0.2;
        homeScore += homePos.diferencia * goalDiffWeight;
        awayScore += awayPos.diferencia * goalDiffWeight;
        
        // Factor 4: Ventaja de local (10% peso adicional para home)
        const homeAdvantage = 0.1;
        homeScore += homeScore * homeAdvantage;
        
        // Determinar ganador
        const totalScore = homeScore + awayScore;
        const homeWinProbability = (homeScore / totalScore) * 100;
        const awayWinProbability = (awayScore / totalScore) * 100;
        const drawProbability = 100 - homeWinProbability - awayWinProbability;
        
        let prediction = '';
        let confidence = '';
        let probability = 0;
        
        const diff = Math.abs(homeWinProbability - awayWinProbability);
        
        if (diff < 10) {
            prediction = 'EMPATE';
            probability = 33;
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
            winner: prediction,
            confidence: confidence,
            probability: probability.toFixed(1),
            homeWinProb: homeWinProbability.toFixed(1),
            awayWinProb: awayWinProbability.toFixed(1),
            drawProb: (100 - homeWinProbability - awayWinProbability).toFixed(1)
        };
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

// Exportar para uso global
window.Calculator = Calculator;
