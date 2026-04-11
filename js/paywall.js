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

  // ═══ 1. PICK GRATUITO — siempre visible ═══
  if (pick_gratuito) {
    html += `
    <div class="pw-section">
      <div class="pw-section-header pw-free-header">
        <span class="pw-badge pw-badge-free">✅ PICK GRATUITO</span>
        <span class="pw-date">${dateStr}</span>
      </div>
      ${renderPickCard(pick_gratuito, 'free')}
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

  // ═══ Sin picks ═══
  if (!pick_gratuito && (!picks_suscripcion || picks_suscripcion.length === 0) && !pick_dia) {
    html = `
    <div class="pw-empty">
      <p>Hoy el motor no encontró picks con valor suficiente.</p>
      <p style="font-size:0.85rem;color:var(--gris);margin-top:0.5rem">No forzamos apuestas — a veces el mejor pick es no apostar.</p>
    </div>`;
  }

  container.innerHTML = html;
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
        <div class="pw-detail-label">Mercado</div>
        <div class="pw-detail-value">${pick.market || '—'} ${odds}</div>
      </div>
      <div class="pw-detail">
        <div class="pw-detail-label">Probabilidad</div>
        <div class="pw-detail-value pw-prob">${prob}</div>
      </div>
      ${ev ? `
      <div class="pw-detail">
        <div class="pw-detail-label">EV ajustado</div>
        <div class="pw-detail-value pw-ev">${ev}</div>
      </div>` : ''}
    </div>
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
        <span class="pw-goals-stat-label">EV ajustado</span>
        <span class="pw-goals-stat-value">${ev}</span>
      </span>
    </div>
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
