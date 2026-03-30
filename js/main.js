/**
 * MAIN APPLICATION CONTROLLER
 * Punto de entrada y controlador principal de la aplicación
 */

// Estado de la aplicación
const AppState = {
    homeTeam: null,
    awayTeam: null,
    currentLeague: 'italy',
    isAnalyzing: false,
    isLoadingLeague: false
};

/**
 * Inicializa la aplicación
 */
async function initApp() {
    console.log('🚀 Inicializando Football Predictor Dashboard...');
    
    try {
        // Mostrar loading
        UIRenderer.toggleLoading(true);
        
        // Cargar liga por defecto
        await loadLeague(AppState.currentLeague);
        
        // Configurar event listeners
        setupEventListeners();
        
        // Ocultar loading
        UIRenderer.toggleLoading(false);
        
        console.log('✅ Aplicación inicializada correctamente');
        
    } catch (error) {
        console.error('❌ Error inicializando aplicación:', error);
        UIRenderer.toggleLoading(false);
        UIRenderer.showError('No se pudo cargar la aplicación. Verifica que el archivo JSON esté disponible.');
    }
}

/**
 * Carga los datos de una liga específica
 * @param {string} league - Código de la liga
 */
async function loadLeague(league) {
    try {
        console.log(`📊 Cargando liga: ${league}`);
        
        // Cargar datos
        await DataLoader.loadData(league);
        
        // Obtener configuración de la liga
        const leagueConfig = DataLoader.getCurrentLeagueConfig();
        
        // Actualizar badge de la liga
        UIRenderer.updateLeagueBadge(leagueConfig);
        
        // Obtener lista de equipos
        const teams = DataLoader.getTeamsList();
        
        if (teams.length === 0) {
            throw new Error('No se encontraron equipos en los datos');
        }
        
        // Poblar selectores
        UIRenderer.populateTeamSelectors(teams);
        
        // Actualizar fecha de última actualización
        const metadata = DataLoader.getMetadata();
        if (metadata && metadata.fecha_actualizacion) {
            UIRenderer.updateLastUpdate(metadata.fecha_actualizacion);
        }
        
        // Reset selecciones
        AppState.homeTeam = null;
        AppState.awayTeam = null;
        AppState.currentLeague = league;
        
        // Ocultar resultados previos
        const resultsContainer = document.getElementById('results-container');
        resultsContainer.classList.add('hidden');
        
        // Actualizar botón
        updateAnalyzeButton();
        
        console.log(`✅ Liga ${leagueConfig.name} cargada correctamente`);
        
    } catch (error) {
        console.error('❌ Error cargando liga:', error);
        
        // Mostrar mensaje más específico
        const leagueConfig = DataLoader.getLeagueConfig(league);
        const leagueName = leagueConfig ? leagueConfig.name : league;
        
        UIRenderer.showError(
            `No se pudo cargar ${leagueName}. ` +
            `Verifica que el archivo '${leagueConfig?.file || 'datos'}' exista en la carpeta 'static'.`
        );
        
        throw error;
    }
}

/**
 * Configura los event listeners
 */
function setupEventListeners() {
    const homeSelect = document.getElementById('home-team');
    const awaySelect = document.getElementById('away-team');
    const analyzeBtn = document.getElementById('analyze-btn');
    const leagueSelect = document.getElementById('league-select');
    
    // Listener para cambio de liga
    leagueSelect.addEventListener('change', async (e) => {
        const selectedLeague = e.target.value;
        
        if (AppState.isLoadingLeague) return;
        
        AppState.isLoadingLeague = true;
        UIRenderer.toggleLoading(true);
        
        try {
            await loadLeague(selectedLeague);
        } catch (error) {
            // Revertir selección si falla
            e.target.value = AppState.currentLeague;
        } finally {
            UIRenderer.toggleLoading(false);
            AppState.isLoadingLeague = false;
        }
    });
    
    // Listener para cambio en selector de equipo local
    homeSelect.addEventListener('change', (e) => {
        AppState.homeTeam = e.target.value;
        updateAnalyzeButton();
    });
    
    // Listener para cambio en selector de equipo visitante
    awaySelect.addEventListener('change', (e) => {
        AppState.awayTeam = e.target.value;
        updateAnalyzeButton();
    });
    
    // Listener para botón de análisis
    analyzeBtn.addEventListener('click', handleAnalyze);
}

/**
 * Actualiza el estado del botón de análisis
 */
