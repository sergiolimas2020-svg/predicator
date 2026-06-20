const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const QUERY_LOG_PATH = path.join(process.cwd(), "static", "ai_chat_queries.log");
const VIP_COOKIE_NAME = "prediktor_vip";
const CHAT_USAGE_COOKIE_NAME = "prediktor_ai_free_count";
const FREE_CHAT_LIMIT = 3;
const FREE_CHAT_MAX_AGE = 60 * 60 * 24 * 365;

const SUPPORTED_MARKETS = [
  "Over corners del partido",
  "Over corners por equipo",
  "Over tiros a puerta por equipo",
  "Over remates totales de jugador",
  "Over tiros a puerta de jugador",
  "Ganador",
  "DNB / apuesta sin empate",
  "Doble oportunidad",
  "Over 1.5 goles",
  "Gol de equipo en primera mitad"
];

const UNSUPPORTED_MARKETS = [
  "Tarjetas",
  "Faltas",
  "Offsides",
  "Posesion",
  "Goles de jugador",
  "Asistencias",
  "Cuotas y EV real"
];

const QUESTION_ALIASES = [
  [/\bholanda\b/g, "netherlands"],
  [/\bpaises bajos\b/g, "netherlands"],
  [/\bpaíses bajos\b/g, "netherlands"],
  [/\bsuecia\b/g, "sweden"],
  [/\becuadro\b/g, "ecuador"],
  [/\becuador\b/g, "ecuador"],
  [/\bcurazao\b/g, "curacao"],
  [/\bcuraçao\b/g, "curacao"],
  [/\bjapon\b/g, "japan"],
  [/\balemania\b/g, "germany"],
  [/\bmarfil\b/g, "ivory coast"],
  [/\bcosta de marfil\b/g, "ivory coast"],
  [/\btunez\b/g, "tunisia"],
  [/\btúnez\b/g, "tunisia"],
  [/\bmexico\b/g, "mexico"],
  [/\bméxico\b/g, "mexico"],
  [/\bsudafrica\b/g, "south africa"],
  [/\bsudáfrica\b/g, "south africa"],
  [/\batletico nacional\b/g, "atletico nacional"],
  [/\bnacional\b/g, "atletico nacional"],
  [/\bjunior\b/g, "junior"],
  [/\braul jimenez\b/g, "raul jimenez"],
  [/\braúl jiménez\b/g, "raul jimenez"],
  [/\bisaak\b/g, "isak"],
  [/\bgoykeres\b/g, "gyokeres"],
  [/\bgyokeres\b/g, "gyokeres"],
  [/\bmessi\b/g, "lionel messi"],
  [/\bcristiano\b/g, "cristiano ronaldo"],
  [/\bcr7\b/g, "cristiano ronaldo"]
];

function readJson(relativePath) {
  try {
    return JSON.parse(fs.readFileSync(path.join(process.cwd(), relativePath), "utf8"));
  } catch (_) {
    return null;
  }
}

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function normalizeQuestion(question) {
  return QUESTION_ALIASES.reduce((text, [pattern, replacement]) => {
    return text.replace(pattern, replacement);
  }, normalize(question));
}

function appendQueryLog(entry) {
  try {
    fs.mkdirSync(path.dirname(QUERY_LOG_PATH), { recursive: true });
    fs.appendFileSync(QUERY_LOG_PATH, `${JSON.stringify(entry)}\n`, "utf8");
  } catch (_) {
    // Logging is observability only; never block a user answer.
  }
}

