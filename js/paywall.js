/**
 * PREDIKTOR — Paywall Frontend
 * Lee daily_picks.json y renderiza picks con control de visibilidad.
 * No calcula, no decide — solo muestra lo que el motor generó.
 */

// ── Estado del usuario (placeholder — se conectará a auth más adelante) ──
const userState = {
  isLogged: false,
  isSubscribed: false,
  hasDayPick: false,
};

// Exponer para pruebas en consola: setUserState({isLogged:true, isSubscribed:true})
window.setUserState = function(state) {
  Object.assign(userState, state);
  if (window._lastDailyData) renderPaywall(window._lastDailyData);
};

// ── Carga y renderizado ──
async function initPaywall() {
  const container = document.getElementById('paywall-container');
  if (!container) return;

  try {
    const [res, configRes] = await Promise.all([
      fetch('static/predictions/daily_picks.json'),
      fetch('/api/public-config').catch(() => null)
    ]);
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    const config = configRes && configRes.ok ? await configRes.json() : null;
    if (shouldDelayFreeSignal(data.date, config)) {
      data._free_signal_delayed = true;
      data.pick_gratuito = null;
    }
    window._lastDailyData = data;

    // Detectar si existe Featured Pick (Nivel 3 de la arquitectura).
    // Si existe, NO renderizamos el Hero verde acá — queda solo el Hero
    // dorado del Featured Pick arriba (dashboard.js). Los picks gratuitos
    // se muestran como cards normales si no son el Hero.
    if (data.date) {
      try {
        const fres = await fetch(`static/predictions/featured_pick_${data.date}.json`);
        if (fres.ok) {
          data._has_featured = true;
        }
      } catch (_) { /* sin featured — render normal */ }
    }

    // Si no hay picks, intentar cargar contenido mínimo diario
    const hasAnyPick = data.pick_gratuito || data.pick_dia
                    || (data.picks_suscripcion && data.picks_suscripcion.length > 0)
                    || data.pick_exploratorio;
    if (!hasAnyPick) {
      try {
        const cres = await fetch('static/predictions/daily_content.json');
        if (cres.ok) {
          data._minimal_content = await cres.json();
        }
      } catch (_) { /* sin contenido mínimo — usar fallback */ }
    }

    renderPaywall(data);
  } catch (e) {
    container.innerHTML = `
      <div class="pw-empty">
        <p>El motor no ha generado picks todavía hoy.</p>
        <p style="font-size:0.85rem;color:var(--gris);margin-top:0.5rem">Los picks se publican cada mañana antes de los partidos.</p>
      </div>`;
  }
}

function shouldDelayFreeSignal(dataDate, config) {
  const hours = Number(config && config.free_signal_delay_hours);
  if (!Number.isFinite(hours) || hours <= 0) return false;
  const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' });
  if (dataDate !== today) return false;
  const nowColombia = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/Bogota' }));
  return nowColombia.getHours() < hours;
}

function renderPaywall(data) {
  const container = document.getElementById('paywall-container');
  const { pick_gratuito, picks_suscripcion, pick_dia, analisis_goles } = data;
  const dateStr = data.date || '—';

  let html = '';

  // ═══ 1. PICK GRATUITO — HERO ═══
  //     ELIMINADO: dashboard.js es ahora el único responsable del Hero
  //     principal del sitio. Maneja 4 estados (A: value bet, B: value +
  //     featured estadístico, C1: sin value, C2: sin nada) leyendo
  //     daily_picks.json y featured_pick_*.json. El paywall queda solo
  //     con cards de listado (suscripción/premium).
  //     Ver js/dashboard.js → renderHero().

  // ═══ 2. PICKS SUSCRIPCIÓN — bloqueados o visibles ═══
  if (picks_suscripcion && picks_suscripcion.length > 0) {
    const susCards = picks_suscripcion
      .filter(p => !pick_gratuito || p.slug !== pick_gratuito.slug)
      .map(p => {
        if (userState.isSubscribed) {
          return renderPickCard(p, 'subscription');
        }
        return renderLockedCard(p, 'subscription');
      }).join('');

    if (susCards) {
      html += `
      <div class="pw-section">
        <div class="pw-section-header pw-sub-header">
          <span class="pw-badge pw-badge-sub">📊 PICKS SUSCRIPCIÓN</span>
          <span class="pw-date">${picks_suscripcion.length - (pick_gratuito ? 1 : 0)} picks</span>
        </div>
        ${susCards}
        ${!userState.isSubscribed ? renderCTA('subscription') : ''}
      </div>`;
    }
  }

  // ═══ 3. PICK DEL DÍA — PREMIUM ═══
  if (pick_dia) {
    html += `
    <div class="pw-section">
      <div class="pw-section-header pw-premium-header">
        <span class="pw-badge pw-badge-premium">🔥 PICK DEL DÍA — PREMIUM</span>
        <span class="pw-date">${dateStr}</span>
      </div>
      ${userState.hasDayPick ? renderPickCard(pick_dia, 'premium') : renderLockedCard(pick_dia, 'premium')}
      ${!userState.hasDayPick ? renderCTA('premium') : ''}
    </div>`;
  }

  // ═══ 4. ANÁLISIS DE GOLES — informativo, no es pick ═══
  if (analisis_goles && analisis_goles.length > 0) {
    const goalsCards = analisis_goles.map(g => renderGoalsAnalysisCard(g)).join('');
    html += `
    <div class="pw-section pw-section-goals">
      <div class="pw-section-header pw-goals-header">
        <span class="pw-badge pw-badge-goals">📊 ANÁLISIS DE GOLES (INFORMATIVO)</span>
        <span class="pw-date">${analisis_goles.length} ${analisis_goles.length === 1 ? 'mercado' : 'mercados'}</span>
      </div>
      <div class="pw-goals-intro">
        Mercados de goles con valor estadístico detectado. No son picks oficiales —
        son insights complementarios para análisis.
      </div>
      ${goalsCards}
    </div>`;
  }

  // ═══ Sin picks — mostrar contenido mínimo diario ═══
  if (!pick_gratuito && (!picks_suscripcion || picks_suscripcion.length === 0) && !pick_dia) {
    html = renderMinimalContent(data._minimal_content, dateStr);
  }

  container.innerHTML = html;

  // GA4: registrar que se vieron las predicciones del día (cuántas y de qué tipo).
  try {
    var nSub = (picks_suscripcion && picks_suscripcion.length) || 0;
    var nGoals = (analisis_goles && analisis_goles.length) || 0;
    if (window.PrediktorAnalytics) {
      window.PrediktorAnalytics.trackPredictionViewed({
        count: nSub + (pick_dia ? 1 : 0),
        subscription_picks: nSub,
        goals_markets: nGoals,
        date: dateStr
      });
    }
  } catch (e) { /* analytics nunca rompe el render */ }
}