function updateAnalyzeButton() {
    const analyzeBtn = document.getElementById('analyze-btn');
    const isValid = DataLoader.validateTeamSelection(AppState.homeTeam, AppState.awayTeam);
    
    analyzeBtn.disabled = !isValid;
    
    // Cambiar estilo si los equipos son iguales
    if (AppState.homeTeam && AppState.awayTeam && AppState.homeTeam === AppState.awayTeam) {
        analyzeBtn.textContent = '⚠️ SELECCIONA EQUIPOS DIFERENTES';
        analyzeBtn.style.background = 'var(--accent-danger)';
    } else {
        analyzeBtn.innerHTML = `
            <span class="btn-text">ANALIZAR PARTIDO</span>
            <span class="btn-icon">📊</span>
        `;
        analyzeBtn.style.background = '';
    }
}

/**
 * Maneja el análisis del partido
 */
async function handleAnalyze() {
    if (AppState.isAnalyzing) return;
    
    const { homeTeam, awayTeam } = AppState;
    
    if (!DataLoader.validateTeamSelection(homeTeam, awayTeam)) {
        UIRenderer.showError('Selección de equipos inválida');
        return;
    }
    
    try {
        AppState.isAnalyzing = true;
        
        // Mostrar loading
        UIRenderer.toggleLoading(true);
        
        console.log(`📊 Analizando partido: ${homeTeam} vs ${awayTeam}`);
        
        // Simular delay para efecto de carga (opcional)
        await new Promise(resolve => setTimeout(resolve, 800));
        
        // Realizar análisis
        const analysis = Calculator.analyzeMatch(homeTeam, awayTeam);
        
        console.log('✅ Análisis completado:', analysis);
        
        // Ocultar loading
        UIRenderer.toggleLoading(false);
        
        // Renderizar resultados
        UIRenderer.renderAnalysis(analysis, homeTeam, awayTeam);
        
        // Log para debugging
        logAnalysisToConsole(analysis, homeTeam, awayTeam);
        
    } catch (error) {
        console.error('❌ Error analizando partido:', error);
        UIRenderer.toggleLoading(false);
        UIRenderer.showError(`Error al analizar el partido: ${error.message}`);
    } finally {
        AppState.isAnalyzing = false;
    }
}

/**
 * Registra el análisis en la consola para debugging
 * @param {Object} analysis - Análisis del partido
 * @param {string} homeTeam - Equipo local
 * @param {string} awayTeam - Equipo visitante
 */
function logAnalysisToConsole(analysis, homeTeam, awayTeam) {
    console.log('\n' + '='.repeat(60));
    console.log(`🏟️  ANÁLISIS: ${homeTeam} vs ${awayTeam}`);
    console.log('='.repeat(60));
    
    console.log('\n🏆 PREDICCIÓN GANADOR:');
    console.log(`   Ganador: ${analysis.winner.winner}`);
    console.log(`   Confianza: ${analysis.winner.confidence} (${analysis.winner.probability}%)`);
    console.log(`   Probabilidades: Local ${analysis.winner.homeWinProb}% | Empate ${analysis.winner.drawProb}% | Visitante ${analysis.winner.awayWinProb}%`);
    
    console.log('\n⚽ PREDICCIÓN GOLES:');
    console.log(`   Over 1.5: ${analysis.goals.over15.probability}% ${analysis.goals.over15.recommended ? '⭐' : ''}`);
    console.log(`   Over 2.5: ${analysis.goals.over25.probability}% ${analysis.goals.over25.recommended ? '⭐' : ''}`);
    console.log(`   Over 3.5: ${analysis.goals.over35.probability}% ${analysis.goals.over35.recommended ? '⭐' : ''}`);
    console.log(`   Mejor apuesta: ${analysis.goals.bestBet} (${analysis.goals.bestProbability}%)`);
    
    console.log('\n🎯 PREDICCIÓN BTTS:');
    console.log(`   Predicción: ${analysis.btts.prediction}`);
    console.log(`   Probabilidad: ${analysis.btts.probability}%`);
    console.log(`   Confianza: ${analysis.btts.confidence}`);
    
    console.log('\n🚩 PREDICCIÓN CORNERS:');
    console.log(`   Total Esperado: ${analysis.corners.totalExpected}`);
    console.log(`   Local Esperado: ${analysis.corners.homeExpected}`);
    console.log(`   Visitante Esperado: ${analysis.corners.awayExpected}`);
    console.log(`   Recomendación: ${analysis.corners.recommended}`);
    
    console.log('\n' + '='.repeat(60) + '\n');
}

/**
 * Maneja errores globales
 */
window.addEventListener('error', (event) => {
    console.error('❌ Error global:', event.error);
});

/**
 * Maneja errores de promesas no capturadas
 */
window.addEventListener('unhandledrejection', (event) => {
    console.error('❌ Promise rechazada:', event.reason);
});

// Inicializar la aplicación cuando el DOM esté listo
// initApp() es llamado desde enterApp() en app.html

// Exportar para debugging
window.AppState = AppState;
window.handleAnalyze = handleAnalyze;