function readCookie(header, name) {
  return String(header || "")
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

function sessionToken() {
  const password = process.env.VIP_PASSWORD;
  const secret = process.env.VIP_SESSION_SECRET || "prediktor-vip-v1";
  if (!password) return null;
  return crypto.createHash("sha256").update(`${password}:${secret}`).digest("hex");
}

function isProRequest(req) {
  const expected = sessionToken();
  if (!expected) return false;
  return readCookie(req.headers.cookie, VIP_COOKIE_NAME) === expected;
}

function readFreeChatCount(req) {
  const value = Number(readCookie(req.headers.cookie, CHAT_USAGE_COOKIE_NAME));
  return Number.isFinite(value) && value > 0 ? Math.floor(value) : 0;
}

function setFreeChatCount(res, count) {
  const safeCount = Math.max(0, Math.min(999, Number(count) || 0));
  res.setHeader(
    "Set-Cookie",
    `${CHAT_USAGE_COOKIE_NAME}=${safeCount}; Path=/; Max-Age=${FREE_CHAT_MAX_AGE}; Secure; SameSite=Lax`
  );
}

function pct(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(1)}%` : "s/d";
}

function verdictFromProbability(prob) {
  const p = Number(prob);
  if (!Number.isFinite(p)) return { verdict: "SIN DATO", label: "Dato insuficiente" };
  if (p >= 60) return { verdict: "SI", label: "La estadistica acompana" };
  if (p >= 52) return { verdict: "JUSTO", label: "Hay inclinacion, pero no margen claro" };
  return { verdict: "NO", label: "La estadistica no acompana" };
}

function poissonOverProbability(lambda, line) {
  const lam = Number(lambda);
  const parsedLine = Number(line);
  if (!Number.isFinite(lam) || !Number.isFinite(parsedLine) || lam < 0) return null;
  const minHits = Math.floor(parsedLine) + 1;
  let term = Math.exp(-lam);
  let cdf = term;
  for (let k = 1; k < minHits; k += 1) {
    term *= lam / k;
    cdf += term;
  }
  return Math.max(0, Math.min(100, (1 - cdf) * 100));
}

function idealOverLine(lambda, minConfidence = 60) {
  const lam = Number(lambda);
  if (!Number.isFinite(lam) || lam <= 0) return null;
  let best = null;
  const maxLine = Math.max(0.5, Math.ceil(lam + 8) + 0.5);
  for (let line = 0.5; line <= maxLine; line += 1) {
    const confidence = poissonOverProbability(lam, line);
    if (Number.isFinite(confidence) && confidence >= minConfidence) {
      best = { line, confidence };
    }
  }
  return best;
}

function extractOverLine(question) {
  const text = String(question || "").toLowerCase().replace(/,/g, ".");
  const explicit = text.match(/(?:over|mas de|más de|\+)\s*(?:de\s*)?(\d+(?:\.\d+)?)/i);
  if (explicit) return Number(explicit[1]);
  return null;
}

function unitsForProbability(prob, passed, marketDisabled, unsupportedMarket) {
  const p = Number(prob);
  if (marketDisabled || unsupportedMarket || !Number.isFinite(p)) {
    return {
      stake: "0u",
      label: "Sin stake",
      reason: "no hay estadistica suficiente para publicar una senal."
    };
  }
  if (!passed) {
    return {
      stake: "0u a 0.25u",
      label: "Observacion",
      reason: "no supera el umbral del modelo; solo tendria sentido como seguimiento, no como pick principal."
    };
  }
  if (p >= 90) {
    return {
      stake: "0.75u",
      label: "Stake moderado",
      reason: "probabilidad muy alta, pero sin cuota no se puede confirmar EV."
    };
  }
  if (p >= 80) {
    return {
      stake: "0.50u",
      label: "Stake bajo-moderado",
      reason: "supera con margen el umbral estadistico."
    };
  }
  return {
    stake: "0.25u",
    label: "Stake bajo",
    reason: "supera el umbral, pero el margen no justifica subir exposicion."
  };
}

function detectMarket(question) {
  const q = normalizeQuestion(question);
  const firstHalf = /\bprimer tiempo\b|\bprimera mitad\b|\b1t\b|\bpt\b/.test(q);
  const teamGoal = /\bgol\b|\bmarque\b|\banote\b|\bhaga un gol\b/.test(q);
  const shotText = /\btiros?\b|\bremates?\b|\bpatea\b|\bpatean\b|\bdisparos?\b|\bshots?\b/.test(q);
  const onTargetText = /\bal arco\b|\ba puerta\b|\bporteria\b|\bsot\b|\bon target\b/.test(q);
  const playerText = /\bjugador\b|\bjugadores\b|\bfutbolista\b|\bdelantero\b|\bgoleador\b/.test(q);
  const asksUnsupportedMarket = /\btarjetas?\b|\bcards?\b|\bamarillas?\b|\brojas?\b|\boffsides?\b|\bfueras de lugar\b|\bfaltas?\b|\bposesion\b|\basistencias?\b|\bpasses?\b|\bpases?\b/.test(q);
  const asksPlayerGoal = teamGoal && (playerText || /\bde\b\s+[a-z]{3,}/.test(q)) && !/\bvs\b|\bentre\b|\bpartido\b|\bequipo\b/.test(q);
  const looksLikePlayerProp = shotText && /\bde\b\s+[a-z]{3,}/.test(q) && !/\bvs\b|\bentre\b|\bpartido\b|\btotal\b|\bambos\b/.test(q);

  if (asksUnsupportedMarket || asksPlayerGoal) {
    return {
      key: "unsupported_market",
      label: asksPlayerGoal ? "Gol de jugador" : "Mercado no soportado",
      unsupported: true
    };
  }

  if (shotText && (playerText || looksLikePlayerProp || /\bquien\b.*\bpatea\b|\bpatea\b.*\bmas\b/.test(q))) {
    return {
      key: "player_shots",
      label: onTargetText ? "Tiros a puerta de jugador" : "Tiros de jugador",
      apiFootball: true
    };
  }
  if (shotText && onTargetText) {
    return {
      key: "team_shots_on_target",
      label: "Tiros a puerta de equipo",
      apiFootball: true
    };
  }

  if (/\bcorners?\b|\btiros de esquina\b/.test(q)) {
    return { key: "corners", label: "Corners", disabledKey: "corners", apiFootball: true };
  }
  if (/\bover 2 5\b|\bmas de 2 5\b|\b\+2 5\b/.test(q)) {
    return { key: "over_2_5", label: "Over 2.5 goles", disabledKey: "over_2_5" };
  }
  if (/\bover 1 5\b|\bmas de 1 5\b|\b\+1 5\b/.test(q)) {
    return { key: "over_1_5", label: "Over 1.5 goles", disabledKey: "over_1_5" };
  }
  if (/\bdnb\b|\bsin empate\b|\bempate no accion\b/.test(q)) {
    return { key: "draw_no_bet", label: "DNB / apuesta sin empate", disabledKey: "draw_no_bet" };
  }
  if (/\bdoble oportunidad\b|\bdc\b/.test(q)) {
    return { key: "double_chance", label: "Doble oportunidad", disabledKey: "double_chance" };
  }
  if (firstHalf && teamGoal) {
    return {
      key: "team_goal_first_half",
      label: "Gol de equipo en primera mitad",
      unsupported: true,
      firstHalf: true
    };
  }
  if (teamGoal) {
    return {
      key: "team_goal",
      label: "Gol de equipo",
      unsupported: true
    };
  }
  if (/\bgana\b|\bganador\b|\bvictoria\b|\bml\b/.test(q)) {
    return { key: "winner", label: "Victoria directa", disabledKey: "winner" };
  }
  return { key: "general", label: "Lectura general" };
}

function marketMatches(market, detected) {
  const name = normalize(market && market.market);
  if (detected.key === "over_1_5") return name.includes("over 1 5");
  if (detected.key === "over_2_5") return name.includes("over 2 5");
  if (detected.key === "winner") return name.includes("victoria");
  if (detected.key === "draw_no_bet") return name.includes("dnb") || name.includes("apuesta sin empate");
  if (detected.key === "double_chance") return name.includes("doble oportunidad");
  if (detected.key === "corners") return name.includes("corner");
  return false;
}

function findMatch(question, radar) {
  const q = normalizeQuestion(question);
  const matches = Array.isArray(radar && radar.matches) ? radar.matches : [];
  let best = null;
  let bestScore = 0;

  matches.forEach((match) => {
    const words = normalizeQuestion(`${match.match} ${match.home} ${match.away}`)
      .split(" ")
      .filter((word) => word.length > 3);
    const score = words.reduce((total, word) => total + (q.includes(word) ? 1 : 0), 0);
    if (score > bestScore) {
      best = match;
      bestScore = score;
    }
  });

  return bestScore > 0 ? best : null;
}

function readApiFootballRecords() {
  const dir = path.join(process.cwd(), "static/api_football/data");
  try {
    return fs.readdirSync(dir)
      .filter((file) => file.endsWith(".json"))
      .sort()
      .reverse()
      .flatMap((file) => {
        try {
          const records = JSON.parse(fs.readFileSync(path.join(dir, file), "utf8"));
          return Array.isArray(records) ? records.map((record) => ({ ...record, _source_file: file })) : [];
        } catch (_) {
          return [];
        }
      });
  } catch (_) {
    return [];
  }
}

function apiMatchTitle(record) {
  if (!record) return "";
  const home = record.home || record.home_name || "";
  const away = record.away || record.away_name || "";
  return home && away ? `${home} vs ${away}` : record.key || "partido";
}

function findApiFootballMatch(question, records) {
  const q = normalizeQuestion(question);
  let best = null;
  let bestScore = 0;

  records.forEach((record) => {
    const haystack = normalizeQuestion([
      record.key,
      record.home,
      record.away,
      record.home_name,
      record.away_name,
      record.league,
      record.date
    ].filter(Boolean).join(" "));
    const words = haystack.split(" ").filter((word) => word.length > 3);
    const score = words.reduce((total, word) => total + (q.includes(word) ? 1 : 0), 0);
    if (score > bestScore) {
      best = record;
      bestScore = score;
    }
  });

  return bestScore > 0 ? best : null;
}

function findAnalyzerMatch(question, analyzer) {
  const q = normalizeQuestion(question);
  const matches = Array.isArray(analyzer && analyzer.matches) ? analyzer.matches : [];
  let best = null;
  let bestScore = 0;

  matches.forEach((match) => {
    const words = normalizeQuestion([
      match.matchup,
      match.home,
      match.away,
      match.league,
      match.key,
      match.search
    ].filter(Boolean).join(" "))
      .split(" ")
      .filter((word) => word.length > 3);
    const score = words.reduce((total, word) => total + (q.includes(word) ? 1 : 0), 0);
    if (score > bestScore) {
      best = match;
      bestScore = score;
    }
  });

  return bestScore > 0 ? best : null;
}

function editDistance(a, b) {
  const aa = normalizeQuestion(a);
  const bb = normalizeQuestion(b);
  const dp = Array.from({ length: aa.length + 1 }, () => Array(bb.length + 1).fill(0));
  for (let i = 0; i <= aa.length; i += 1) dp[i][0] = i;
  for (let j = 0; j <= bb.length; j += 1) dp[0][j] = j;
  for (let i = 1; i <= aa.length; i += 1) {
    for (let j = 1; j <= bb.length; j += 1) {
      const cost = aa[i - 1] === bb[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
    }
  }
  return dp[aa.length][bb.length];
}

function playerNameScore(queryName, playerName) {
  const q = normalizeQuestion(queryName);
  const p = normalizeQuestion(playerName);
  if (!q || !p) return 0;
  if (p.includes(q) || q.includes(p)) return 100;
  const qWords = q.split(" ").filter((word) => word.length > 2);
  const pWords = p.split(" ").filter((word) => word.length > 2);
  let score = 0;
  qWords.forEach((qw) => {
    const best = Math.max(...pWords.map((pw) => {
      if (pw === qw) return 25;
      if (pw.includes(qw) || qw.includes(pw)) return 18;
      const dist = editDistance(qw, pw);
      return dist <= 2 ? 14 - dist * 3 : 0;
    }), 0);
    score += best;
  });
  return score;
}

function findDailyPick(match, daily) {
  const picks = [
    daily && daily.pick_gratuito,
    daily && daily.pick_dia,
    ...((daily && daily.picks_suscripcion) || [])
  ].filter(Boolean);
  const matchName = normalize(match && match.match);
  return picks.find((pick) => normalize(pick.matchup) === matchName) || null;
}

function findAssistantMatch(match, assistantCalibration) {
  const matchName = normalize(match && match.match);
  return ((assistantCalibration && assistantCalibration.matches) || [])
    .find((item) => normalize(item.matchup) === matchName) || null;
}

function teamMentioned(question, match) {
  const q = normalizeQuestion(question);
  const home = normalizeQuestion(match && match.home);
  const away = normalizeQuestion(match && match.away);
  if (home && q.includes(home)) return match.home;
  if (away && q.includes(away)) return match.away;
  return null;
}

function apiTeamMentioned(question, record) {
  const q = normalizeQuestion(question);
  if (/\bpartido\b|\btotal\b|\bambos\b|\bentre\b/.test(q)) return null;
  const home = normalizeQuestion(record && (record.home || record.home_name));
  const away = normalizeQuestion(record && (record.away || record.away_name));
  if (home && q.includes(home)) return "home";
  if (away && q.includes(away)) return "away";
  return null;
}

function fmtNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2).replace(/\.00$/, "") : "s/d";
}

function stakeForTeamDanger(danger) {
  const sot = Number(danger && danger.shots_on_target_avg);
  const sample = Number(danger && danger.n_fixtures);
  if (!Number.isFinite(sot) || sample < 3) {
    return {
      stake: "0u",
      label: "Sin stake",
      reason: "muestra insuficiente o dato incompleto."
    };
  }
  if (sot >= 6) {
    return {
      stake: "0.25u",
      label: "Exploratorio",
      reason: "promedio alto de tiros a puerta; falta cuota para confirmar valor."
    };
  }
  if (sot >= 4.5) {
    return {
      stake: "0.10u a 0.25u",
      label: "Seguimiento",
      reason: "hay volumen ofensivo aceptable, sin margen para subir exposicion."
    };
  }
  return {
    stake: "0u a 0.10u",
    label: "Muy conservador",
    reason: "el volumen de tiros a puerta no es fuerte."
  };
}

function stakeForStatProbability(prob) {
  const p = Number(prob);
  if (!Number.isFinite(p)) {
    return {
      stake: "0u",
      label: "Sin stake",
      reason: "no hay porcentaje calculable con los datos disponibles."
    };
  }
  if (p >= 70) {
    return {
      stake: "0.50u",
      label: "Stake bajo-moderado",
      reason: "la linea queda bien por debajo del promedio estadistico."
    };
  }
  if (p >= 60) {
    return {
      stake: "0.25u",
      label: "Stake bajo",
      reason: "la estadistica acompana, pero sin cuota no se confirma valor esperado."
    };
  }
  if (p >= 52) {
    return {
      stake: "0.10u",
      label: "Muy bajo",
      reason: "hay inclinacion, pero el margen es corto."
    };
  }
  return {
    stake: "0u",
    label: "No tomar",
    reason: "la confianza estadistica queda por debajo del minimo."
  };
}

function nearestLineEntry(market, line) {
  const table = Array.isArray(market && market.line_table) ? market.line_table : [];
  if (!Number.isFinite(Number(line))) return null;
  return table.find((item) => Number(item.line) === Number(line)) || null;
}

function chooseAnalyzerMarket(question, analyzerMatch, detected) {
  const q = normalizeQuestion(question);
  const markets = Array.isArray(analyzerMatch && analyzerMatch.markets) ? analyzerMatch.markets : [];
  const metric = detected.key === "corners" ? "corners" : detected.key === "team_shots_on_target" ? "shots_on_target" : null;
  if (!metric) return null;

  const asksMatchTotal = /\bpartido\b|\btotal\b|\bambos\b|\bentre\b/.test(q);
  const home = normalizeQuestion(analyzerMatch.home);
  const away = normalizeQuestion(analyzerMatch.away);
  const side = asksMatchTotal ? null : home && q.includes(home) ? "home" : away && q.includes(away) ? "away" : null;

  if (side) {
    return markets.find((market) => market.metric === metric && market.scope === "team" && market.variables && market.variables.side === side) || null;
  }
  return markets.find((market) => market.metric === metric && market.scope === "match") || null;
}

function findAnalyzerPlayerMarket(question, analyzer, detected) {
  const desiredMetric = /puerta|arco|porteria|sot|on target/i.test(normalizeQuestion(question))
    ? "player_shots_on_target"
    : "player_shots_total";
  const queryName = extractPlayerQueryName(question);
  const line = extractOverLine(question);
  const matches = Array.isArray(analyzer && analyzer.matches) ? analyzer.matches : [];
  let best = null;
  let bestScore = 0;

  matches.forEach((match) => {
    (match.markets || []).forEach((market) => {
      if (market.scope !== "player" || market.metric !== desiredMetric) return;
      if (Number.isFinite(line) && !nearestLineEntry(market, line)) return;
      const score = playerNameScore(queryName, market.variables && market.variables.player_name);
      if (score > bestScore) {
        bestScore = score;
        best = { match, market };
      }
    });
  });

  return bestScore >= 10 ? best : null;
}

function explainAnalyzerVariables(market) {
  const v = (market && market.variables) || {};
  const sampleNote = v.sample_quality === "low" ? " Muestra baja: confianza castigada." : "";
  if (market.scope === "match") {
    return [
      `${v.home_team}: promedio ultimos ${v.home_sample || "s/d"} partidos = ${fmtNumber(v.home_recent_avg)}.`,
      `${v.away_team}: promedio ultimos ${v.away_sample || "s/d"} partidos = ${fmtNumber(v.away_recent_avg)}.`,
      `Promedio combinado esperado: ${fmtNumber(v.combined_avg)}.${sampleNote}`
    ];
  }
  return [
    `${v.team}: promedio ultimos ${v.sample || "s/d"} partidos = ${fmtNumber(v.recent_avg)}.${sampleNote}`
  ];
}

function extractPlayerQueryName(question) {
  const q = normalizeQuestion(question);
  const specific = q.match(/\b(?:a puerta|al arco|porteria|sot)\s+de\s+([a-z0-9 ]{3,})$/);
  if (specific) {
    return specific[1].replace(/\s+/g, " ").trim();
  }
  const match = q.match(/\b(?:de|para)\s+([a-z0-9 ]{3,})$/);
  if (!match) return null;
  return match[1]
    .replace(/\b(over|mas|de|tiros|remates|disparos|puerta|arco|porteria|sot|on|target)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function buildMissingPlayerDataAnswer(question) {
  const player = extractPlayerQueryName(question);
  const line = extractOverLine(question);
  const lines = [
    player
      ? `Mercado detectado: tiros a puerta de jugador (${player}).`
      : "Mercado detectado: tiros a puerta de jugador.",
    "",
    "Respuesta: JUGADOR NO ENCONTRADO.",
    "El motor ya tiene una base de remates/tiros a puerta por jugador, pero no pude empatar ese nombre con un jugador cargado."
  ];

  if (Number.isFinite(line)) {
    lines.push(`Linea preguntada: Over ${line} tiros a puerta.`);
  }

  lines.push("");
  lines.push("Prueba con nombre + apellido, o agrega el partido/equipo para desambiguar. Ejemplo: Over 1.5 tiros a puerta de Alexander Isak vs Netherlands.");
  lines.push("Stake sugerido: 0u.");
  lines.push("Motivo: sin empatar el jugador correcto, no voy a inventar promedio ni porcentaje.");
  return lines.join("\n");
}

function buildAnalyzerAnswer(question, analyzerMatch, detected) {
  const market = chooseAnalyzerMarket(question, analyzerMatch, detected);
  if (!market) return null;

  const line = extractOverLine(question);
  const lineEntry = nearestLineEntry(market, line);
  const ideal = market.ideal_line;
  const label = detected.key === "corners" ? "corners" : "tiros a puerta";
  const scopeText = market.scope === "match" ? "del partido" : `de ${market.variables && market.variables.team}`;
  const lines = [`${analyzerMatch.matchup} - ${market.label}`, ""];

  if (lineEntry) {
    lines.push(`Respuesta: ${lineEntry.verdict} (${verdictFromProbability(lineEntry.prob).label}).`);
    lines.push(`Confianza estadistica para Over ${lineEntry.line} ${label} ${scopeText}: ${pct(lineEntry.prob)}.`);
    if (Number(lineEntry.confidence_factor) < 1 && Number.isFinite(Number(lineEntry.raw_prob))) {
      lines.push(`Probabilidad base: ${pct(lineEntry.raw_prob)}. Ajuste por muestra: x${lineEntry.confidence_factor}.`);
    }
  } else if (Number.isFinite(line)) {
    lines.push("Respuesta: SIN LINEA EN MATRIZ.");
    lines.push(`El motor tiene datos para ${market.label}, pero no calcula todavia Over ${line}.`);
  } else {
    lines.push("Respuesta: necesito la linea exacta para responder SI o NO.");
  }

  lines.push(...explainAnalyzerVariables(market));
  if (ideal) {
    lines.push(`Linea ideal del motor: Over ${ideal.line} ${label} ${scopeText} (${pct(ideal.prob)} de confianza).`);
  } else {
    lines.push("Linea ideal del motor: ninguna linea supera 60% de confianza con estos datos.");
  }

  if (lineEntry) {
    lines.push("");
    lines.push(`Stake sugerido: ${lineEntry.stake} (${lineEntry.label}).`);
    lines.push("Metodo: promedio reciente de equipos + Poisson por linea + seleccion de linea ideal >= 60%.");
  }
  lines.push("Nota: el chat esta leyendo el analizador del motor, no calculando una respuesta aparte.");
  return lines.join("\n");
}

function buildAnalyzerPlayerAnswer(question, found) {
  if (!found) return null;
  const { match, market } = found;
  const line = extractOverLine(question);
  const lineEntry = nearestLineEntry(market, line);
  const ideal = market.ideal_line;
  const v = market.variables || {};
  const label = market.metric === "player_shots_on_target" ? "tiros a puerta" : "tiros totales";
  const lines = [`${v.player_name} - ${label}`, ""];

  if (lineEntry) {
    lines.push(`Respuesta: ${lineEntry.verdict} (${verdictFromProbability(lineEntry.prob).label}).`);
    lines.push(`Confianza estadistica para Over ${lineEntry.line} ${label}: ${pct(lineEntry.prob)}.`);
    if (Number(lineEntry.confidence_factor) < 1 && Number.isFinite(Number(lineEntry.raw_prob))) {
      lines.push(`Probabilidad base: ${pct(lineEntry.raw_prob)}. Ajuste por muestra: x${lineEntry.confidence_factor}.`);
    }
  } else if (Number.isFinite(line)) {
    lines.push("Respuesta: SIN LINEA EN MATRIZ.");
    lines.push(`El motor tiene datos de ${v.player_name}, pero no calcula todavia Over ${line} ${label}.`);
  } else {
    lines.push("Respuesta: necesito la linea exacta para responder SI o NO.");
  }

  lines.push(`Equipo: ${v.team}. Partido relacionado: ${match.matchup}.`);
  lines.push(`Promedio reciente: ${fmtNumber(v.recent_avg)} ${label} por partido.`);
  lines.push(`Muestra: ${v.appearances || "s/d"} apariciones, ${fmtNumber(v.minutes_avg)} minutos promedio.`);
  if (v.sample_quality === "low") {
    lines.push("Muestra baja: confianza castigada.");
  }
  if (ideal) {
    lines.push(`Linea ideal del motor: Over ${ideal.line} ${label} (${pct(ideal.prob)} de confianza).`);
  } else {
    lines.push("Linea ideal del motor: ninguna linea supera 60% de confianza con estos datos.");
  }

  if (lineEntry) {
    lines.push("");
    lines.push(`Stake sugerido: ${lineEntry.stake} (${lineEntry.label}).`);
    lines.push("Metodo: promedio reciente del jugador + Poisson por linea + ajuste por muestra/minutos.");
  }
  lines.push("Nota: el chat esta leyendo props de jugador del analizador del motor.");
  return lines.join("\n");
}

function buildUnsupportedCoverageAnswer(question, detected) {
  const line = extractOverLine(question);
  const lines = [
    `Mercado detectado: ${detected.label || "mercado no soportado"}.`,
    "",
    "Respuesta: SIN COBERTURA DEL MOTOR.",
    "PREDIKTOR todavia no tiene una base estadistica publicada para responder ese mercado con porcentaje y stake."
  ];
  if (Number.isFinite(line)) {
    lines.push(`Linea preguntada: Over ${line}.`);
  }
  lines.push("");
  lines.push(`Mercados que si puedo auditar ahora: ${SUPPORTED_MARKETS.join(", ")}.`);
  lines.push(`Mercados pendientes: ${UNSUPPORTED_MARKETS.join(", ")}.`);
  lines.push("Stake sugerido: 0u.");
  lines.push("Motivo: no voy a usar goles o ganador como reemplazo de un mercado distinto.");
  return lines.join("\n");
}

function dangerLine(label, danger) {
  if (!danger) return `${label}: sin bloque de danger guardado.`;
  return `${label}: ${fmtNumber(danger.shots_on_target_avg)} tiros a puerta promedio, ${fmtNumber(danger.corners_avg)} corners promedio, muestra ${danger.n_fixtures || 0} partidos.`;
}

function sampleLabel(danger) {
  const sample = Number(danger && danger.n_fixtures);
  if (!Number.isFinite(sample) || sample <= 0) return "ultimos partidos disponibles";
  return `ultimos ${sample} partidos`;
}

function buildApiFootballAnswer(question, record, detected) {
  const title = apiMatchTitle(record);
  const home = record.home || record.home_name || "Local";
  const away = record.away || record.away_name || "Visitante";
  const side = apiTeamMentioned(question, record);
  const homeDanger = record.home_danger || null;
  const awayDanger = record.away_danger || null;
  const playerBlocks = [record.home_player_shots, record.away_player_shots].filter(Boolean);
  const playerCount = playerBlocks.reduce((total, block) => total + (Array.isArray(block.players) ? block.players.length : 0), 0);

  if (detected.key === "player_shots") {
    const lines = [
      `${title} - ${detected.label}`,
      "",
      "Lectura honesta: el motor ya tiene soporte para props de jugador, pero los archivos publicados ahora mismo no traen jugadores con tiros/remates para este partido."
    ];

    if (playerCount === 0) {
      lines.push("Por eso no voy a inventar nombres, titulares ni promedios de remates.");
    }

    lines.push("");
    lines.push("Lo que si hay disponible como proxy de contexto:");
    lines.push(dangerLine(home, homeDanger));
    lines.push(dangerLine(away, awayDanger));
    lines.push("");
    lines.push("Stake sugerido: 0u en props de jugador hasta que el bloque home_player_shots / away_player_shots venga cargado.");
    lines.push("Decision de producto: este es exactamente el tipo de mercado que conviene bloquear/desbloquear cuando tengamos datos completos, porque ahi el chat si tendria una ventaja clara.");
    return lines.join("\n");
  }

  if (detected.key === "team_shots_on_target") {
    const selectedDanger = side === "home" ? homeDanger : side === "away" ? awayDanger : null;
    const selectedName = side === "home" ? home : side === "away" ? away : null;
    const line = extractOverLine(question);
    const lines = [`${title} - tiros a puerta`, ""];

    if (selectedDanger && Number.isFinite(line)) {
      const confidence = poissonOverProbability(selectedDanger.shots_on_target_avg, line);
      const decision = verdictFromProbability(confidence);
      const stake = stakeForStatProbability(confidence);
      lines.push(`Respuesta: ${decision.verdict} (${decision.label}).`);
      lines.push(`Confianza estadistica para Over ${line} tiros a puerta de ${selectedName}: ${pct(confidence)}.`);
      lines.push(`Dato usado: ${fmtNumber(selectedDanger.shots_on_target_avg)} tiros a puerta promedio en muestra de ${selectedDanger.n_fixtures || 0} partidos.`);
      lines.push(`Corners de contexto: ${fmtNumber(selectedDanger.corners_avg)} promedio.`);
      lines.push("");
      lines.push(`Stake sugerido: ${stake.stake} (${stake.label}).`);
      lines.push(`Por que: ${stake.reason}`);
    } else if (selectedDanger) {
      const stake = stakeForTeamDanger(selectedDanger);
      lines.push(`Respuesta: necesito una linea exacta para decir SI o NO. Ejemplo: Over 4.5 tiros a puerta de ${selectedName}.`);
      lines.push(`${selectedName}: ${fmtNumber(selectedDanger.shots_on_target_avg)} tiros a puerta promedio en muestra de ${selectedDanger.n_fixtures || 0} partidos.`);
      lines.push(`Corners de contexto: ${fmtNumber(selectedDanger.corners_avg)} promedio.`);
      lines.push("");
      lines.push(`Lectura base: ${stake.stake} (${stake.label}).`);
      lines.push(`Por que: ${stake.reason}`);
    } else {
      lines.push(dangerLine(home, homeDanger));
      lines.push(dangerLine(away, awayDanger));
      lines.push("");
      lines.push("Stake sugerido: 0u. Para responder SI o NO necesito equipo y linea exacta.");
    }

    lines.push("Nota: esta respuesta usa datos internos ya guardados por PREDIKTOR, sin llamada a OpenAI.");
    return lines.join("\n");
  }

  if (detected.key === "corners") {
    const selectedDanger = side === "home" ? homeDanger : side === "away" ? awayDanger : null;
    const selectedName = side === "home" ? home : side === "away" ? away : null;
    const line = extractOverLine(question);
    const lines = [`${title} - corners`, ""];

    if (selectedDanger && Number.isFinite(line)) {
      const confidence = poissonOverProbability(selectedDanger.corners_avg, line);
      const decision = verdictFromProbability(confidence);
      const stake = stakeForStatProbability(confidence);
      lines.push(`Respuesta: ${decision.verdict} (${decision.label}).`);
      lines.push(`Confianza estadistica para Over ${line} corners de ${selectedName}: ${pct(confidence)}.`);
      lines.push(`Dato usado: ${fmtNumber(selectedDanger.corners_avg)} corners promedio en muestra de ${selectedDanger.n_fixtures || 0} partidos.`);
      lines.push(`Tiros a puerta de contexto: ${fmtNumber(selectedDanger.shots_on_target_avg)} promedio.`);
      lines.push("");
      lines.push(`Stake sugerido: ${stake.stake} (${stake.label}).`);
      lines.push(`Por que: ${stake.reason}`);
    } else if (selectedDanger) {
      lines.push(`Respuesta: necesito una linea exacta para decir SI o NO. Ejemplo: Over 5.5 corners de ${selectedName}.`);
      lines.push(`${selectedName}: ${fmtNumber(selectedDanger.corners_avg)} corners promedio en muestra de ${selectedDanger.n_fixtures || 0} partidos.`);
      lines.push(`Tiros a puerta de contexto: ${fmtNumber(selectedDanger.shots_on_target_avg)} promedio.`);
    } else if (!selectedDanger && homeDanger && awayDanger && Number.isFinite(line)) {
      const totalCorners = Number(homeDanger.corners_avg) + Number(awayDanger.corners_avg);
      const confidence = poissonOverProbability(totalCorners, line);
      const decision = verdictFromProbability(confidence);
      const stake = stakeForStatProbability(confidence);
      const ideal = idealOverLine(totalCorners);
      lines.push(`Respuesta: ${decision.verdict} (${decision.label}).`);
      lines.push(`Confianza estadistica para Over ${line} corners del partido: ${pct(confidence)}.`);
      lines.push(`Dato usado: ${home} en sus ${sampleLabel(homeDanger)} saco ${fmtNumber(homeDanger.corners_avg)} corners promedio.`);
      lines.push(`${away} en sus ${sampleLabel(awayDanger)} saco ${fmtNumber(awayDanger.corners_avg)} corners promedio.`);
      lines.push(`Promedio combinado: ${fmtNumber(totalCorners)} corners por partido.`);
      if (ideal) {
        lines.push(`Linea ideal segun este promedio: Over ${ideal.line} corners (${pct(ideal.confidence)} de confianza).`);
      }
      lines.push("");
      lines.push(`Stake sugerido: ${stake.stake} (${stake.label}).`);
      lines.push(`Por que: ${stake.reason}`);
    } else {
      lines.push(dangerLine(home, homeDanger));
      lines.push(dangerLine(away, awayDanger));
    }

    lines.push("");
    lines.push("Nota: esto sale de estadisticas disponibles del equipo; sin cuota real no confirmo EV.");
    return lines.join("\n");
  }

  return null;
}

function buildUnsupportedMarketAnswer(question, match, detected, calibration, dailyPick, assistantMatch, assistantCalibration) {
  const over15 = (match.markets || []).find((market) => marketMatches(market, { key: "over_1_5" }));
  const winner = (match.markets || []).find((market) => marketMatches(market, { key: "winner" }));
  const team = teamMentioned(question, match);

  const lines = [
    `Para ${match.match}, esa pregunta cae en "${detected.label}".`,
    ""
  ];

  if (detected.key === "corners") {
    const line = extractOverLine(question);
    lines.push("Respuesta: SIN DATO DIRECTO.");
    if (Number.isFinite(line)) {
      lines.push(`No tengo estadisticas de corners guardadas para calcular el Over ${line} corners en este partido.`);
    } else {
      lines.push("No tengo estadisticas de corners guardadas para calcular esa linea.");
    }
    lines.push("");
    lines.push("Para hacer ese calculo necesito que el motor tenga los corners recientes de ambos equipos: ultimos 5 de Ecuador y ultimos 5 de Curazao.");
    lines.push("Dato disponible para este partido: el radar si trae goles/ganador/DNB, pero eso no lo voy a usar como reemplazo de corners.");
    lines.push("Stake sugerido: 0u.");
    lines.push("Motivo: sin el promedio de corners de los ultimos partidos de Ecuador y Curazao no hay forma honesta de dar porcentaje para esa linea.");
    return lines.join("\n");
  }

  if (detected.firstHalf && team && assistantMatch && assistantMatch.team_goal_first_half) {
    const teamProxy = assistantMatch.team_goal_first_half[team];
    if (teamProxy) {
      const decision = verdictFromProbability(teamProxy.adjusted_prob);
      const stake = stakeForStatProbability(teamProxy.adjusted_prob);
      lines.push(`Respuesta: ${decision.verdict} (${decision.label}).`);
      lines.push(`Confianza estadistica de gol 1T para ${team}: ${teamProxy.adjusted_prob}% (${teamProxy.raw_prob}% base por Poisson).`);
      lines.push(`Dato usado: lambda ofensiva ${team === match.home ? assistantMatch.lambda_home : assistantMatch.lambda_away}; ajuste conservador aplicado para primera mitad.`);
      lines.push("");
      lines.push(`Stake sugerido: ${stake.stake} (${stake.label}).`);
      lines.push(`Por que: ${stake.reason}`);
      lines.push("Nota: esto responde segun estadistica disponible del partido; sin cuota real no confirmo EV.");
      return lines.join("\n");
    }
  }

  if (detected.firstHalf) {
    lines.push("Respuesta: SIN DATO.");
    lines.push("No tengo suficiente estadistica interna para calcular confianza de primera mitad en este partido.");
  }

  if (team) {
    if (detected.key === "corners") {
      lines.push(`Sobre ${team}: puedo usar el contexto general del partido, pero necesito una linea concreta para responder SI o NO.`);
    } else {
      lines.push(`Sobre ${team}: puedo usar el contexto del partido como referencia, pero necesito datos suficientes del mercado exacto.`);
    }
  }

  if (over15) {
    lines.push(`Como proxy de ritmo/goles, el radar tiene Over 1.5 del partido en ${pct(over15.prob)} contra umbral ${pct(over15.threshold)} (${over15.passed ? "pasa" : "no pasa"}).`);
  }
  if (winner) {
    lines.push(`En ganador, ${winner.pick || "el favorito"} aparece con ${pct(winner.prob)} contra umbral ${pct(winner.threshold)} (${winner.passed ? "pasa" : "no pasa"}).`);
  }
  if (dailyPick) {
    lines.push(`Pick diario relacionado: ${dailyPick.market} con ${pct(dailyPick.prob_adjusted)}.`);
  }

  lines.push("");
  lines.push("Stake sugerido: 0u si no hay porcentaje directo para esa linea.");
  lines.push("Motivo: el asistente debe responder con datos verificables, no inventar una confianza donde el archivo no la trae.");

  return lines.join("\n");
}

function buildAnswer(question) {
  const daily = readJson("static/predictions/daily_picks.json");
  const radar = readJson("static/statistical_radar.json");
  const calibration = readJson("static/calibration_shadow.json");
  const assistantCalibration = readJson("static/assistant_market_calibration.json");
  const marketAnalyzer = readJson("static/market_analyzer.json");
  const detected = detectMarket(question);
  const match = findMatch(question, radar);
  const analyzerMatch = findAnalyzerMatch(question, marketAnalyzer);
  const apiRecords = detected.apiFootball ? readApiFootballRecords() : [];
  const apiMatch = detected.apiFootball ? findApiFootballMatch(question, apiRecords) : null;

  if (detected.key === "unsupported_market") {
    return buildUnsupportedCoverageAnswer(question, detected);
  }

  if (detected.key === "player_shots") {
    const playerAnswer = buildAnalyzerPlayerAnswer(
      question,
      findAnalyzerPlayerMarket(question, marketAnalyzer, detected)
    );
    if (playerAnswer) return playerAnswer;
    if (!apiMatch) return buildMissingPlayerDataAnswer(question);
  }

  if (analyzerMatch && (detected.key === "team_shots_on_target" || detected.key === "corners")) {
    const answer = buildAnalyzerAnswer(question, analyzerMatch, detected);
    if (answer) return answer;
  }

  if (apiMatch && (detected.key === "team_shots_on_target" || detected.key === "player_shots" || detected.key === "corners")) {
    const answer = buildApiFootballAnswer(question, apiMatch, detected);
    if (answer) return answer;
  }

  if (!match) {
    return [
      "No encontre ese partido en el radar actual de PREDIKTOR.",
      "",
      "Puedes preguntarme con el formato: mercado + partido. Ejemplo:",
      "Over 1.5 en Netherlands vs Sweden",
      "Tiros a puerta de Atletico Nacional vs Junior",
      "Corners en Ecuador vs Curacao",
      "Ecuador gol primera mitad vs Curacao"
    ].join("\n");
  }

  const dailyPick = findDailyPick(match, daily);
  const assistantMatch = findAssistantMatch(match, assistantCalibration);
  const disabledMarkets = calibration && calibration.disabled_markets ? calibration.disabled_markets : [];
  const marketDisabled = detected.disabledKey && disabledMarkets.includes(detected.disabledKey);

  if (detected.unsupported || marketDisabled) {
    return buildUnsupportedMarketAnswer(question, match, detected, calibration, dailyPick, assistantMatch, assistantCalibration);
  }

  let market = (match.markets || []).find((item) => marketMatches(item, detected));
  if (!market && detected.key === "general") {
    market = match.recommended || (match.markets || []).find((item) => item.passed) || (match.markets || [])[0];
  }

  if (!market) {
    return [
      `En ${match.match} no encontre datos para "${detected.label}" en el radar actual.`,
      "",
      "Stake sugerido: 0u.",
      "Motivo: si el mercado no esta en el radar, no conviene inventar lectura."
    ].join("\n");
  }

  const stake = unitsForProbability(market.prob, market.passed, false, false);
  const status = market.passed ? "SI, la estadistica da para esa linea" : "NO, la estadistica no da suficiente para esa linea";
  const pickText = market.pick ? ` para ${market.pick}` : "";
  const lines = [
    `${match.match} - ${market.market}${pickText}`,
    "",
    `Respuesta: ${status}.`,
    `Probabilidad del radar: ${pct(market.prob)}.`,
    `Umbral minimo: ${pct(market.threshold)}.`,
    `Razon del motor: ${market.reason || "s/d"}.`
  ];

  if (dailyPick) {
    lines.push(`Pick diario relacionado: ${dailyPick.market} con ${pct(dailyPick.prob_adjusted)}.`);
  }

  lines.push("");
  lines.push(`Stake sugerido: ${stake.stake} (${stake.label}).`);
  lines.push(`Por que: ${stake.reason}`);
  lines.push("Nota: sin cuota real no confirmo EV; esto es lectura estadistica, no apuesta segura.");

  return lines.join("\n");
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 12000) {
        reject(new Error("payload_too_large"));
        req.destroy();
      }
    });
    req.on("end", () => resolve(body));
    req.on("error", reject);
  });
}

function json(res, status, payload) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify(payload));
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return json(res, 405, { ok: false, error: "Method not allowed" });
  }

  let message = "";
  try {
    const raw = await readBody(req);
    const body = JSON.parse(raw || "{}");
    message = String(body.message || "").trim();
  } catch (_) {
    return json(res, 400, { ok: false, error: "Solicitud invalida" });
  }

  if (message.length < 3) {
    return json(res, 400, { ok: false, error: "Escribe una pregunta un poco mas especifica." });
  }
  if (message.length > 1200) {
    return json(res, 400, { ok: false, error: "La pregunta es demasiado larga." });
  }

  const isPro = isProRequest(req);
  const currentCount = readFreeChatCount(req);
  if (!isPro && currentCount >= FREE_CHAT_LIMIT) {
    const detected = detectMarket(message);
    appendQueryLog({
      at: new Date().toISOString(),
      question: normalizeQuestion(message).slice(0, 240),
      market_key: detected.key,
      market_label: detected.label,
      unsupported: detected.key === "unsupported_market",
      answered: false,
      locked: true,
      free_data_mode: true
    });
    return json(res, 402, {
      ok: false,
      locked: true,
      error: "Ya usaste tus 3 preguntas gratis. Activa PREDIKTOR Pro para seguir usando el asistente estadistico sin limite.",
      cta: {
        label: "Ver Plan Pro",
        href: "/plan-pro"
      },
      remaining: 0,
      limit: FREE_CHAT_LIMIT,
      is_pro: false
    });
  }

  const answer = buildAnswer(message);
  const detected = detectMarket(message);
  const unsupported = detected.key === "unsupported_market" || answer.includes("SIN COBERTURA DEL MOTOR");
  const nextCount = isPro ? currentCount : currentCount + 1;
  if (!isPro) {
    setFreeChatCount(res, nextCount);
  }
  appendQueryLog({
    at: new Date().toISOString(),
    question: normalizeQuestion(message).slice(0, 240),
    market_key: detected.key,
    market_label: detected.label,
    unsupported,
    answered: Boolean(answer),
    locked: false,
    free_data_mode: true
  });
  return json(res, 200, {
    ok: true,
    answer,
    market: {
      key: detected.key,
      label: detected.label,
      unsupported
    },
    supported_markets: SUPPORTED_MARKETS,
    is_pro: isPro,
    free_data_mode: true,
    remaining: isPro ? null : Math.max(0, FREE_CHAT_LIMIT - nextCount),
    limit: FREE_CHAT_LIMIT
  });
};
