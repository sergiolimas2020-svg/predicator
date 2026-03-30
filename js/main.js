const AppState = {
    homeTeam: null,
    awayTeam: null,
    currentLeague: 'italy',
    isAnalyzing: false,
    isLoadingLeague: false
};

async function initApp(ligaInicial) {
    console.log('🚀 Inicializando Football Predictor Dashboard...');
    try {
        UIRenderer.toggleLoading(true);
        await loadLeague(ligaInicial || AppState.currentLeague);
        setupEventListeners();
        UIRenderer.toggleLoading(false);
        console.log('✅ Aplicación inicializada correctamente');
    } catch (error) {
        console.error('❌ Error inicializando aplicación:', error);
        UIRenderer.toggleLoading(false);
    }
}

async function loadLeague(league) {
    try {
        console.log('📊 Cargando liga: ' + league);
        await DataLoader.loadData(league);
        const leagueConfig = DataLoader.getCurrentLeagueConfig();
        UIRenderer.updateLeagueBadge(leagueConfig);
        const teams = DataLoader.getTeamsList();
        if (teams.length === 0) throw new Error('No se encontraron equipos');
        UIRenderer.populateTeamSelectors(teams);
        const metadata = DataLoader.getMetadata();
        if (metadata && metadata.fecha_actualizacion) {
            UIRenderer.updateLastUpdate(metadata.fecha_actualizacion);
        }
        AppState.homeTeam = null;
        AppState.awayTeam = null;
        AppState.currentLeague = league;
        const resultsContainer = document.getElementById('results-container');
        if (resultsContainer) resultsContainer.classList.add('hidden');
        updateAnalyzeButton();
        console.log('✅ Liga ' + leagueConfig.name + ' cargada correctamente');
    } catch (error) {
        console.error('❌ Error cargando liga:', error);
        throw error;
    }
}

function setupEventListeners() {
    const homeSelect = document.getElementById('home-team');
    const awaySelect = document.getElementById('away-team');
    const analyzeBtn = document.getElementById('analyze-btn');
    const leagueSelect = document.getElementById('league-select');
    if (!leagueSelect) return;

    leagueSelect.addEventListener('change', async (e) => {
        if (AppState.isLoadingLeague) return;
        AppState.isLoadingLeague = true;
        UIRenderer.toggleLoading(true);
        try {
            await loadLeague(e.target.value);
        } catch (error) {
            e.target.value = AppState.currentLeague;
        } finally {
            UIRenderer.toggleLoading(false);
            AppState.isLoadingLeague = false;
        }
    });

    homeSelect.addEventListener('change', (e) => { AppState.homeTeam = e.target.value; updateAnalyzeButton(); });
    awaySelect.addEventListener('change', (e) => { AppState.awayTeam = e.target.value; updateAnalyzeButton(); });
    analyzeBtn.addEventListener('click', handleAnalyze);
}

function updateAnalyzeButton() {
    const analyzeBtn = document.getElementById('analyze-btn');
    if (!analyzeBtn) return;
    const isValid = DataLoader.validateTeamSelection(AppState.homeTeam, AppState.awayTeam);
    analyzeBtn.disabled = !isValid;
    if (AppState.homeTeam && AppState.awayTeam && AppState.homeTeam === AppState.awayTeam) {
        analyzeBtn.textContent = '⚠️ SELECCIONA EQUIPOS DIFERENTES';
    } else {
        analyzeBtn.innerHTML = '<span class="btn-text">ANALIZAR PARTIDO</span><span class="btn-icon">📊</span>';
        analyzeBtn.style.background = '';
    }
}

async function handleAnalyze() {
    if (AppState.isAnalyzing) return;
    const { homeTeam, awayTeam } = AppState;
    if (!DataLoader.validateTeamSelection(homeTeam, awayTeam)) return;
    try {
        AppState.isAnalyzing = true;
        UIRenderer.toggleLoading(true);
        await new Promise(resolve => setTimeout(resolve, 800));
        const analysis = Calculator.analyzeMatch(homeTeam, awayTeam);
        UIRenderer.toggleLoading(false);
        UIRenderer.renderAnalysis(analysis, homeTeam, awayTeam);
    } catch (error) {
        console.error('❌ Error:', error);
        UIRenderer.toggleLoading(false);
        UIRenderer.showError('Error al analizar: ' + error.message);
    } finally {
        AppState.isAnalyzing = false;
    }
}

window.AppState = AppState;
window.handleAnalyze = handleAnalyze;
