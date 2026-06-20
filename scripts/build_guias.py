#!/usr/bin/env python3
"""
Genera las guías nuevas de /guias/ con la plantilla exacta del sitio (System A,
head SEO + JSON-LD, nav/footer con rutas limpias). Solo se autoriza el contenido
único de cada artículo; el shell garantiza consistencia visual y de metadata.

Uso: python3 scripts/build_guias.py
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "guias"

STYLE = """
  <style>
    :root {
      --negro:#0a0a0f; --oscuro:#111118; --card:#16161f; --card2:#1c1c28;
      --borde:#2a2a3a; --dorado:#f0b429; --dorado2:#c9900a;
      --verde:#22c55e; --rojo:#ef4444; --azul:#3b82f6;
      --texto:#e2e8f0; --gris:#94a3b8;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body { font-family:'DM Sans',sans-serif; background:var(--negro); color:var(--texto); line-height:1.7; }
    nav {
      display:flex; justify-content:space-between; align-items:center;
      padding:1.2rem 2rem; border-bottom:1px solid var(--borde);
      position:sticky; top:0; background:rgba(10,10,15,0.96);
      backdrop-filter:blur(12px); z-index:100;
    }
    .logo { font-family:'Bebas Neue',sans-serif; font-size:1.8rem; letter-spacing:3px; color:var(--texto); text-decoration:none; }
    .logo span { color:var(--dorado); }
    .nav-links { display:flex; gap:1.5rem; align-items:center; flex-wrap:wrap; }
    .nav-links a { color:var(--gris); text-decoration:none; font-size:0.9rem; font-weight:500; transition:color 0.2s; }
    .nav-links a:hover, .nav-links a.active { color:var(--dorado); }
    article { max-width:820px; margin:3rem auto; padding:0 1.5rem 5rem; }
    .breadcrumb { font-size:0.8rem; color:var(--gris); margin-bottom:1.5rem; letter-spacing:1px; text-transform:uppercase; }
    .breadcrumb a { color:var(--dorado); text-decoration:none; }
    h1 { font-family:'Bebas Neue',sans-serif; font-size:clamp(2.4rem,6vw,3.8rem); line-height:1.05; letter-spacing:1px; margin-bottom:1rem; color:#fff; }
    h1 span { color:var(--dorado); }
    .subtitle { font-size:1.1rem; color:var(--gris); margin-bottom:2.5rem; max-width:680px; }
    h2 { font-family:'Bebas Neue',sans-serif; font-size:clamp(1.7rem,3.5vw,2.4rem); letter-spacing:1px; color:#fff; margin:3rem 0 1rem; padding-bottom:0.6rem; border-bottom:1px solid var(--borde); }
    h3 { font-size:1.25rem; font-weight:700; color:var(--dorado); margin:2rem 0 0.8rem; letter-spacing:0.5px; }
    p { margin-bottom:1.2rem; font-size:1rem; color:var(--texto); }
    p strong { color:#fff; font-weight:600; }
    a { color:var(--dorado); }
    ul, ol { margin:1rem 0 1.4rem 1.5rem; }
    li { margin-bottom:0.6rem; color:var(--texto); }
    li strong { color:#fff; }
    .formula {
      background:var(--card); border:1px solid var(--borde); border-left:3px solid var(--dorado);
      border-radius:6px; padding:1.2rem 1.4rem; margin:1.4rem 0;
      font-family:'Courier New',monospace; font-size:0.95rem; color:var(--dorado); overflow-x:auto;
    }
    .callout {
      background:rgba(240,180,41,0.05); border:1px solid rgba(240,180,41,0.2); border-left:3px solid var(--dorado);
      border-radius:6px; padding:1rem 1.3rem; margin:1.5rem 0;
    }
    .callout strong { color:var(--dorado); }
    .tip {
      background:rgba(34,197,94,0.05); border:1px solid rgba(34,197,94,0.2); border-left:3px solid var(--verde);
      border-radius:6px; padding:1rem 1.3rem; margin:1.5rem 0; font-size:0.95rem;
    }
    .tip strong { color:var(--verde); }
    table { width:100%; border-collapse:collapse; margin:1.5rem 0; background:var(--card); border:1px solid var(--borde); border-radius:6px; overflow:hidden; font-size:0.92rem; }
    th, td { padding:0.8rem 1rem; text-align:left; border-bottom:1px solid var(--borde); }
    th { background:var(--card2); color:var(--dorado); font-weight:700; font-size:0.8rem; text-transform:uppercase; letter-spacing:1px; }
    tr:last-child td { border-bottom:none; }
    .toc { background:var(--card2); border-left:3px solid var(--dorado); border-radius:6px; padding:1.2rem 1.4rem; margin:1.5rem 0 2.5rem; font-size:0.92rem; }
    .toc > ul { margin:0.5rem 0 0 1rem; }
    .toc a { color:var(--dorado); text-decoration:none; }
    .toc a:hover { text-decoration:underline; }
    .article-meta { display:flex; gap:1rem; flex-wrap:wrap; align-items:center; font-size:0.85rem; color:var(--gris); margin:0.5rem 0 2rem; }
    .article-meta span { display:inline-flex; align-items:center; gap:0.4rem; }
    .tier-badge { font-size:0.7rem; padding:0.25rem 0.7rem; border-radius:3px; letter-spacing:1.5px; text-transform:uppercase; font-weight:700; }
    .tier-1 { background:rgba(34,197,94,0.15); color:var(--verde); }
    .tier-2 { background:rgba(240,180,41,0.15); color:var(--dorado); }
    .tier-3 { background:rgba(239,68,68,0.15); color:var(--rojo); }
    footer { background:var(--oscuro); border-top:1px solid var(--borde); padding:3rem 2rem 2rem; text-align:center; }
    .footer-logo { font-family:'Bebas Neue',sans-serif; font-size:2rem; color:var(--dorado); letter-spacing:3px; margin-bottom:0.8rem; }
    .footer-desc { color:var(--gris); font-size:0.88rem; max-width:480px; margin:0 auto 1.5rem; line-height:1.7; }
    .footer-links { display:flex; justify-content:center; gap:1.5rem; margin-bottom:2rem; flex-wrap:wrap; }
    .footer-links a { color:var(--gris); text-decoration:none; font-size:0.85rem; transition:color 0.2s; }
    .footer-links a:hover { color:var(--dorado); }
    .footer-copy { color:var(--borde); font-size:0.8rem; }
    .disclaimer {
      background:rgba(240,180,41,0.04); border-top:1px solid rgba(240,180,41,0.1); border-bottom:1px solid rgba(240,180,41,0.1);
      padding:1.2rem 2rem; text-align:center; color:var(--gris); font-size:0.82rem; line-height:1.6;
    }
    @media (max-width:640px) { nav { padding:1rem; } .nav-links { gap:0.8rem; } }
  </style>
"""

NAV = """
  <nav>
    <a href="/" class="logo">PREDI<span>KTOR</span></a>
    <div class="nav-links">
      <a href="/">Inicio</a>
      <a href="/metodologia">Metodología</a>
      <a href="/glosario">Glosario</a>
      <a href="/como-usar">Cómo usar</a>
      <a href="/guias/" class="active">Guías</a>
      <a href="/historial">Historial</a>
      <a href="/sobre">Sobre</a>
    </div>
  </nav>
"""

FOOTER = """
  <div class="disclaimer">⚠️ <strong>Aviso +18:</strong> Este contenido es informativo y educativo. PREDIKTOR no es una casa de apuestas. El juego puede generar adicción; apuesta con responsabilidad y solo en operadores autorizados por Coljuegos.</div>

  <footer>
    <div class="footer-logo">PREDIKTOR</div>
    <div class="footer-desc">Sistema automatizado de análisis estadístico deportivo. Metodología abierta, datos verificables.</div>
    <div class="footer-links">
      <a href="/">Inicio</a>
      <a href="/metodologia">Metodología</a>
      <a href="/glosario">Glosario</a>
      <a href="/como-usar">Cómo usar</a>
      <a href="/guias/">Guías</a>
      <a href="/historial">Historial</a>
      <a href="/casas-autorizadas">Casas autorizadas</a>
      <a href="/sobre">Sobre</a>
      <a href="/contacto">Contacto</a>
      <a href="/privacidad">Privacidad</a>
    </div>
    <div class="footer-copy">© 2026 PREDIKTOR · contacto@prediktor.app</div>
  </footer>
"""

SHELL = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>__TITLE__</title>
  <meta name="description" content="__DESC__">
  <meta name="keywords" content="__KEYWORDS__">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="https://prediktorcol.com/guias/__SLUG__">

  <meta property="og:title" content="__OGTITLE__">
  <meta property="og:description" content="__DESC__">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://prediktorcol.com/guias/__SLUG__">
  <meta property="og:site_name" content="PREDIKTOR">
  <meta property="article:published_time" content="__DATE__">

  <script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "__HEADLINE__",
  "description": "__DESC__",
  "datePublished": "__DATE__",
  "dateModified": "__DATE__",
  "author": { "@type": "Organization", "name": "PREDIKTOR", "url": "https://prediktorcol.com" },
  "publisher": { "@type": "Organization", "name": "PREDIKTOR", "url": "https://prediktorcol.com" },
  "mainEntityOfPage": { "@type": "WebPage", "@id": "https://prediktorcol.com/guias/__SLUG__" },
  "wordCount": __WORDCOUNT__,
  "keywords": "__KEYWORDS__"
}
  </script>
  <script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Inicio", "item": "https://prediktorcol.com/" },
    { "@type": "ListItem", "position": 2, "name": "Guías", "item": "https://prediktorcol.com/guias/" },
    { "@type": "ListItem", "position": 3, "name": "__HEADLINE__", "item": "https://prediktorcol.com/guias/__SLUG__" }
  ]
}
  </script>

  <script async src="https://www.googletagmanager.com/gtag/js?id=G-K3JES4SQS9"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-K3JES4SQS9');
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
__STYLE__
</head>
<body>
__NAV__
  <article>
    <div class="breadcrumb">
      <a href="/">Inicio</a> · <a href="/guias/">Guías</a> · __BREADCRUMB__
    </div>

    <h1>__H1__</h1>
    <div class="article-meta">
      <span class="tier-badge __TIER_CLASS__">__TIER_LABEL__</span>
      <span>📅 __DATE__</span>
      <span>📖 __READMIN__ min de lectura</span>
    </div>

    <div class="toc">
__TOC__
    </div>
__BODY__
  </article>
__FOOTER__
</body>
</html>
"""

# ----------------------------------------------------------------------------
# Contenido único por guía
# ----------------------------------------------------------------------------

GUIAS = [
    {
        "slug": "gestion-de-bankroll",
        "title": "Gestión de bankroll en apuestas: la guía completa — PREDIKTOR",
        "headline": "Gestión de bankroll: cómo proteger y hacer crecer tu capital",
        "desc": "Qué es el bankroll y cómo gestionarlo: porcentaje fijo, Kelly simplificado y sistema de unidades, con ejemplos prácticos y errores a evitar.",
        "keywords": "gestion de bankroll, bankroll apuestas, sistema de unidades, kelly criterion, stake apuestas",
        "date": "2026-05-20",
        "tier_class": "tier-1", "tier_label": "Básico", "readmin": "9", "wordcount": 880,
        "h1": "Gestión de bankroll: cómo proteger y hacer crecer tu capital",
        "toc": [
            ("que-es-el-bankroll", "1. Qué es el bankroll"),
            ("por-que-es-lo-mas-importante", "2. Por qué es lo más importante"),
            ("metodos-de-gestion", "3. Métodos de gestión"),
            ("ejemplos-con-numeros", "4. Ejemplos prácticos con números"),
            ("errores-comunes", "5. Errores más comunes"),
            ("llevar-un-registro", "6. Cómo llevar un registro"),
        ],
        "body": """
<p>Podés tener el mejor modelo de predicción del mundo y aun así perder todo tu dinero. La diferencia entre un apostador que sobrevive a largo plazo y uno que quiebra rara vez está en qué tan buenas son sus predicciones: está en <strong>cómo gestiona su dinero</strong>. Esta guía explica qué es el bankroll y los tres métodos probados para administrarlo sin arruinarte en una mala racha.</p>

<h2 id="que-es-el-bankroll">1. Qué es el bankroll</h2>
<p>El <strong>bankroll</strong> es el capital total que destinás exclusivamente a apostar. Es dinero que ya separaste de tus gastos, tus ahorros y tus obligaciones, y que estás dispuesto a perder por completo sin que eso afecte tu vida. Si una apuesta perdida te quita el sueño o te toca la comida del mes, ese dinero no debería estar en juego.</p>
<p>La regla de oro es simple: tu bankroll es una cuenta separada y cerrada. No se recarga con dinero del salario después de una mala semana, y no se mezcla con la billetera del día a día. Definir esa frontera es el primer acto de disciplina financiera de cualquier apostador serio.</p>

<h2 id="por-que-es-lo-mas-importante">2. Por qué es lo más importante</h2>
<p>Las apuestas, incluso las de valor positivo, tienen una <strong>varianza brutal a corto plazo</strong>. Una apuesta con 60% de probabilidad real de ganar pierde 4 de cada 10 veces. Encadenar cinco o seis derrotas seguidas es estadísticamente normal, no mala suerte excepcional.</p>
<div class="callout">
<strong>El riesgo de ruina:</strong> si apostás una fracción demasiado grande de tu bankroll en cada jugada, una racha negociable normal puede llevarte a cero. Y desde cero no hay modelo que te recupere, porque ya no te queda capital para apostar.
</div>
<p>La gestión de bankroll existe para que ninguna racha mala te saque del juego. Mientras sigas teniendo capital, tu ventaja estadística sigue trabajando para vos a lo largo de cientos de apuestas. Quebrar es el único error verdaderamente irreversible.</p>

<h2 id="metodos-de-gestion">3. Métodos de gestión</h2>
<h3>Porcentaje fijo (flat betting)</h3>
<p>Apostás siempre el mismo porcentaje de tu bankroll <em>actual</em> en cada jugada, típicamente entre 1% y 3%. Es el método más recomendado para principiantes: simple, conservador y casi imposible de quebrar. Si ganás, tus apuestas crecen un poco; si perdés, se achican automáticamente, protegiéndote en las malas rachas.</p>
<h3>Sistema de unidades</h3>
<p>Una <strong>unidad</strong> es un porcentaje fijo de tu bankroll (por ejemplo, 1% = 1 unidad). En vez de apostar siempre lo mismo, ajustás el número de unidades según tu confianza: 1 unidad en un pick de confianza media, hasta 3 unidades en uno de confianza alta. Nunca más de 5 unidades en una sola apuesta. Es el método que mejor se alinea con los niveles de confianza que publica PREDIKTOR.</p>
<h3>Kelly Criterion simplificado</h3>
<p>El criterio de Kelly calcula el porcentaje óptimo a apostar en función de tu ventaja y la cuota. La fórmula completa es agresiva y castiga mucho los errores de estimación, por lo que casi todos los profesionales usan <strong>Kelly fraccionado</strong>: la mitad o un cuarto de lo que sugiere la fórmula. Es el método más rentable en teoría, pero también el más peligroso si sobreestimás tus probabilidades.</p>

<h2 id="ejemplos-con-numeros">4. Ejemplos prácticos con números</h2>
<p>Supongamos un bankroll de <strong>$1.000.000 COP</strong> y el sistema de unidades con 1 unidad = 1% = $10.000.</p>
<table>
<thead><tr><th>Confianza del pick</th><th>Unidades</th><th>Monto apostado</th></tr></thead>
<tbody>
<tr><td>Baja</td><td>1 unidad</td><td>$10.000</td></tr>
<tr><td>Media</td><td>2 unidades</td><td>$20.000</td></tr>
<tr><td>Alta</td><td>3 unidades</td><td>$30.000</td></tr>
</tbody>
</table>
<p>Con porcentaje fijo al 2%, si perdés 5 apuestas seguidas tu bankroll baja a ~$903.000, pero cada apuesta siguiente se recalcula sobre el nuevo total, así que el daño se frena solo. Con un apostador que mete el 25% por jugada, esas mismas 5 derrotas lo dejan en ~$237.000: un pozo del que es casi imposible volver.</p>
<div class="tip">
<strong>Conclusión:</strong> apostar pequeño no es timidez, es supervivencia. El objetivo número uno no es ganar rápido, es no quebrar nunca. Quien no quiebra deja que su ventaja estadística haga el trabajo con el tiempo.
</div>

<h2 id="errores-comunes">5. Errores más comunes</h2>
<ul>
<li><strong>Chase losses (perseguir pérdidas):</strong> duplicar las apuestas para recuperar lo perdido. Es la forma más rápida y común de quebrar. La racha mala no te debe nada.</li>
<li><strong>Apostar sin porcentaje definido:</strong> meter montos al ojo según cómo te sentís ese día. Sin una regla fija, la emoción decide por vos.</li>
<li><strong>Subir el stake tras ganar:</strong> creerte invencible después de tres aciertos y arriesgar de más justo antes de la regresión a la media.</li>
<li><strong>Mezclar el bankroll con el dinero personal:</strong> cuando la frontera se borra, las pérdidas dejan de ser controladas y empiezan a doler de verdad.</li>
</ul>

<h2 id="llevar-un-registro">6. Cómo llevar un registro</h2>
<p>No podés mejorar lo que no medís. Anotá cada apuesta con: fecha, evento, mercado, probabilidad estimada, cuota, unidades apostadas y resultado. Una simple hoja de cálculo basta. Revisá tu rendimiento cada 50-100 apuestas, nunca antes: las muestras pequeñas solo muestran ruido.</p>
<p>Ese registro te dirá la verdad que la memoria distorsiona: si realmente vas ganando, en qué mercados sos fuerte y en cuáles estás perdiendo plata. Para entender por qué el largo plazo es lo único que importa, leé nuestra guía sobre <a href="/guias/value-bets">qué son las value bets</a>, y para ver cómo aplicamos confianza a cada pick, revisá la <a href="/metodologia">metodología del modelo</a>.</p>
"""
    },
    {
        "slug": "value-bets",
        "title": "Qué son las value bets y cómo detectarlas — PREDIKTOR",
        "headline": "Value bets: la única estrategia rentable a largo plazo",
        "desc": "Qué es una value bet, cómo se calcula el valor esperado, por qué la casa siempre gana sin value y cómo PREDIKTOR detecta apuestas con valor real.",
        "keywords": "value bets, apuestas de valor, valor esperado, ev positivo, probabilidad implicita, value betting",
        "date": "2026-05-22",
        "tier_class": "tier-2", "tier_label": "Intermedio", "readmin": "9", "wordcount": 870,
        "h1": "Value bets: la única estrategia rentable a largo plazo",
        "toc": [
            ("que-es-una-value-bet", "1. Qué es una value bet"),
            ("como-calcular-el-valor", "2. Cómo calcular el valor esperado"),
            ("por-que-la-casa-gana", "3. Por qué la casa siempre gana sin value"),
            ("como-prediktor-detecta-value", "4. Cómo PREDIKTOR detecta value"),
            ("ejemplos-value-vs-no-value", "5. Ejemplos: value vs apuesta sin valor"),
            ("el-largo-plazo", "6. Por qué el value a largo plazo es lo único sostenible"),
        ],
        "body": """
<p>Casi todos los apostadores piensan en términos de "quién va a ganar". Los apostadores rentables piensan en términos de <strong>valor</strong>: no apuestan al equipo más probable, sino al que la casa está pagando por encima de su probabilidad real. Esa diferencia de mentalidad es lo que separa a quien gana a largo plazo de quien dona su dinero lentamente.</p>

<h2 id="que-es-una-value-bet">1. Qué es una value bet</h2>
<p>Una <strong>value bet</strong> (apuesta de valor) es aquella en la que la probabilidad real de que ocurra un resultado es <em>mayor</em> que la probabilidad que implica la cuota ofrecida por la casa. Cuando eso pasa, la cuota está "sobrepagada" y, a largo plazo, apostarla deja ganancia.</p>
<p>La clave es que el value no depende de si la apuesta gana o pierde una vez. Depende de si el precio que te ofrecen es bueno respecto a la probabilidad verdadera. Apostar a un favorito puede no tener valor si la cuota es ridículamente baja, y apostar a un underdog puede tener un valor enorme si la cuota es alta.</p>

<h2 id="como-calcular-el-valor">2. Cómo calcular el valor esperado</h2>
<p>El valor esperado (EV) se calcula con una fórmula simple:</p>
<div class="formula">EV = (probabilidad real × cuota) − 1</div>
<p>Si el resultado es positivo, hay valor. Si es negativo, no lo hay. También podés usar el atajo de la <strong>probabilidad implícita</strong> de una cuota:</p>
<div class="formula">Probabilidad implícita = 1 / cuota</div>
<p>Si tu estimación de probabilidad real supera la probabilidad implícita de la cuota, tenés una value bet. Profundizamos en estas cuentas, con tablas y ejemplos, en la guía <a href="/guias/que-es-ev-apuestas">qué es el EV en apuestas</a>.</p>

<h2 id="por-que-la-casa-gana">3. Por qué la casa siempre gana sin value</h2>
<p>Las casas de apuestas no ganan adivinando resultados: ganan aplicando un <strong>margen</strong> (el "juice" o "vig") a cada mercado. Si un partido es una moneda al aire 50/50, la cuota justa sería 2.00 para cada lado. Pero la casa ofrece 1.90 y 1.90: ese recorte es su comisión garantizada.</p>
<div class="callout">
<strong>El margen en cifras:</strong> las casas colombianas suelen tener márgenes del 12-15%, mucho más altos que los de operadores europeos como Pinnacle (2-3%). Eso significa que, jugando "al azar", el apostador promedio pierde estructuralmente. La única forma de revertirlo es encontrar cuotas con valor a pesar del margen.
</div>
<p>Por eso el 95% de los apostadores pierde a largo plazo: no porque fallen sus pronósticos, sino porque pagan el margen una y otra vez sin buscar nunca valor.</p>

<h2 id="como-prediktor-detecta-value">4. Cómo PREDIKTOR detecta value</h2>
<p>PREDIKTOR estima la probabilidad real de cada resultado con un modelo estadístico que combina un modelo de Poisson para goles con variables de rendimiento: forma reciente, goles esperados, rendimiento local y visitante, posición en la tabla y enfrentamientos directos. Esa probabilidad propia es independiente de la cuota.</p>
<p>El sistema aplica además un <strong>factor de confianza</strong> que reduce la probabilidad estimada cuando los datos de una liga son escasos o el mercado es de alta varianza. El resultado es una probabilidad conservadora que evita los falsos positivos típicos de los modelos demasiado optimistas. Podés ver el detalle completo en la <a href="/metodologia">metodología</a>.</p>

<h2 id="ejemplos-value-vs-no-value">5. Ejemplos: value vs apuesta sin valor</h2>
<table>
<thead><tr><th>Caso</th><th>Prob. real</th><th>Cuota</th><th>EV</th><th>¿Value?</th></tr></thead>
<tbody>
<tr><td>Favorito sobrevalorado</td><td>70%</td><td>1.30</td><td>−0.09</td><td>No</td></tr>
<tr><td>Favorito con valor</td><td>55%</td><td>2.10</td><td>+0.155</td><td>Sí</td></tr>
<tr><td>Underdog con valor</td><td>30%</td><td>4.00</td><td>+0.20</td><td>Sí</td></tr>
<tr><td>Underdog trampa</td><td>20%</td><td>3.40</td><td>−0.32</td><td>No</td></tr>
</tbody>
</table>
<p>Fijate que el favorito al 70% es <strong>mala apuesta</strong> porque la cuota 1.30 implica 77% y tu probabilidad real es menor. En cambio, el underdog al 30% con cuota 4.00 es excelente: la cuota implica solo 25%. El resultado puntual puede ir en cualquier dirección; el valor está en el precio.</p>

<h2 id="el-largo-plazo">6. Por qué el value a largo plazo es lo único sostenible</h2>
<p>Una value bet puede perder. Diez seguidas pueden perder. El valor no es una promesa sobre la próxima apuesta, sino una ventaja matemática que se materializa a lo largo de cientos de jugadas, igual que la ventaja de la casa se materializa sobre miles de clientes.</p>
<p>Por eso el value betting solo funciona acompañado de dos cosas: <strong>disciplina de bankroll</strong> para sobrevivir la varianza, y <strong>paciencia</strong> para no abandonar el método en la primera mala racha. Si querés la otra mitad de la ecuación, leé nuestra guía de <a href="/guias/gestion-de-bankroll">gestión de bankroll</a>, y revisá el <a href="/historial">historial verificable</a> para ver cómo se comporta el enfoque con el tiempo.</p>
"""
    },
    {
        "slug": "estadisticas-futbol",
        "title": "Estadísticas de fútbol que sí predicen resultados — PREDIKTOR",
        "headline": "Estadísticas de fútbol: las variables que de verdad predicen",
        "desc": "xG, posesión vs efectividad, estadísticas defensivas, factor localía y forma reciente: qué métricas del fútbol moderno predicen resultados y cómo combinarlas.",
        "keywords": "estadisticas futbol, xg goles esperados, factor localia, forma reciente, xga clean sheets, analisis estadistico futbol",
        "date": "2026-05-24",
        "tier_class": "tier-2", "tier_label": "Intermedio", "readmin": "10", "wordcount": 900,
        "h1": "Estadísticas de fútbol: las variables que de verdad predicen",
        "toc": [
            ("el-futbol-moderno", "1. El fútbol moderno es estadística"),
            ("xg-goles-esperados", "2. xG: goles esperados"),
            ("posesion-vs-efectividad", "3. Posesión vs efectividad"),
            ("estadisticas-defensivas", "4. Estadísticas defensivas"),
            ("factor-localia", "5. Factor localía"),
            ("forma-vs-temporada", "6. Forma reciente vs temporada"),
            ("combinar-variables", "7. Cómo combinar variables"),
        ],
        "body": """
<p>Durante décadas, el fútbol se analizó con el ojo y la corazonada. Hoy, los clubes de élite y los apostadores serios usan datos que predicen mucho mejor que la intuición. Pero no todas las estadísticas valen lo mismo: algunas son ruido vistoso y otras son señales reales. Esta guía separa unas de otras.</p>

<h2 id="el-futbol-moderno">1. El fútbol moderno es estadística</h2>
<p>El marcador final de un partido es una muestra minúscula: un 1-0 puede esconder un dominio aplastante o un robo afortunado. Las estadísticas avanzadas existen para mirar <strong>debajo del resultado</strong> y medir qué tan bien jugó realmente cada equipo, más allá de la suerte puntual de un rebote o un error arbitral.</p>
<p>La idea central es distinguir <strong>proceso</strong> de <strong>resultado</strong>. Un equipo puede merecer ganar y perder; otro puede jugar mal y llevarse tres puntos. A largo plazo, el proceso (las buenas métricas) predice mejor los resultados futuros que los resultados pasados.</p>

<h2 id="xg-goles-esperados">2. xG: goles esperados</h2>
<p>El <strong>xG (expected goals, o goles esperados)</strong> mide la calidad de las ocasiones de gol. Cada remate recibe un valor entre 0 y 1 según la probabilidad histórica de que un disparo desde esa posición y situación termine en gol. Un penalti vale ~0.76 xG; un remate lejano y forzado, 0.03.</p>
<div class="callout">
<strong>Por qué importa:</strong> si un equipo gana 1-0 pero generó 0.4 xG y su rival 2.1 xG, los números dicen que el resultado fue afortunado y difícilmente se repita. El xG es uno de los predictores individuales más potentes del rendimiento futuro.
</div>
<p>El xG acumulado a lo largo de varias jornadas revela qué equipos están "robando" puntos (sobre-rendimiento que tiende a corregirse) y cuáles merecen más de lo que la tabla muestra.</p>

<h2 id="posesion-vs-efectividad">3. Posesión vs efectividad</h2>
<p>La posesión es la estadística más sobrevalorada del fútbol. Tener el 65% del balón no predice casi nada por sí solo: hay equipos que dominan la pelota sin generar peligro y otros que ceden la posesión y matan al contragolpe.</p>
<p>Lo que importa no es cuánto tenés la pelota, sino <strong>qué hacés con ella</strong>: remates por partido, toques en el área rival, xG generado. Un equipo con 45% de posesión pero alta efectividad ofensiva es mucho más peligroso que uno con 65% estéril.</p>

<h2 id="estadisticas-defensivas">4. Estadísticas defensivas</h2>
<p>La defensa gana campeonatos, y los datos lo confirman. Las métricas defensivas clave son:</p>
<ul>
<li><strong>Goles concedidos:</strong> el dato básico, pero ruidoso a corto plazo.</li>
<li><strong>xGA (xG en contra):</strong> la calidad de las ocasiones que un equipo permite. Predice mejor que los goles concedidos crudos.</li>
<li><strong>Clean sheets (vallas invictas):</strong> partidos sin recibir gol. Un indicador de solidez y un mercado interesante en sí mismo.</li>
</ul>
<p>Un equipo con bajo xGA es estructuralmente sólido aunque haya recibido goles por mala suerte o errores puntuales que tienden a no repetirse.</p>

<h2 id="factor-localia">5. Factor localía</h2>
<p>Jugar de local es una ventaja real y medible. Históricamente, los equipos locales ganan entre el 45% y el 50% de los partidos, frente a un 25-30% de los visitantes. La ventaja proviene del público, la familiaridad con el campo y la ausencia de viaje.</p>
<p>Pero la localía no pesa igual en todas las ligas ni para todos los equipos. En el fútbol colombiano, con viajes largos y altitudes muy distintas (de Bogotá a la costa), el factor cancha puede ser más fuerte que en ligas compactas. Un buen modelo ajusta la localía por liga y por equipo, no con un valor único.</p>

<h2 id="forma-vs-temporada">6. Forma reciente vs temporada</h2>
<p>¿Qué pesa más: cómo viene un equipo en los últimos 5 partidos o su rendimiento de toda la temporada? La respuesta honesta es: <strong>ambas, ponderadas</strong>. La forma reciente capta lesiones, cambios de técnico y momento anímico; el rendimiento de temporada capta el nivel real del plantel.</p>
<p>Confiar solo en la forma reciente te hace sobrerreaccionar a rachas de 3 partidos que muchas veces son puro azar. Confiar solo en la temporada te hace ignorar que un equipo perdió a su goleador. El equilibrio entre ambas es donde está la señal.</p>

<h2 id="combinar-variables">7. Cómo combinar variables</h2>
<p>Ninguna estadística aislada predice bien. La fuerza está en <strong>combinarlas con la ponderación correcta</strong>: xG ofensivo y defensivo, forma reciente, localía ajustada por liga, posición en la tabla y enfrentamientos directos. Eso es exactamente lo que hace un modelo estadístico, y es imposible de replicar a ojo de forma consistente.</p>
<p>PREDIKTOR integra estas variables en un modelo que produce una probabilidad para cada resultado, calibrada contra resultados históricos. Si querés ver cómo se traduce todo esto en un pick concreto, leé la <a href="/metodologia">metodología completa</a> o aprendé a interpretarlos en la guía de <a href="/como-usar">cómo usar PREDIKTOR</a>.</p>
"""
    },
]


def build_toc(items):
    lis = "\n".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in items)
    return f"<ul>\n{lis}\n</ul>"


def render(g):
    html = SHELL
    repl = {
        "__TITLE__": g["title"],
        "__DESC__": g["desc"],
        "__KEYWORDS__": g["keywords"],
        "__SLUG__": g["slug"],
        "__OGTITLE__": g["headline"],
        "__DATE__": g["date"],
        "__WORDCOUNT__": str(g["wordcount"]),
        "__HEADLINE__": g["headline"],
        "__H1__": g["h1"],
        "__BREADCRUMB__": g["headline"],
        "__TIER_CLASS__": g["tier_class"],
        "__TIER_LABEL__": g["tier_label"],
        "__READMIN__": g["readmin"],
        "__TOC__": build_toc(g["toc"]),
        "__BODY__": g["body"].strip(),
        "__STYLE__": STYLE,
        "__NAV__": NAV,
        "__FOOTER__": FOOTER,
    }
    for k, v in repl.items():
        html = html.replace(k, v)
    return html


def main() -> int:
    for g in GUIAS:
        out = OUT / f"{g['slug']}.html"
        out.write_text(render(g), encoding="utf-8")
        print(f"  escrito: guias/{g['slug']}.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
