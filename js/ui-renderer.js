/**
 * UI RENDERER MODULE
 * Responsable de renderizar los resultados en la interfaz
 */

const UIRenderer = {
    
    /**
     * Renderiza la predicción del ganador
     * @param {Object} winnerData - Datos de la predicción del ganador
     */
    renderWinner(winnerData) {
        const container = document.getElementById('winner-prediction');
        
        const confidenceClass = 
            winnerData.confidence === 'alta' ? 'confidence-high' :
            winnerData.confidence === 'media' ? 'confidence-medium' :
            'confidence-low';
        
        container.innerHTML = `
            <div class="prediction-winner">${winnerData.winner}</div>
            <div class="prediction-confidence ${confidenceClass}">
                Confianza: ${winnerData.confidence.toUpperCase()} (${winnerData.probability}%)
            </div>
            <div style="margin-top: 1rem; font-size: 0.9rem; color: var(--text-muted);">
                Local: ${winnerData.homeWinProb}% | 
                Empate: ${winnerData.drawProb}% | 
                Visitante: ${winnerData.awayWinProb}%
            </div>
        `;
    },

    /**
     * Renderiza las predicciones de goles
     * @param {Object} goalsData - Datos de predicciones de goles
     */
    renderGoals(goalsData) {
        const container = document.getElementById('goals-prediction');
        
        const goals = [
            { label: 'Over 1.5', data: goalsData.over15 },
            { label: 'Over 2.5', data: goalsData.over25 },
            { label: 'Over 3.5', data: goalsData.over35 }
        ];
        
        let html = '';
        
        goals.forEach(goal => {
            const recommendedClass = goal.data.recommended ? 'recommended' : '';
            const probability = parseFloat(goal.data.probability);
            
            html += `
                <div class="goal-prediction ${recommendedClass}">
                    <span class="goal-label">
                        ${goal.label}
                        ${goal.data.recommended ? '⭐' : ''}
                    </span>
                    <div class="goal-probability">
                        <div class="probability-bar">
                            <div class="probability-fill" style="width: ${probability}%"></div>
                        </div>
                        <span class="probability-text">${goal.data.probability}%</span>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    },

    /**
     * Renderiza la predicción BTTS
     * @param {Object} bttsData - Datos de predicción BTTS
     */
    renderBTTS(bttsData) {
        const container = document.getElementById('btts-prediction');
        
        const confidenceClass = 
            bttsData.confidence === 'alta' ? 'confidence-high' :
            bttsData.confidence === 'media' ? 'confidence-medium' :
            'confidence-low';
        
        const icon = bttsData.prediction === 'SÍ' ? '✅' : '❌';
        
        container.innerHTML = `
            <div class="prediction-winner" style="display: flex; align-items: center; gap: 1rem; justify-content: center;">
                <span>${icon}</span>
                <span>${bttsData.prediction}</span>
            </div>
            <div class="prediction-confidence ${confidenceClass}">
                Probabilidad: ${bttsData.probability}%
            </div>
            <div style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-muted);">
                ${bttsData.reasoning}
            </div>
        `;
    },

    /**
     * Renderiza las predicciones de corners
     * @param {Object} cornersData - Datos de predicciones de corners
     */
    renderCorners(cornersData) {
        const container = document.getElementById('corners-prediction');
        
        container.innerHTML = `
            <div class="corner-stat" style="background: rgba(0, 255, 136, 0.1); border-left: 3px solid var(--accent-primary);">
                <span class="corner-label">Total Esperado</span>
                <span class="corner-value">${cornersData.totalExpected}</span>
            </div>
            <div class="corner-stat">
                <span class="corner-label">Local Esperado</span>
                <span class="corner-value">${cornersData.homeExpected}</span>
            </div>
            <div class="corner-stat">
                <span class="corner-label">Visitante Esperado</span>
                <span class="corner-value">${cornersData.awayExpected}</span>
            </div>
            <div class="corner-stat" style="background: rgba(255, 215, 0, 0.1);">
                <span class="corner-label">Recomendación</span>
                <span class="corner-value" style="color: var(--accent-secondary);">
                    ${cornersData.recommended}
                </span>
            </div>
        `;
    },

    /**
     * Renderiza las estadísticas detalladas de un equipo
     * @param {Object} stats - Estadísticas del equipo
     * @param {string} containerId - ID del contenedor
     */
    renderTeamStats(stats, containerId) {
        const container = document.getElementById(containerId);
        
        const position = stats.position;
        const corners = stats.corners;
        const goals = stats.goals;
        
        const winRate = ((position.ganados / position.partidos) * 100).toFixed(1);
        const avgGoalsScored = (position.goles_favor / position.partidos).toFixed(2);
        const avgGoalsConceded = (position.goles_contra / position.partidos).toFixed(2);
        
        container.innerHTML = `
            <div class="stat-row">
                <span class="stat-label">Posición</span>
                <span class="stat-value">#${position.posicion}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Puntos</span>
                <span class="stat-value">${position.puntos} pts</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Partidos</span>
                <span class="stat-value">${position.partidos} (${position.ganados}G / ${position.empatados}E / ${position.perdidos}D)</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Win Rate</span>
                <span class="stat-value">${winRate}%</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Goles Favor/Contra</span>
                <span class="stat-value">${position.goles_favor} / ${position.goles_contra}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Promedio Goles/Partido</span>
                <span class="stat-value">${avgGoalsScored} marcados | ${avgGoalsConceded} recibidos</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Diferencia de Goles</span>
                <span class="stat-value" style="color: ${position.diferencia > 0 ? 'var(--accent-primary)' : 'var(--accent-danger)'}">
                    ${position.diferencia > 0 ? '+' : ''}${position.diferencia}
                </span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Corners Promedio</span>
                <span class="stat-value">${corners.corners_favor} a favor | ${corners.corners_contra} en contra</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Over 2.5</span>
                <span class="stat-value">${goals.over_2_5}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">BTTS</span>
                <span class="stat-value">${goals.btts || goals.bts}</span>
            </div>
        `;
    },

    /**
     * Renderiza todos los resultados del análisis
     * @param {Object} analysis - Análisis completo del partido
     * @param {string} homeTeam - Nombre del equipo local
     * @param {string} awayTeam - Nombre del equipo visitante
     */
    renderAnalysis(analysis, homeTeam, awayTeam) {
        // Mostrar contenedor de resultados
        const resultsContainer = document.getElementById('results-container');
        resultsContainer.classList.remove('hidden');
        
        // Renderizar cada sección
        this.renderWinner(analysis.winner);
        this.renderGoals(analysis.goals);
        this.renderBTTS(analysis.btts);
        this.renderCorners(analysis.corners);
        
        // Renderizar estadísticas detalladas
        document.getElementById('home-stats-title').textContent = `${homeTeam} (Local)`;
        document.getElementById('away-stats-title').textContent = `${awayTeam} (Visitante)`;
        
        this.renderTeamStats(analysis.homeStats, 'home-stats-content');
        this.renderTeamStats(analysis.awayStats, 'away-stats-content');
        
        // Scroll suave hacia los resultados
        setTimeout(() => {
            resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    },

    /**
     * Muestra/oculta el overlay de carga
     * @param {boolean} show - Mostrar u ocultar
     */
    toggleLoading(show) {
        const overlay = document.getElementById('loading-overlay');
        if (show) {
            overlay.classList.remove('hidden');
        } else {
            overlay.classList.add('hidden');
        }
    },

    /**
     * Muestra un mensaje de error
     * @param {string} message - Mensaje de error
     */
    showError(message) {
        alert(`❌ Error: ${message}`);
    },

    /**
     * Actualiza la fecha de última actualización
     * @param {string} date - Fecha en formato ISO
     */
    updateLastUpdate(date) {
        const dateObj = new Date(date);
        const formatted = dateObj.toLocaleString('es-ES', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        document.getElementById('last-update').textContent = formatted;
    },

    /**
     * Puebla los selectores de equipos
     * @param {Array<string>} teams - Lista de equipos
     */
    populateTeamSelectors(teams) {
        const homeSelect = document.getElementById('home-team');
        const awaySelect = document.getElementById('away-team');
        
        // Limpiar opciones existentes (excepto la primera)
        homeSelect.innerHTML = '<option value="">-- Seleccionar equipo --</option>';
        awaySelect.innerHTML = '<option value="">-- Seleccionar equipo --</option>';
        
        // Agregar equipos
        teams.forEach(team => {
            const option1 = document.createElement('option');
            option1.value = team;
            option1.textContent = team;
            homeSelect.appendChild(option1);
            
            const option2 = document.createElement('option');
            option2.value = team;
            option2.textContent = team;
            awaySelect.appendChild(option2);
        });
    },

    /**
     * Actualiza el badge de la liga actual
     * @param {Object} leagueConfig - Configuración de la liga
     */
    updateLeagueBadge(leagueConfig) {
        const badge = document.getElementById('current-league-badge');
        
        badge.innerHTML = `
            <span class="league-flag ${leagueConfig.flag}"></span>
            <div class="league-info">
                <span class="league-name">${leagueConfig.name.toUpperCase()}</span>
                <span class="season">2024/25</span>
            </div>
        `;
    }
};

// Exportar para uso global
window.UIRenderer = UIRenderer;