// ── Contenido mínimo diario (cuando no hay picks de valor) ──
function renderMinimalContent(content, dateStr) {
  // Sin contenido mínimo → fallback al mensaje genérico
  if (!content) {
    return `
    <div class="pw-empty">
      <p>Hoy el motor no encontró picks con valor suficiente.</p>
      <p style="font-size:0.85rem;color:var(--gris);margin-top:0.5rem">No forzamos apuestas — a veces el mejor pick es no apostar.</p>
    </div>`;
  }

  const icon = content.icon || '📝';
  const title = content.title || 'Información del día';
  const body = content.body || '';

  // Convertir saltos de línea a <br> y <b> tags del body (viene de Python)
  const bodyHtml = body
    .replace(/<b>/g, '<strong>')
    .replace(/<\/b>/g, '</strong>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');

  return `
  <div class="pw-minimal">
    <div class="pw-minimal-header">
      <span class="pw-minimal-badge">${icon} ${title.toUpperCase()}</span>
      <span class="pw-date">${dateStr}</span>
    </div>
    <div class="pw-minimal-body"><p>${bodyHtml}</p></div>
    <div class="pw-minimal-footer">
      <span>🔔 Volvemos a publicar picks cuando haya valor real</span>
    </div>
  </div>`;
}

// NOTA: PREDIKTOR no muestra cuotas. No disponemos de las cuotas reales del
// mercado local (BetPlay), así que NO afirmamos nada sobre cuotas/EV. Cada pick
// se presenta solo con su PROBABILIDAD calibrada y su mercado. El usuario
// compara la cuota en su casa de apuestas.

// ── Card completa (desbloqueada) ──
function renderPickCard(pick, tier) {
  const icon = (pick.league || '').includes('NBA') ? '🏀' : (pick.league || '').includes('Mundial') ? '🏆' : '⚽';
  const prob = pick.prob_adjusted ? `${Math.round(pick.prob_adjusted)}%` : '—';
  const tierClass = tier === 'premium' ? 'pw-card-premium' : tier === 'subscription' ? 'pw-card-sub' : 'pw-card-free';

  return `
  <div class="pw-card ${tierClass}" data-pick="${pick.slug || ''}" data-league="${pick.league || ''}" data-market="${pick.market || ''}">
    <div class="pw-card-league">${icon} ${pick.league || '—'}</div>
    <div class="pw-card-matchup">${pick.matchup || '—'}</div>
    <div class="pw-card-details">
      <div class="pw-detail">
        <div class="pw-detail-label">Pick</div>
        <div class="pw-detail-value">${pick.market || '—'}</div>
      </div>
      <div class="pw-detail">
        <div class="pw-detail-label">Probabilidad del modelo</div>
        <div class="pw-detail-value pw-prob">${prob}</div>
      </div>
    </div>
  </div>`;
}

