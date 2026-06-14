/**
 * PREDIKTOR — Dashboard frontend (arquitectura de 3 niveles)
 *
 * Maneja:
 *   1. HERO — Featured Pick del Día      (#featured-container)
 *   2. VALUE PICKS — manejado por paywall.js (#paywall-container)
 *   3. ANÁLISIS DEL DÍA                  (#analysis-container)
 *
 * Después de paywall.js termine, ocultamos #value-picks-section si quedó vacía.
 *
 * Fuentes de datos:
 *   - static/predictions/daily_picks.json          (autoritativa para fecha)
 *   - static/predictions/featured_pick_YYYY-MM-DD.json (Nivel 3)
 *   - static/predictions/analysis_YYYY-MM-DD.json     (Nivel 1)
 */

(async function dashboardInit() {

  // ── Helper: fetch con manejo de error y retry ──
  async function safeFetch(url, opts = {}) {
    try {
      const res = await fetch(url, opts);
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  // ── Cargar daily_picks.json para obtener la fecha autoritativa ──
  const daily = await safeFetch('static/predictions/daily_picks.json');
  if (!daily || !daily.date) {
    renderError('featured-container', 'No se pudo cargar el JSON diario.');
    renderError('analysis-container', 'No se pudo cargar el análisis.');
    return;
  }
  const date = daily.date;
  const todayCol = getColombiaDate();

  // ── Cargar Nivel 1 y Nivel 3 en paralelo ──
  const [featured, analysis] = await Promise.all([
    safeFetch(`static/predictions/featured_pick_${date}.json`),
    safeFetch(`static/predictions/analysis_${date}.json`),
  ]);

  // pick_gratuito viene en daily.pick_gratuito (Nivel 2)
  const pickGratuito = daily && daily.pick_gratuito;
  const analysisCount = (analysis && analysis.total_fixtures) || 0;

  // ── Renderizar Hero unificado (decide A/B/C1/C2 según contenido) ──
  renderHero(featured, pickGratuito, analysisCount, date, todayCol);

  // ── Renderizar Análisis (Nivel 1) ──
  renderAnalysis(analysis, date, todayCol);

  // ── Coordinar con paywall.js: ocultar sección Value Picks si quedó vacía ──
  // paywall.js es deferred, así que esperamos un tick.
  setTimeout(() => {
    const pwContainer = document.getElementById('paywall-container');
    if (!pwContainer) return;
    // Detectar si paywall.js renderizó cards reales (no skeletons ni mensajes vacíos)
    const hasCards = pwContainer.querySelectorAll('.pw-card, .pw-hero-card').length > 0;
    const hasMinimal = pwContainer.querySelector('.pw-minimal, .pw-empty') !== null;
    if (!hasCards && !hasMinimal) {
      // Aún sin renderizar — esperamos otro tick
      setTimeout(checkValueSection, 500);
    } else {
      checkValueSection();
    }
  }, 200);

  function checkValueSection() {
    const pwContainer = document.getElementById('paywall-container');
    const valueSection = document.getElementById('value-picks-section');
    if (!pwContainer || !valueSection) return;
    const hasRealCards = pwContainer.querySelectorAll('.pw-card:not(.pw-card-locked), .pw-hero-card').length > 0;
    const hasLockedCards = pwContainer.querySelectorAll('.pw-card-locked').length > 0;
    // Si NO hay value picks reales ni bloqueados, ocultar la sección
    if (!hasRealCards && !hasLockedCards) {
      valueSection.style.display = 'none';
    }
  }

  // ──────────────────────────────────────────────────────────────
  // RENDER: Hero unificado — decide entre 4 estados A/B/C1/C2
  // ──────────────────────────────────────────────────────────────
  // featured        — featured_pick_*.json o null
  // pickGratuito    — daily.pick_gratuito o null/undefined
  // analysisCount   — analysis.total_fixtures (para Estado C2)
  //
  // Estados:
  //   A  = pick_gratuito existe (con o sin featured value_pick coincidente)
  //   B  = pick_gratuito existe + featured statistical_only DISTINTO al pick_gratuito
  //   C1 = solo featured statistical_only, sin pick_gratuito
  //   C2 = ni featured ni pick_gratuito
  function renderHero(featured, pickGratuito, analysisCount, dataDate, todayDate) {
    const container = document.getElementById('featured-container');
    if (!container) return;

    const isStale = featured && dataDate !== todayDate;
    const stale = isStale
      ? `<div class="dash-date-warning">⚠ Datos del ${dataDate} (no es hoy)</div>` : '';

    // Compat: si tier_origin no existe (JSON viejo), asumir "value_pick"
    const tierOrigin = featured ? (featured.tier_origin || 'value_pick') : null;
    const featuredIsStatistical = featured && tierOrigin === 'statistical_only';

    // ¿El featured coincide con el pick_gratuito?
    const featuredMatchesGratuito = featured && pickGratuito
      && featured.matchup === pickGratuito.matchup;

    // Decisión de estado
    let state;
    if (!featured && !pickGratuito) {
      state = 'C2';
    } else if (featuredIsStatistical && !pickGratuito) {
      state = 'C1';
    } else if (pickGratuito && featuredIsStatistical && !featuredMatchesGratuito) {
      state = 'B';
    } else {
      state = 'A';
    }

    let html = stale;

    if (state === 'A') {
      // Card principal = pick_gratuito (si existe) o featured value_pick
      const main = pickGratuito || featured;
      html += renderMainCard(main, /*isValueBet=*/true);
    }
    else if (state === 'B') {
      // Principal = pick_gratuito (value bet)
      html += renderMainCard(pickGratuito, /*isValueBet=*/true);
      // Secundario = featured estadístico
      html += renderSecondaryCard(featured);
    }
    else if (state === 'C1') {
      // Pre-mensaje + featured estadístico como secundario
      html += `
        <div class="featured-empty featured-empty-c1">
          <div class="featured-empty-eyebrow">Hoy · Sin picks de alta confianza</div>
          <div class="featured-empty-title">Hoy no hay un pick que cumpla el estándar</div>
          <div class="featured-empty-msg">
            Analizamos los partidos del día y ninguno alcanza la probabilidad
            ni el respaldo estadístico que exigimos. Preferimos no recomendar
            antes que recomendar mal.
          </div>
          <div class="featured-empty-sub">
            Como referencia estadística, el partido con mayor probabilidad
            del modelo es:
          </div>
        </div>`;
      html += renderSecondaryCard(featured);
    }
    else {
      // C2: nada del todo
      const n = analysisCount > 0 ? analysisCount : '—';
      html += `
        <div class="featured-empty featured-empty-c2">
          <div class="featured-empty-eyebrow">Hoy · Día sin picks</div>
          <div class="featured-empty-title">Hoy ningún partido alcanza el estándar</div>
          <div class="featured-empty-msg">
            Analizamos <strong>${n}</strong> partidos. Ninguno cumple
            nuestros criterios estadísticos. Volvé mañana — no apostamos por apostar.
          </div>
          <div class="featured-empty-ctas">
            <a href="#analysis-section" class="featured-empty-cta">
              Ver análisis del día →
            </a>
            <a href="/historial.html" class="featured-empty-cta">
              Ver historial verificado →
            </a>
          </div>
        </div>`;
    }

    container.innerHTML = html;
  }

  // Card principal (Hero dorado) — Estado A y B usan esto
  function renderMainCard(pick, isValueBet) {
    const probAdj = pick.prob_adjusted != null ? pick.prob_adjusted : '—';
    const confLabel = (pick.confidence_label || 'media').replace(' ', '-');
    const probClass = `confidence-${confLabel}`;
    const confDisplay = (pick.confidence_label || 'media').toUpperCase();
    const market = pick.market || '';

    return `
      <div class="featured-card">
        <div class="featured-eyebrow">Pick destacado del día</div>
        <div class="featured-badges">
          <span class="featured-badge featured-badge-league">${escapeHtml(pick.league || '')}</span>
        </div>
        <div class="featured-matchup">${escapeHtml(pick.matchup || '')}</div>
        <div class="featured-market">
          Pick del modelo: <strong>${escapeHtml(market)}</strong>
        </div>
        <div class="featured-explainer">
          Seleccionado por su probabilidad calibrada y respaldo estadístico.
        </div>
        <div class="featured-stats">
          <div class="featured-stat">
            <div class="featured-stat-val ${probClass}">${probAdj}%</div>
            <div class="featured-stat-lbl">Probabilidad del modelo</div>
          </div>
          <div class="featured-stat">
            <div class="featured-stat-val ${probClass}">${confDisplay}</div>
            <div class="featured-stat-lbl">Confianza</div>
          </div>
        </div>
        <div class="featured-disclaimer">
          Compará en tu casa de apuestas. Apostá con responsabilidad. +18.
        </div>
      </div>`;
  }

  // Card secundaria (gris, menor) — Estado B y C1 usan esto
  function renderSecondaryCard(pick) {
    const probAdj = pick.prob_adjusted != null ? pick.prob_adjusted : '—';
    const market = pick.market || '';

    return `
      <div class="featured-card featured-card-secondary">
        <div class="featured-eyebrow featured-eyebrow-muted">
          También hoy · Alta probabilidad estadística
        </div>
        <div class="featured-badges">
          <span class="featured-badge featured-badge-league">${escapeHtml(pick.league || '')}</span>
        </div>
        <div class="featured-matchup featured-matchup-sm">${escapeHtml(pick.matchup || '')}</div>
        <div class="featured-market featured-market-sm">
          Pick del modelo: <strong>${escapeHtml(market)}</strong>
        </div>
        <div class="featured-explainer featured-explainer-sm">
          Alta probabilidad calibrada según nuestro modelo. Compará la cuota
          en tu casa de apuestas y decidí con responsabilidad.
        </div>
        <div class="featured-stats featured-stats-sm">
          <div class="featured-stat">
            <div class="featured-stat-val">${probAdj}%</div>
            <div class="featured-stat-lbl">Probabilidad del modelo</div>
          </div>
        </div>
        <a href="#analysis-section" class="featured-secondary-link">
          Ver análisis completo →
        </a>
      </div>`;
  }

  // ──────────────────────────────────────────────────────────────
  // RENDER: Análisis del Día (Nivel 1)
  // ──────────────────────────────────────────────────────────────
  function renderAnalysis(data, dataDate, todayDate) {
    const container = document.getElementById('analysis-container');
    const subtitle = document.getElementById('analysis-subtitle');
    if (!container) return;

    if (!data || !data.matches || data.matches.length === 0) {
      if (subtitle) subtitle.textContent = 'Sin partidos para analizar hoy.';
      container.innerHTML = `
        <div class="dash-error">
          Hoy no hay partidos disponibles en las ligas que cubrimos.
        </div>`;
      return;
    }

    if (subtitle) {
      subtitle.textContent = `${data.total_fixtures} partidos analizados con datos reales · ${dataDate}`;
    }

    const isStale = dataDate !== todayDate;
    const stale = isStale
      ? `<div class="dash-date-warning">⚠ Datos del ${dataDate} (no es hoy)</div>` : '';

    const rows = data.matches.map(m => {
      const p = m.probabilities || {};
      const home = clamp(p.win_home);
      const draw = clamp(p.draw);
      const away = clamp(p.win_away);
      const isNba = m.is_nba;

      const probsHtml = isNba
        ? `<div class="analysis-probs-grid" style="grid-template-columns:1fr 1fr;">
             <div class="analysis-prob-cell">
               <div class="analysis-prob-val">${home.toFixed(0)}%</div>
               <div class="analysis-prob-lbl">Local</div>
             </div>
             <div class="analysis-prob-cell">
               <div class="analysis-prob-val">${away.toFixed(0)}%</div>
               <div class="analysis-prob-lbl">Visitante</div>
             </div>
           </div>`
        : `<div class="analysis-probs-grid">
             <div class="analysis-prob-cell">
               <div class="analysis-prob-val">${home.toFixed(0)}%</div>
               <div class="analysis-prob-lbl">Local</div>
             </div>
             <div class="analysis-prob-cell">
               <div class="analysis-prob-val">${draw.toFixed(0)}%</div>
               <div class="analysis-prob-lbl">Empate</div>
             </div>
             <div class="analysis-prob-cell">
               <div class="analysis-prob-val">${away.toFixed(0)}%</div>
               <div class="analysis-prob-lbl">Visitante</div>
             </div>
           </div>`;

      const overs = [];
      if (p.over_1_5 != null) overs.push(`Over 1.5: <strong>${p.over_1_5}%</strong>`);
      if (p.over_2_5 != null) overs.push(`Over 2.5: <strong>${p.over_2_5}%</strong>`);
      const oversHtml = overs.length
        ? `<div class="analysis-overs">${overs.join(' · ')}</div>`
        : '';

      // Mini barra solo para fútbol (no tiene sentido en NBA con draw=0)
      const barHtml = isNba ? '' : `
        <div class="prob-bar" aria-label="Distribución de probabilidades">
          <div class="prob-bar-home" style="width:${home}%"></div>
          <div class="prob-bar-draw" style="width:${draw}%"></div>
          <div class="prob-bar-away" style="width:${away}%"></div>
        </div>`;

      // Generar métricas avanzadas (xG, Elo, Danger Signals) si están disponibles y no es NBA
      let advancedHtml = '';
      if (!isNba) {
          const xgHome = m.lambda_home != null ? m.lambda_home.toFixed(2) : null;
          const xgAway = m.lambda_away != null ? m.lambda_away.toFixed(2) : null;
          const eloHome = m.elo_home != null ? Math.round(m.elo_home) : null;
          const eloAway = m.elo_away != null ? Math.round(m.elo_away) : null;
          const sotHome = (m.danger && m.danger.home_sot != null) ? m.danger.home_sot.toFixed(1) : null;
          const sotAway = (m.danger && m.danger.away_sot != null) ? m.danger.away_sot.toFixed(1) : null;

          advancedHtml = `
          <div class="analysis-advanced-grid">
            <div class="advanced-metric-box">
              <div class="metric-box-title">Goles Esperados (xG)</div>
              <div class="metric-box-values">
                <span class="metric-val-home">${xgHome !== null ? xgHome : '—'}</span>
                <span class="metric-vs">vs</span>
                <span class="metric-val-away">${xgAway !== null ? xgAway : '—'}</span>
              </div>
              <div class="metric-box-label">Basado en Poisson dinámico</div>
            </div>
            
            <div class="advanced-metric-box">
              <div class="metric-box-title">Calidad Elo Rating</div>
              <div class="metric-box-values">
                <span class="metric-val-home" style="color: var(--verde);">${eloHome !== null ? eloHome : '1500'}</span>
                <span class="metric-vs">vs</span>
                <span class="metric-val-away" style="color: var(--verde);">${eloAway !== null ? eloAway : '1500'}</span>
              </div>
              <div class="metric-box-label">Puntaje de fuerza dinámico</div>
            </div>
            
            <div class="advanced-metric-box">
              <div class="metric-box-title">Tiros a Puerta (Prom. L5)</div>
              <div class="metric-box-values">
                <span class="metric-val-home">${sotHome !== null ? sotHome : '—'}</span>
                <span class="metric-vs">vs</span>
                <span class="metric-val-away">${sotAway !== null ? sotAway : '—'}</span>
              </div>
              <div class="metric-box-label">Indicador de peligro reciente</div>
            </div>
          </div>`;
      }

      const marketExplorerHtml = renderMarketExplorer(m.markets_explored);

      return `
      <details class="analysis-row">
        <summary class="analysis-summary">
          <div class="analysis-summary-content">
            <div class="analysis-summary-matchup">${escapeHtml(m.matchup || '')}</div>
            <div class="analysis-summary-league">${escapeHtml(m.league || '')}</div>
            ${barHtml}
          </div>
          <span class="analysis-summary-icon" aria-hidden="true">▸</span>
        </summary>
        <div class="analysis-details">
          ${probsHtml}
          ${oversHtml}
          <div class="analysis-favorite">Favorito estadístico: <strong>${escapeHtml(m.favorite || '—')}</strong></div>
          ${advancedHtml}
          ${marketExplorerHtml}
        </div>
      </details>`;
    }).join('');

    container.innerHTML = `${stale}<div class="analysis-list">${rows}</div>`;
  }

  // ──────────────────────────────────────────────────────────────
  // Helpers
  // ──────────────────────────────────────────────────────────────

  function getColombiaDate() {
    // Hora Colombia = UTC-5 (sin DST)
    const now = new Date();
    const utcMs = now.getTime() + (now.getTimezoneOffset() * 60_000);
    const colDate = new Date(utcMs - 5 * 3_600_000);
    return colDate.toISOString().slice(0, 10);
  }

  function clamp(n) {
    if (n == null || isNaN(n)) return 0;
    return Math.max(0, Math.min(100, Number(n)));
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }

  function renderMarketExplorer(markets) {
    if (!markets) return '';

    const available = Array.isArray(markets.available) ? markets.available : [];
    const unavailable = Array.isArray(markets.unavailable) ? markets.unavailable : [];
    const topMarkets = available.slice(0, 8);

    const cards = topMarkets.map(item => {
      const prob = item.prob_adjusted != null && !isNaN(Number(item.prob_adjusted))
        ? `${Number(item.prob_adjusted).toFixed(1)}%`
        : '—';
      const isCandidate = Boolean(item.official_pick_candidate);
      const cardClass = isCandidate
        ? 'market-line-card market-line-card-candidate'
        : 'market-line-card';
      const badge = isCandidate
        ? '<span class="market-line-badge market-line-badge-candidate">Candidato</span>'
        : '<span class="market-line-badge">Explorada</span>';

      return `
        <div class="${cardClass}">
          <div class="market-line-head">
            <span class="market-line-type">${escapeHtml(marketTypeLabel(item.market_key))}</span>
            ${badge}
          </div>
          <div class="market-line-name">${escapeHtml(item.market || 'Línea sin nombre')}</div>
          <div class="market-line-meta">
            <span>${prob}</span>
            <span>${escapeHtml(sourceLabel(item.source))}</span>
          </div>
        </div>`;
    }).join('');

    const unavailableHtml = unavailable.slice(0, 3).map(item => `
      <div class="market-line-unavailable">
        <span>${escapeHtml(unavailableGroupLabel(item.group))}</span>
        <small>${escapeHtml(item.reason || 'Sin datos suficientes')}</small>
      </div>
    `).join('');

    if (!cards && !unavailableHtml) return '';

    return `
      <section class="market-explorer" aria-label="Líneas exploradas">
        <div class="market-explorer-title">Líneas exploradas</div>
        ${cards ? `<div class="market-lines-grid">${cards}</div>` : ''}
        ${unavailableHtml ? `<div class="market-lines-unavailable">${unavailableHtml}</div>` : ''}
      </section>`;
  }

  function marketTypeLabel(key) {
    const labels = {
      over15: 'Goles',
      over25: 'Goles',
      corners: 'Corners',
      match_corners: 'Corners',
      team_corners: 'Corners equipo',
      shots: 'Tiros a puerta',
      match_sot: 'Tiros a puerta',
      team_shots: 'Tiros equipo',
      team_sot: 'Tiros equipo',
      player_sot: 'Tiros jugador',
      player_shots: 'Tiros jugador'
    };
    return labels[key] || 'Mercado';
  }

  function sourceLabel(source) {
    const labels = {
      model_goals: 'Modelo goles',
      model_danger: 'Datos de peligro',
      player_fixture_stats: 'API jugadores',
      api_football_fixture_players: 'API jugadores',
      api_football_fixture_statistics: 'API estadísticas',
      api_football: 'API-Football'
    };
    return labels[source] || source || 'Modelo';
  }

  function unavailableGroupLabel(group) {
    const labels = {
      football_props: 'Props fútbol',
      corners: 'Corners',
      shots: 'Tiros',
      players: 'Jugadores',
      player_shots: 'Tiros de jugadores',
      api_football_markets: 'API-Football',
      corners_shots_players: 'Corners, tiros y jugadores'
    };
    return labels[group] || group || 'Mercados sin datos';
  }

  function renderError(containerId, msg) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `
      <div class="dash-error">
        ${escapeHtml(msg)}
        <br>
        <button class="dash-error-btn" onclick="location.reload()">Reintentar</button>
      </div>`;
  }
})();
