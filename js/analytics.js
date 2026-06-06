/**
 * PREDIKTOR — Helper de Google Analytics 4 (GA4)
 * ----------------------------------------------
 * Sitio ESTÁTICO (HTML + JS vanilla), NO Next.js. El tag de GA4 se carga inline
 * en el <head> de cada página (gtag.js con id G-K3JES4SQS9). Este archivo NO
 * instala el tag: añade una capa consistente y tipada (JSDoc) para disparar
 * eventos del negocio, y auto-cablea los más comunes.
 *
 * Inclúyelo en cada página con:  <script src="/js/analytics.js" defer></script>
 *
 * IMPORTANTE: el ID de medición (G-K3JES4SQS9) y, sobre todo, el dominio del
 * "flujo de datos" se configuran en GA4 (analytics.google.com → Admin → Flujos
 * de datos). Si ese flujo apunta a un dominio que no es el real
 * (https://prediktorcol.com), GA NO registra tráfico aunque el tag esté bien.
 * Eso se corrige en el panel de GA4, no en el código.
 */
(function () {
  'use strict';

  var GA_ID = 'G-K3JES4SQS9';

  /**
   * Dispara un evento de GA4 de forma segura (no-op si gtag no está cargado).
   * @param {string} eventName  nombre del evento (snake_case)
   * @param {Object<string, any>} [params]  parámetros del evento
   */
  function trackEvent(eventName, params) {
    try {
      if (typeof window !== 'undefined' && typeof window.gtag === 'function') {
        window.gtag('event', eventName, params || {});
      } else if (window && window.dataLayer) {
        // Fallback: encola hasta que gtag esté disponible.
        window.dataLayer.push(['event', eventName, params || {}]);
      }
    } catch (e) { /* nunca romper la página por analytics */ }
  }

  // ── Eventos del negocio (envoltorios tipados) ──────────────────────────
  /** @param {{slug?:string, league?:string, market?:string, count?:number}} [p] */
  function trackPredictionViewed(p) { trackEvent('prediction_viewed', p); }
  /** @param {{slug?:string, league?:string, market?:string}} [p] */
  function trackPredictionClicked(p) { trackEvent('prediction_clicked', p); }
  function trackPlanProViewed(p) { trackEvent('plan_pro_viewed', p); }
  /** @param {{label?:string, location?:string, href?:string}} [p] */
  function trackCtaClicked(p) { trackEvent('cta_clicked', p); }
  function trackFormSubmit(p) { trackEvent('form_submit', p); }
  function trackSignupStarted(p) { trackEvent('signup_started', p); }
  function trackLoginSuccess(p) { trackEvent('login_success', p); }

  // ── Auto-cableado ──────────────────────────────────────────────────────
  // Selectores de CTA existentes en el sitio (clases reales) + opt-in genérico.
  var CTA_SELECTOR = [
    '[data-track-cta]', '.btn-primary', '.bookie-btn', '.pw-telegram-btn',
    '.cta-action', '.featured-empty-cta', '.plan-cta', '.btn-cta'
  ].join(',');
  // Selectores de "card" de predicción (incluye los que renderiza paywall.js).
  var PICK_SELECTOR = '[data-pick], .pw-card, .pw-hero, .featured-hero';

  function labelOf(el) {
    return (el.getAttribute('data-track-cta') ||
            (el.textContent || '').trim().slice(0, 60) ||
            el.getAttribute('aria-label') || 'cta');
  }

  function onClick(ev) {
    var t = ev.target;
    if (!t || !t.closest) return;
    var pick = t.closest(PICK_SELECTOR);
    if (pick) {
      trackPredictionClicked({
        slug: pick.getAttribute('data-pick') || undefined,
        league: pick.getAttribute('data-league') || undefined,
        market: pick.getAttribute('data-market') || undefined
      });
      return;
    }
    var cta = t.closest(CTA_SELECTOR);
    if (cta) {
      trackCtaClicked({
        label: labelOf(cta),
        href: cta.getAttribute('href') || undefined,
        location: location.pathname
      });
    }
  }

  function init() {
    // Click delegado (funciona con cards inyectadas dinámicamente por paywall.js)
    document.addEventListener('click', onClick, true);

    // form_submit en TODOS los formularios
    document.addEventListener('submit', function (ev) {
      var form = ev.target;
      trackFormSubmit({
        form_id: (form && (form.id || form.getAttribute('name'))) || 'form',
        location: location.pathname
      });
    }, true);

    // plan_pro_viewed al cargar la página de Plan Pro
    if (/plan-pro/i.test(location.pathname)) {
      trackPlanProViewed({ page: location.pathname });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Exponer la API para uso manual desde otros scripts (p.ej. paywall.js).
  window.PrediktorAnalytics = {
    GA_ID: GA_ID,
    trackEvent: trackEvent,
    trackPredictionViewed: trackPredictionViewed,
    trackPredictionClicked: trackPredictionClicked,
    trackPlanProViewed: trackPlanProViewed,
    trackCtaClicked: trackCtaClicked,
    trackFormSubmit: trackFormSubmit,
    trackSignupStarted: trackSignupStarted,
    trackLoginSuccess: trackLoginSuccess
  };
})();