// ── Hero card: pick gratuito destacado ──
function renderHeroCard(pick) {
  const icon = (pick.league || '').includes('NBA') ? '🏀' : (pick.league || '').includes('Mundial') ? '🏆' : '⚽';
  const prob = pick.prob_adjusted ? `${Math.round(pick.prob_adjusted)}%` : '—';

  return `
  <div class="pw-hero-card" data-pick="${pick.slug || ''}" data-league="${pick.league || ''}" data-market="${pick.market || ''}">
    <div class="pw-hero-league">${icon} ${pick.league || '—'}</div>
    <div class="pw-hero-matchup">${pick.matchup || '—'}</div>
    <div class="pw-hero-market">${pick.market || '—'}</div>
    <div class="pw-hero-stats">
      <div class="pw-hero-stat">
        <div class="pw-hero-stat-label">Probabilidad del modelo</div>
        <div class="pw-hero-stat-value pw-hero-prob">${prob}</div>
      </div>
    </div>
  </div>`;
}

// ── Card de análisis de goles (informativo, no es pick) ──
function renderGoalsAnalysisCard(item) {
  const prob = item.prob_adjusted ? `${Math.round(item.prob_adjusted)}%` : '—';

  return `
  <div class="pw-goals-card">
    <div class="pw-goals-league">${item.league || '—'}</div>
    <div class="pw-goals-matchup">${item.matchup || '—'}</div>
    <div class="pw-goals-market">${item.market || '—'}</div>
    <div class="pw-goals-stats">
      <span class="pw-goals-stat">
        <span class="pw-goals-stat-label">Probabilidad del modelo</span>
        <span class="pw-goals-stat-value">${prob}</span>
      </span>
    </div>
    <div class="pw-goals-note">Análisis estadístico — no es pick oficial</div>
  </div>`;
}

// ── Card bloqueada (teaser) ──
function renderLockedCard(pick, tier) {
  const icon = (pick.league || '').includes('NBA') ? '🏀' : (pick.league || '').includes('Mundial') ? '🏆' : '⚽';
  const lockClass = tier === 'premium' ? 'pw-locked-premium' : 'pw-locked-sub';
  const market = pick.market || pick.prediction || pick.pick || 'Mercado disponible';

  return `
  <div class="pw-card pw-card-locked ${lockClass}">
    <div class="pw-card-league">${icon} ${pick.league || '—'}</div>
    <div class="pw-card-matchup">${pick.matchup || '—'}</div>
    <div class="pw-card-details">
      <div class="pw-detail">
        <div class="pw-detail-label">Mercado</div>
        <div class="pw-detail-value">${market}</div>
      </div>
      <div class="pw-detail">
        <div class="pw-detail-label">Probabilidad</div>
        <div class="pw-detail-value">Disponible con acceso</div>
      </div>
      <div class="pw-detail">
        <div class="pw-detail-label">Confianza</div>
        <div class="pw-detail-value">Reservada</div>
      </div>
    </div>
    <div class="pw-lock-overlay">
      <span class="pw-lock-icon">🔒</span>
      <span>${tier === 'premium' ? 'Contenido premium' : 'Solo suscriptores'}</span>
    </div>
  </div>`;
}

// ── CTA botones ──
function renderCTA(tier) {
  const telegramUrl = 'https://t.me/prediktorcol';

  if (tier === 'premium') {
    return `
    <div class="pw-cta pw-cta-premium">
      <div class="pw-cta-text">
        <strong>Desbloquea el Pick del Día</strong>
        <span>El pick con mayor valor esperado, analizado por el motor</span>
      </div>
      <a href="#" class="pw-cta-btn pw-cta-btn-premium" onclick="alert('Pagos próximamente');return false;">
        💎 Desbloquear — próximamente
      </a>
    </div>
    <div class="pw-telegram">
      <div class="pw-telegram-text">
        <strong>El Pick del Día se adelanta en nuestro canal</strong>
        <span>Síguenos en Telegram para no perderte las oportunidades</span>
      </div>
      <a href="${telegramUrl}" target="_blank" rel="noopener" class="pw-telegram-btn">🔥 Ir a Telegram</a>
    </div>`;
  }
  return `
  <div class="pw-cta pw-cta-sub">
    <div class="pw-cta-text">
      <strong>Accede a todos los picks diarios</strong>
      <span>2 a 4 picks con mercado y probabilidad calibrada del modelo</span>
    </div>
    <a href="#" class="pw-cta-btn pw-cta-btn-sub" onclick="alert('Suscripción próximamente');return false;">
      📊 Suscribirse — próximamente
    </a>
  </div>
  <div class="pw-telegram">
    <div class="pw-telegram-text">
      <strong>¿Quieres ver picks diarios reales?</strong>
      <span>Únete gratis a nuestro canal de Telegram</span>
    </div>
    <a href="${telegramUrl}" target="_blank" rel="noopener" class="pw-telegram-btn">📣 Ver picks en Telegram</a>
  </div>`;
}

// ── Iniciar al cargar ──
document.addEventListener('DOMContentLoaded', initPaywall);
