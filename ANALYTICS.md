# Analítica — Google Analytics 4 (PREDIKTOR)

Stack: **sitio estático** (HTML + JS vanilla) servido en Vercel. **No es Next.js**,
así que NO hay `lib/analytics.ts`, `NEXT_PUBLIC_GA_ID` ni "layout". El tag de GA4
se carga inline en el `<head>` de cada página.

- **ID de medición:** `G-K3JES4SQS9`
- **Dominio real de producción:** `https://prediktorcol.com` (¡ojo! NO `prediktorcon.com`)

## ⚠️ Lo que hay que arreglar EN EL PANEL DE GA4 (no es código)

El motivo más probable de "0 tráfico / conversiones en 0" **no está en el código**,
sino en la configuración de GA4. Hay que entrar a
[analytics.google.com](https://analytics.google.com) → **Admin → Flujos de datos**
y verificar:

1. **El flujo de datos apunta al dominio real.** Si el flujo está configurado para
   el dominio de *staging* de Vercel
   (`predicator-...vercel.app`) o para `prediktorcon.com` (dominio que **no existe**;
   el real es `prediktorco**l**.com`), GA no asocia el tráfico real. Edita la URL del
   flujo a `https://prediktorcol.com`.
2. **Eventos como conversiones.** Marca como "evento clave/conversión" los eventos de
   negocio (`cta_clicked`, `plan_pro_viewed`, `form_submit`, etc.) en
   Admin → Eventos / Eventos clave. Por defecto cuentan 0 hasta que se marcan.
3. **Filtros de tráfico interno.** Revisa que un filtro de IP interna no esté
   excluyendo todo el tráfico.

> El código solo dispara los eventos; **que se registren y cuenten como conversión
> depende de esta configuración en el panel.**

## Qué hace el código (ya implementado)

- **Tag GA4 en TODAS las páginas** públicas (se añadió a `privacy.html` y
  `contacto.html`, que no lo tenían). Las páginas de predicción generadas por
  `scrapers/generate_predictions.py` lo incluyen vía la constante `GA`.
- **Helper `js/analytics.js`** (incluido en todas las páginas con
  `<script src="/js/analytics.js" defer></script>`). Expone `window.PrediktorAnalytics`
  y auto-cablea eventos. Nunca rompe la página si `gtag` no cargó.

### Eventos

| Evento | Cuándo se dispara | Cómo |
|---|---|---|
| `prediction_viewed` | al renderizar los picks del día | `paywall.js` → `trackPredictionViewed` |
| `prediction_clicked` | click en una card de pick | auto (cards con `data-pick`) |
| `plan_pro_viewed` | carga de `/plan-pro.html` | auto (por `location.pathname`) |
| `cta_clicked` | click en un CTA | auto (clases `.btn-primary`, `.bookie-btn`, `.pw-telegram-btn`, `.cta-action`, `.featured-empty-cta`, o `[data-track-cta]`) |
| `form_submit` | submit de cualquier `<form>` | auto (listener global) |
| `signup_started` / `login_success` | — | helper listo, **sin cablear**: el sitio aún no tiene auth real |

### Uso manual desde cualquier script

```js
window.PrediktorAnalytics.trackEvent('mi_evento', { foo: 'bar' });
window.PrediktorAnalytics.trackCtaClicked({ label: 'Suscribirme' });
```

Para marcar un elemento como CTA con etiqueta propia, añade `data-track-cta="Etiqueta"`.
Para que una card cuente su identidad en `prediction_clicked`, añade `data-pick`,
`data-league`, `data-market`.

## Verificar que funciona

1. Abre el sitio con la extensión **GA Debug** o DevTools → Network → filtra `collect`.
2. Realtime en GA4 → debe verse tu sesión y los eventos al navegar/hacer click.
3. El ID está hardcodeado inline (intencional en sitio estático). No hay `.env`.
