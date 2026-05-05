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

  // ── Renderizar Hero (Nivel 3) ──
  renderFeatured(featured, date, todayCol);

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
  // RENDER: Featured Pick (Hero — Nivel 3)
  // ──────────────────────────────────────────────────────────────
  function renderFeatured(data, dataDate, todayDate) {
    const container = document.getElementById('featured-container');
    if (!container) return;

    if (!data) {
      // No hay featured_pick.json hoy → mensaje elegante
      container.innerHTML = `
        <div class="featured-empty">
          <div class="featured-empty-title">Hoy no hay pick destacado</div>
          <div class="featured-empty-msg">
            Ningún partido del día tiene confianza estadística suficiente
            (umbral mínimo 55%). Mañana volvemos con análisis completo.
          </div>
        </div>`;
      return;
    }

    const isStale = dataDate !== todayDate;
    const stale = isStale
      ? `<div class="dash-date-warning">⚠ Datos del ${dataDate} (no es hoy)</div>` : '';

    const isValuePick = data.tier_origin === 'value_pick';
    const probClass = `confidence-${data.confidence_label.replace(' ', '-').replace('media-alta', 'media-alta')}`;

    container.innerHTML = `
      ${stale}
      <div class="featured-card">
        <div class="featured-badges">
          <span class="featured-badge featured-badge-league">${escapeHtml(data.league || '')}</span>
          ${isValuePick
            ? `<span class="featured-badge featured-badge-value">⚡ VALUE BET</span>`
            : ''}
        </div>
        <div class="featured-matchup">${escapeHtml(data.matchup || '')}</div>
        <div class="featured-market">
          Mercado recomendado: <strong>${escapeHtml(data.market || '')}</strong>
        </div>
        <div class="featured-stats">
          <div class="featured-stat">
            <div class="featured-stat-val ${probClass}">${data.prob_adjusted}%</div>
            <div class="featured-stat-lbl">Probabilidad</div>
          </div>
          <div class="featured-stat">
            <div class="featured-stat-val">${data.bk_odds ? data.bk_odds.toFixed(2) : '—'}</div>
            <div class="featured-stat-lbl">Cuota europea</div>
          </div>
          <div class="featured-stat">
            <div class="featured-stat-val ${probClass}">${data.confidence_label.toUpperCase()}</div>
            <div class="featured-stat-lbl">Confianza</div>
          </div>
        </div>
        ${renderFeaturedBetplay(data)}
        <div class="featured-note">${escapeHtml(data.nota || '')}</div>
      </div>`;
  }

  // ──────────────────────────────────────────────────────────────
  // Bloque Betplay (aditivo, opcional) — solo si campos presentes
  // ──────────────────────────────────────────────────────────────
  function renderFeaturedBetplay(d) {
    if (d.cuota_betplay_estimada == null && d.ev_betplay_estimado == null) return '';
    const cuota = d.cuota_betplay_estimada != null ? d.cuota_betplay_estimada.toFixed(2) : '—';
    const ev = d.ev_betplay_estimado != null
      ? `${d.ev_betplay_estimado >= 0 ? '+' : ''}${d.ev_betplay_estimado.toFixed(1)}%`
      : '—';
    return `
        <div class="featured-betplay">
          <div class="featured-betplay-title">Estimado en Betplay (descuento ~10%)</div>
          <div class="featured-betplay-grid">
            <div class="featured-betplay-stat">
              <div class="featured-betplay-val">${cuota}</div>
              <div class="featured-betplay-lbl">Cuota estimada</div>
            </div>
            <div class="featured-betplay-stat">
              <div class="featured-betplay-val">${ev}</div>
              <div class="featured-betplay-lbl">EV estimado</div>
            </div>
          </div>
          <div class="featured-betplay-note">⚠️ Verifica la cuota real en tu casa antes de apostar.</div>
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
