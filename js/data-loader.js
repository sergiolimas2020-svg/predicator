/**
 * DATA LOADER MODULE
 * Responsable de cargar y gestionar los datos desde el JSON
 */

const DataLoader = {
    data: null,
    metadata: null,
    currentLeague: 'italy',
    
    // Configuración de ligas disponibles
    leagues: {
        'england': {
            name: 'Premier League',
            country: 'Inglaterra',
            flag: 'flag-england',
            file: 'england_stats.json'
        },
        'spain': {
            name: 'La Liga',
            country: 'España',
            flag: 'flag-spain',
            file: 'spain_stats.json'
        },
        'germany': {
            name: 'Bundesliga',
            country: 'Alemania',
            flag: 'flag-germany',
            file: 'germany_stats.json'
        },
        'italy': {
            name: 'Serie A',
            country: 'Italia',
            flag: 'flag-italy',
            file: 'italy_stats.json'
        },
        'france': {
            name: 'Ligue 1',
            country: 'Francia',
            flag: 'flag-france',
            file: 'france_stats.json'
        },
        'argentina': {
            name: 'Liga Profesional',
            country: 'Argentina',
            flag: 'flag-argentina',
            file: 'argentina_stats.json'
        },
        'brazil': {
            name: 'Campeonato Brasileño',
            country: 'Brasil',
            flag: 'flag-brazil',
            file: 'brazil_stats.json'
        },
        'colombia': {
            name: 'Liga Colombiana',
            country: 'Colombia',
            flag: 'flag-colombia',
            file: 'colombia_stats.json'
        },
        'turkey': {
            name: 'Super Lig',
            country: 'Turquía',
            flag: 'flag-turkey',
            file: 'turkey_stats.json'
        },
        'uefa-champions-league': {
            name: 'Champions League',
            country: 'UEFA',
            flag: 'flag-uefa',
            file: 'uefa-champions-league_stats.json'
        }
    },

    /**
     * Carga los datos del archivo JSON de una liga específica
     * @param {string} league - Código de la liga (england, spain, germany, italy, france)
     * @returns {Promise<Object>} Datos cargados
     */
    async loadData(league = 'italy') {
        try {
            this.currentLeague = league;
            const leagueConfig = this.leagues[league];
            
            if (!leagueConfig) {
                throw new Error(`Liga no soportada: ${league}`);
            }
            
            const fileName = leagueConfig.file;
            const response = await fetch(`/static/${fileName}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const jsonData = await response.json();
            
            // Separar metadata del resto de datos
            this.metadata = jsonData._metadata;
            delete jsonData._metadata;
            
            // Filtrar equipos válidos (que tengan datos de posición)
            this.data = {};
            Object.keys(jsonData).forEach(team => {
                if (jsonData[team].position && Object.keys(jsonData[team].position).length > 0) {
                    this.data[team] = jsonData[team];
                }
            });
            
            console.log(`✅ Datos de ${leagueConfig.name} cargados:`, {
                liga: leagueConfig.name,
                equipos: Object.keys(this.data).length,
                metadata: this.metadata
            });
            
            return this.data;
            
        } catch (error) {
            console.error('❌ Error cargando datos:', error);
            throw error;
        }
    },

    /**
     * Obtiene la configuración de una liga
     * @param {string} league - Código de la liga
     * @returns {Object} Configuración de la liga
     */
    getLeagueConfig(league) {
        return this.leagues[league] || null;
    },

    /**
     * Obtiene la configuración de la liga actual
     * @returns {Object} Configuración de la liga actual
     */
    getCurrentLeagueConfig() {
        return this.leagues[this.currentLeague];
    },

    /**
     * Obtiene la lista de equipos disponibles
     * @returns {Array<string>} Lista de nombres de equipos
     */
    getTeamsList() {
        if (!this.data) {
            console.warn('⚠️ Datos no cargados aún');
            return [];
        }
        
        return Object.keys(this.data)
            .filter(team => team !== 'League average')
            .sort();
    },

    /**
     * Obtiene los datos de un equipo específico
     * @param {string} teamName - Nombre del equipo
     * @returns {Object|null} Datos del equipo
     */
    getTeamData(teamName) {
        if (!this.data || !this.data[teamName]) {
            console.warn(`⚠️ Equipo no encontrado: ${teamName}`);
            return null;
        }
        
        return this.data[teamName];
    },

    /**
     * Obtiene estadísticas de un equipo en casa
     * @param {string} teamName - Nombre del equipo
     * @returns {Object} Estadísticas como local
     */
    getHomeStats(teamName) {
        const team = this.getTeamData(teamName);
        if (!team) return null;

        // Si tiene estructura local/visitante, úsala; si no, transforma la estructura simple
        let corners = team.corners?.local || {};
        
        if (!corners.corners_favor && team.corners) {
            // Transformar promedio a corners_favor/corners_contra
            const promedio = parseInt(team.corners.promedio) || 0;
            const partidos = parseInt(team.corners.partidos) || 1;
            corners = {
                corners_favor: promedio,
                corners_contra: promedio,
                partidos: partidos,
                promedio: promedio
            };
        }

        return {
            corners: corners,
            goals: team.goals || {},
            position: team.position || {}
        };
    },

    /**
     * Obtiene estadísticas de un equipo fuera de casa
     * @param {string} teamName - Nombre del equipo
     * @returns {Object} Estadísticas como visitante
     */
    getAwayStats(teamName) {
        const team = this.getTeamData(teamName);
        if (!team) return null;

        // Si tiene estructura local/visitante, úsala; si no, transforma la estructura simple
        let corners = team.corners?.visitante || {};
        
        if (!corners.corners_favor && team.corners) {
            // Transformar promedio a corners_favor/corners_contra
            const promedio = parseInt(team.corners.promedio) || 0;
            const partidos = parseInt(team.corners.partidos) || 1;
            corners = {
                corners_favor: promedio,
                corners_contra: promedio,
                partidos: partidos,
                promedio: promedio
            };
        }

        return {
            corners: corners,
            goals: team.goals || {},
            position: team.position || {}
        };
    },

    /**
     * Obtiene el promedio de la liga
     * @returns {Object} Estadísticas promedio
     */
    getLeagueAverage() {
        return this.data['League average'] || null;
    },

    /**
     * Obtiene la metadata del archivo
     * @returns {Object} Metadata
     */
    getMetadata() {
        return this.metadata;
    },

    /**
     * Convierte un porcentaje string a número
     * @param {string} percentStr - Porcentaje como string (ej: "75%")
     * @returns {number} Porcentaje como número (ej: 75)
     */
    parsePercentage(percentStr) {
        if (!percentStr || percentStr === 'N/A') return 0;
        return parseFloat(percentStr.replace('%', ''));
    },

    /**
     * Valida que los equipos seleccionados sean diferentes
     * @param {string} homeTeam - Equipo local
     * @param {string} awayTeam - Equipo visitante
     * @returns {boolean} True si son válidos
     */
    validateTeamSelection(homeTeam, awayTeam) {
        if (!homeTeam || !awayTeam) {
            return false;
        }
        
        if (homeTeam === awayTeam) {
            console.warn('⚠️ No se puede seleccionar el mismo equipo para local y visitante');
            return false;
        }
        
        return true;
    }
};

// Exportar para uso global
window.DataLoader = DataLoader;
