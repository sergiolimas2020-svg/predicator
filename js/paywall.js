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
    const res = await fetch('static/predictions/daily_picks.json');
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
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

function renderPaywall(data) {
  const container = document.getElementById('paywall-container');
  const { pick_gratuito, picks_suscripcion, pick_dia, analisis_goles } = data;
  const dateStr = data.date || '—';

  let html = '';

  // ═══ 1. PICK GRATUITO — HERO ═══
  //     Solo se renderiza acá si NO existe Featured Pick. Con Featured
  //     Pick activo, el Hero principal del sitio es ése (dashboard.js)
  //     y mostramos el pick gratuito como card normal abajo (sección 2).
  if (pick_gratuito && !data._has_featured) {
    html += `
    <div class="pw-hero">
      <div class="pw-hero-badge">✅ PICK GRATUITO DEL DÍA</div>
      <div class="pw-hero-date">${dateStr}</div>
      ${renderHeroCard(pick_gratuito)}
      <div class="pw-hero-telegram">
        <p>📲 Este mismo pick se publica gratis en nuestro canal de Telegram</p>
        <a href="https://t.me/prediktorcol" target="_blank" rel="noopener" class="pw-hero-telegram-btn">
          Seguirnos en Telegram
        </a>
      </div>
    </div>`;
  }

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

// ── Bloque de transparencia Betplay (aditivo, opcional) ──
// Se muestra solo si el pick tiene los campos cuota_betplay_estimada
// y ev_betplay_estimado generados por _betplay_fields() en el motor.
function renderBetplaySection(pick) {
  if (pick.cuota_betplay_estimada == null && pick.ev_betplay_estimado == null) return '';
  const cuotaBp = pick.cuota_betplay_estimada != null ? pick.cuota_betplay_estimada.toFixed(2) : '—';
  const evBp    = pick.ev_betplay_estimado != null
    ? `${pick.ev_betplay_estimado >= 0 ? '+' : ''}${pick.ev_betplay_estimado.toFixed(1)}%`
    : '—';
  return `
    <div class="pw-betplay">
      <div class="pw-betplay-title">Estimado en Betplay (descuento ~10%)</div>
      <div class="pw-betplay-grid">
        <div class="pw-betplay-stat"><span class="pw-betplay-label">Cuota estimada</span><span class="pw-betplay-value">${cuotaBp}</span></div>
        <div class="pw-betplay-stat"><span class="pw-betplay-label">EV estimado</span><span class="pw-betplay-value">${evBp}</span></div>
      </div>
      <div class="pw-betplay-note">⚠️ Verifica la cuota real en tu casa antes de apostar.</div>
    </div>`;
}

// ── Card completa (desbloqueada) ──
function renderPickCard(pick, tier) {
  const icon = (pick.league || '').includes('NBA') ? '🏀' : '⚽';
  const odds = pick.bk_odds ? `@${pick.bk_odds}` : '';
  const prob = pick.prob_adjusted ? `${Math.round(pick.prob_adjusted)}%` : '—';
  const ev = pick.ev_adjusted ? `${pick.ev_adjusted.toFixed(1)}%` : null;
  const tierClass = tier === 'premium' ? 'pw-card-premium' : tier === 'subscription' ? 'pw-card-sub' : 'pw-card-free';

  return `
  <div class="pw-card ${tierClass}">
    <div class="pw-card-league">${icon} ${pick.league || '—'}</div>
    <div class="pw-card-matchup">${pick.matchup || '—'}</div>
    <div class="pw-card-details">
      <div class="pw-detail">
        <div class="pw-detail-label">Mercado <small>(referencia europea)</small></div>
        <div class="pw-detail-value">${pick.market || '—'} ${odds}</div>
      </div>
      <div class="pw-detail">
        <div class="pw-detail-label">Probabilidad</div>
        <div class="pw-detail-value pw-prob">${prob}</div>
      </div>
      ${ev ? `
      <div class="pw-detail">
        <div class="pw-detail-label">EV ajustado <small>(referencia)</small></div>
        <div class="pw-detail-value pw-ev">${ev}</div>
      </div>` : ''}
    </div>
    ${renderBetplaySection(pick)}
  </div>`;
}

// ── Hero card: pick gratuito destacado ──
function renderHeroCard(pick) {
  const icon = (pick.league || '').includes('NBA') ? '🏀' : '⚽';
  const odds = pick.bk_odds ? pick.bk_odds : '—';
  const prob = pick.prob_adjusted ? `${Math.round(pick.prob_adjusted)}%` : '—';
  const ev = pick.ev_adjusted != null ? `+${pick.ev_adjusted.toFixed(1)}%` : null;

  return `
  <div class="pw-hero-card">
    <div class="pw-hero-league">${icon} ${pick.league || '—'}</div>
    <div class="pw-hero-matchup">${pick.matchup || '—'}</div>
    <div class="pw-hero-market">${pick.market || '—'}</div>
    <div class="pw-hero-stats">
      <div class="pw-hero-stat">
        <div class="pw-hero-stat-label">Cuota <small>(europeo)</small></div>
        <div class="pw-hero-stat-value pw-hero-odds">${odds}</div>
      </div>
      <div class="pw-hero-stat">
        <div class="pw-hero-stat-label">Probabilidad</div>
        <div class="pw-hero-stat-value pw-hero-prob">${prob}</div>
      </div>
      ${ev ? `
      <div class="pw-hero-stat">
        <div class="pw-hero-stat-label">EV <small>(referencia)</small></div>
        <div class="pw-hero-stat-value pw-hero-ev">${ev}</div>
      </div>` : ''}
    </div>
    ${renderBetplaySection(pick)}
  </div>`;
}

// ── Card de análisis de goles (informativo, no es pick) ──
function renderGoalsAnalysisCard(item) {
  const odds = item.bk_odds ? `@${item.bk_odds}` : '';
  const prob = item.prob_adjusted ? `${Math.round(item.prob_adjusted)}%` : '—';
  const ev = item.ev_adjusted != null ? `+${item.ev_adjusted.toFixed(1)}%` : '—';

  return `
  <div class="pw-goals-card">
    <div class="pw-goals-league">${item.league || '—'}</div>
    <div class="pw-goals-matchup">${item.matchup || '—'}</div>
    <div class="pw-goals-market">${item.market || '—'} ${odds}</div>
    <div class="pw-goals-stats">
      <span class="pw-goals-stat">
        <span class="pw-goals-stat-label">Probabilidad</span>
        <span class="pw-goals-stat-value">${prob}</span>
      </span>
      <span class="pw-goals-stat">
        <span class="pw-goals-stat-label">EV <small>(ref)</small></span>
        <span class="pw-goals-stat-value">${ev}</span>
      </span>
    </div>
    ${renderBetplaySection(item)}
    <div class="pw-goals-note">Análisis estadístico — no es pick oficial</div>
  </div>`;
}

// ── Card bloqueada (teaser) ──
function renderLockedCard(pick, tier) {
  const icon = (pick.league || '').includes('NBA') ? '🏀' : '⚽';
  const lockClass = tier === 'premium' ? 'pw-locked-premium' : 'pw-locked-sub';

  return `
  <div class="pw-card pw-card-locked ${lockClass}">
    <div class="pw-card-league">${icon} ${pick.league || '—'}</div>
    <div class="pw-card-matchup">${pick.matchup || '—'}</div>
    <div class="pw-card-details pw-blurred">
      <div class="pw-detail">
        <div class="pw-detail-label">Mercado</div>
        <div class="pw-detail-value">████████</div>
      </div>
      <div class="pw-detail">
        <div class="pw-detail-label">Probabilidad</div>
        <div class="pw-detail-value">██%</div>
      </div>
      <div class="pw-detail">
        <div class="pw-detail-label">Cuota</div>
        <div class="pw-detail-value">█.██</div>
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
      <span>2 a 4 picks con mercado, cuota y probabilidad completos</span>
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
