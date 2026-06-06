# PREDIKTOR — Roadmap estratégico

Objetivo: producto profesional y **superar a los tipsters humanos** explotando la
ventaja de máquina (analiza todo, sin sesgos, 100% estadística).

## Restricción de producto (decidida con el dueño)
**NO mostramos cuotas.** No tenemos las cuotas reales del mercado local (BetPlay)
y las europeas no aplican. No afirmamos NADA sobre cuotas, EV vs mercado, CLV ni
"tu casa paga X". Todo se comunica por **PROBABILIDAD calibrada**. El foso de
honestidad se construye sobre probabilidad + calibración + track record, que solo
necesitan nuestras predicciones y los resultados reales.

---

## Fase 1 — Honestidad / credibilidad ✅ (hecha)
- Quitar todo claim de cuotas del sitio, del bot de Telegram y de `daily_picks.json`
  (`_betplay_fields` → no-op; cards y mensajes solo probabilidad).
- Corregir la afirmación falsa de "cuotas de cierre" en `backtest_log_real.py`.
- Unificar el track record del home a **una sola cifra verificable** (historial.json:
  58% en 110 picks); se eliminó la sección de stats.json (población distinta → 46%,
  contradictoria). Precio del hero alineado con plan-pro.

## Fase 2 — Foso anti-tipster (probabilidad, sin cuotas)
- **Calibración pública**: curva "predicho vs real" por bucket + Brier score en vivo
  (ya existe la función en backtest; falta exponerla). Ningún tipster puede mostrarlo.
- **Track record radical**: ROI/acierto por liga y mercado, drawdown, con n y fecha,
  incluyendo lo negativo. Evidencia auditable.

## Fase 3 — Edge de modelo (mejora la PROBABILIDAD, no usa cuotas)
- **Dixon-Coles** (corrige correlación de goles bajos) — mejor relación impacto/esfuerzo.
- **Normalizar ataque/defensa por liga** (hoy usa 1.35 fijo para todas).
- **Lesiones (`/injuries`) + descanso** ajustando λ (requiere 2ª corrida pre-kickoff).
- **Mercados nuevos** desde la matriz Poisson ya calculada: BTTS, hándicap asiático,
  primer tiempo, marcador exacto.
- **Ratings bayesianos** (Glicko-2 / time-decay) con incertidumbre → ajusta confianza.
- Props NBA avanzadas (mercado menos eficiente).

## Fase 4 — Producto / profesionalismo
- **Unificar diseño**: hoy coexisten ~4 sistemas (las 201 páginas de pick se ven como
  otra web). Un solo `tokens.css` (negro/dorado/DM Sans), migrar primero las páginas
  de pick (mayor superficie SEO).
- **"Por qué este pick"** en cada card (reason, prob, racha del mercado).
- **Plan Pro**: convertir los `alert('próximamente')` en captura de email; auth+pagos
  (Wompi/Mercado Pago) solo cuando la demanda lo valide (medir con GA4).
- Limpieza: email del footer al dominio real, quitar animaciones `infinite`,
  `preconnect` de fuentes en todas las páginas.

## Lo que NO perseguimos (humo / bajo ROI o depende de cuotas)
- CLV / cuotas de cierre / EV vs mercado (no tenemos cuotas fiables).
- xG propio completo (el SoT ya es buen proxy; API-Football no da xG fiable en
  CONMEBOL/Colombia, las ligas con edge).
- Clima; endpoint `/predictions` de API-Football como decisor (es un Poisson genérico).
