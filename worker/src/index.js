const JT_URL = "https://official.jtjms-br.com/official/logisticsTracking/v2/getDetailByWaybillNo";
const JT_TRACKING_URL = "https://www.jtexpress.com.br/trajectquery?waybillNo=";
const JADLOG_URL = "https://www.jadlog.com.br/jadlog/rastreio";
const JADLOG_TRACKING_URL = "https://www.jadlog.com.br/jadlog/rastreio?cte=";
const LOGGI_URL = "https://rastreamento.superfrete.com/public/tracking/";
const LOGGI_TRACKING_URL = "https://rastreamento.superfrete.com/?code=";
const CORREIOS_TRACKING_URL = "https://rastreamento.correios.com.br/app/index.php?objeto=";
const PACOTEVICIO_URL = "https://correios-rastreamento-de-encomendas.p.rapidapi.com/track";
const PACOTEVICIO_HOST = "correios-rastreamento-de-encomendas.p.rapidapi.com";
const APP_ID = "3B29A9C5728BF3E1DB0C4D66B79748B7";
const JT_KEY = "94bbcac67ab47c736d530efe3e1dc358";
const MAX_FAIL = 3;

const HUB_MAP = {
  "SN RAO": "Ribeirão Preto",
  RAO: "Ribeirão Preto",
  "ARA-SP": "Araraquara",
  ARA: "Araraquara",
  "SJC-SP": "São José dos Campos",
  SJC: "São José dos Campos",
  "SP BRE": "Barueri",
  BRE: "Barueri",
  HQ: "São Paulo",
};

const EMOJI_MAP = [
  [["entregue", "entrega realizada", "pedido entregue", "delivered"], "✅"],
  [["saiu para entrega", "em rota", "retirou", "out for delivery"], "🛵"],
  [["saída", "saiu", "enviada para"], "📤"],
  [["chegada", "chegou", "recebido no"], "📍"],
  [["coletado", "coleta", "etiqueta comprada", "postado"], "📦"],
  [["tentativa", "ausente", "nao entregue", "falha", "ocorrencia"], "❌"],
  [["devolucao", "devolvido", "retorno"], "🔄"],
  [["em transito", "transporte", "encaminhada", "transferencia"], "🚚"],
];

function required(env, name) {
  const value = env[name];
  if (value === undefined || value === null || String(value).trim() === "") {
    throw new Error(`binding obrigatorio ausente: ${name}`);
  }
  return String(value).trim();
}

export function parseList(raw, upper = false) {
  return String(raw || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean)
    .map((value) => (upper ? value.toUpperCase() : value));
}

export function parseLabels(raw) {
  const labels = {};
  for (const item of parseList(raw)) {
    const separator = item.indexOf("=");
    if (separator > 0) labels[item.slice(0, separator).trim()] = item.slice(separator + 1).trim();
  }
  return labels;
}

function normalize(text) {
  return String(text || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function pickEmoji(text) {
  const lower = String(text || "").toLowerCase();
  for (const [keywords, emoji] of EMOJI_MAP) {
    if (keywords.some((keyword) => lower.includes(keyword))) return emoji;
  }
  return "📬";
}

export function cleanText(status, desc) {
  let text = `${status || ""} ${desc || ""}`.trim().replace(/[【】]/g, " ");
  let normalized = normalize(text);
  for (const [abbreviation, city] of Object.entries(HUB_MAP)) {
    const replacement = normalized.includes(normalize(city)) ? "" : city;
    text = text.replaceAll(`[${abbreviation}]`, replacement);
    normalized = normalize(text);
  }
  text = text
    .replace(/\[[A-Z0-9]{1,4}[\s-][A-Z0-9]{1,4}\]/g, "")
    .replace(/\[[A-Z0-9]{2,5}\]/g, "")
    .replace(/\[([^\]]+)\]/g, "$1")
    .replace(/\b\w\*{2,}\w\b/g, "")
    .replace(/\.?\s*Se voc\S+ tiver.*/i, "")
    .replace(/,?\s*ligue para.*/i, "");
  for (let index = 0; index < 3; index += 1) {
    text = text.replace(/[,\s]+(para|de|do|da|operador|enviada|e)\s*$/i, "").replace(/[ ,.]+$/, "");
  }
  text = text.replace(/\s{2,}/g, " ").trim();
  return text.length > 150 ? `${text.slice(0, 147)}...` : text;
}

function stripHtml(raw) {
  return String(raw || "")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)))
    .replace(/\s{2,}/g, " ")
    .trim();
}

function formatDateTime(raw) {
  const text = String(raw || "").trim();
  let match = text.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}:\d{2})/);
  if (match) return `${match[3]}/${match[2]} ${match[4]}`;
  match = text.match(/^(\d{2})\/(\d{2})\/\d{2,4}\s*(?:-|\s)\s*(\d{2}:\d{2})/);
  if (match) return `${match[1]}/${match[2]} ${match[3]}`;
  return text;
}

function eventKey(event) {
  return `${event.time || ""}|${event.status || ""}|${event.desc || ""}`;
}

export function diffEvents(oldEvents, newEvents) {
  const oldKeys = new Set((oldEvents || []).map(eventKey));
  return (newEvents || []).filter((event) => !oldKeys.has(eventKey(event)));
}

function isDelivered(event) {
  const text = normalize(`${event.status || ""} ${event.desc || ""}`);
  return ["entregue", "entrega realizada", "delivered", "pedido entregue"].some((word) => text.includes(word));
}

function isJadlogDelivered(event) {
  return normalize(`${event.status || ""} ${event.desc || ""}`).includes("destinatario");
}

function objKeySort(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) return data;
  const result = {};
  for (const key of Object.keys(data).sort()) {
    const value = data[key];
    if (Array.isArray(value)) result[key] = value.map((item) => (item && typeof item === "object" ? objKeySort(item) : item));
    else if (value !== null && typeof value === "object") result[key] = objKeySort(value);
    else if (value !== null) result[key] = value;
  }
  return result;
}

// A API oficial antiga da J&T usa MD5 e o Web Crypto não oferece esse algoritmo.
function md5(str) {
  function safeAdd(x, y) { const lsw = (x & 0xffff) + (y & 0xffff); return (((x >> 16) + (y >> 16) + (lsw >> 16)) << 16) | (lsw & 0xffff); }
  function rotate(num, count) { return (num << count) | (num >>> (32 - count)); }
  function common(q, a, b, x, s, t) { return safeAdd(rotate(safeAdd(safeAdd(a, q), safeAdd(x, t)), s), b); }
  function ff(a, b, c, d, x, s, t) { return common((b & c) | (~b & d), a, b, x, s, t); }
  function gg(a, b, c, d, x, s, t) { return common((b & d) | (c & ~d), a, b, x, s, t); }
  function hh(a, b, c, d, x, s, t) { return common(b ^ c ^ d, a, b, x, s, t); }
  function ii(a, b, c, d, x, s, t) { return common(c ^ (b | ~d), a, b, x, s, t); }
  const bytes = [...new TextEncoder().encode(str)];
  const length = bytes.length;
  bytes.push(0x80);
  while (bytes.length % 64 !== 56) bytes.push(0);
  const bits = length * 8;
  bytes.push(bits & 0xff, (bits >>> 8) & 0xff, (bits >>> 16) & 0xff, (bits >>> 24) & 0xff, 0, 0, 0, 0);
  const words = new Array(Math.ceil(bytes.length / 4)).fill(0);
  bytes.forEach((byte, index) => { words[index >> 2] |= byte << ((index % 4) * 8); });
  let a = 0x67452301; let b = 0xefcdab89; let c = 0x98badcfe; let d = 0x10325476;
  for (let n = 0; n < words.length; n += 16) {
    const [aa, bb, cc, dd] = [a, b, c, d];
    a=ff(a,b,c,d,words[n],7,-680876936);d=ff(d,a,b,c,words[n+1],12,-389564586);c=ff(c,d,a,b,words[n+2],17,606105819);b=ff(b,c,d,a,words[n+3],22,-1044525330);
    a=ff(a,b,c,d,words[n+4],7,-176418897);d=ff(d,a,b,c,words[n+5],12,1200080426);c=ff(c,d,a,b,words[n+6],17,-1473231341);b=ff(b,c,d,a,words[n+7],22,-45705983);
    a=ff(a,b,c,d,words[n+8],7,1770035416);d=ff(d,a,b,c,words[n+9],12,-1958414417);c=ff(c,d,a,b,words[n+10],17,-42063);b=ff(b,c,d,a,words[n+11],22,-1990404162);
    a=ff(a,b,c,d,words[n+12],7,1804603682);d=ff(d,a,b,c,words[n+13],12,-40341101);c=ff(c,d,a,b,words[n+14],17,-1502002290);b=ff(b,c,d,a,words[n+15],22,1236535329);
    a=gg(a,b,c,d,words[n+1],5,-165796510);d=gg(d,a,b,c,words[n+6],9,-1069501632);c=gg(c,d,a,b,words[n+11],14,643717713);b=gg(b,c,d,a,words[n],20,-373897302);
    a=gg(a,b,c,d,words[n+5],5,-701558691);d=gg(d,a,b,c,words[n+10],9,38016083);c=gg(c,d,a,b,words[n+15],14,-660478335);b=gg(b,c,d,a,words[n+4],20,-405537848);
    a=gg(a,b,c,d,words[n+9],5,568446438);d=gg(d,a,b,c,words[n+14],9,-1019803690);c=gg(c,d,a,b,words[n+3],14,-187363961);b=gg(b,c,d,a,words[n+8],20,1163531501);
    a=gg(a,b,c,d,words[n+13],5,-1444681467);d=gg(d,a,b,c,words[n+2],9,-51403784);c=gg(c,d,a,b,words[n+7],14,1735328473);b=gg(b,c,d,a,words[n+12],20,-1926607734);
    a=hh(a,b,c,d,words[n+5],4,-378558);d=hh(d,a,b,c,words[n+8],11,-2022574463);c=hh(c,d,a,b,words[n+11],16,1839030562);b=hh(b,c,d,a,words[n+14],23,-35309556);
    a=hh(a,b,c,d,words[n+1],4,-1530992060);d=hh(d,a,b,c,words[n+4],11,1272893353);c=hh(c,d,a,b,words[n+7],16,-155497632);b=hh(b,c,d,a,words[n+10],23,-1094730640);
    a=hh(a,b,c,d,words[n+13],4,681279174);d=hh(d,a,b,c,words[n],11,-358537222);c=hh(c,d,a,b,words[n+3],16,-722521979);b=hh(b,c,d,a,words[n+6],23,76029189);
    a=hh(a,b,c,d,words[n+9],4,-640364487);d=hh(d,a,b,c,words[n+12],11,-421815835);c=hh(c,d,a,b,words[n+15],16,530742520);b=hh(b,c,d,a,words[n+2],23,-995338651);
    a=ii(a,b,c,d,words[n],6,-198630844);d=ii(d,a,b,c,words[n+7],10,1126891415);c=ii(c,d,a,b,words[n+14],15,-1416354905);b=ii(b,c,d,a,words[n+5],21,-57434055);
    a=ii(a,b,c,d,words[n+12],6,1700485571);d=ii(d,a,b,c,words[n+3],10,-1894986606);c=ii(c,d,a,b,words[n+10],15,-1051523);b=ii(b,c,d,a,words[n+1],21,-2054922799);
    a=ii(a,b,c,d,words[n+8],6,1873313359);d=ii(d,a,b,c,words[n+15],10,-30611744);c=ii(c,d,a,b,words[n+6],15,-1560198380);b=ii(b,c,d,a,words[n+13],21,1309151649);
    a=ii(a,b,c,d,words[n+4],6,-145523070);d=ii(d,a,b,c,words[n+11],10,-1120210379);c=ii(c,d,a,b,words[n+2],15,718787259);b=ii(b,c,d,a,words[n+9],21,-343485551);
    a=safeAdd(a,aa);b=safeAdd(b,bb);c=safeAdd(c,cc);d=safeAdd(d,dd);
  }
  return [a,b,c,d].map((value) => { let result=""; for(let j=0;j<4;j+=1) result += (`0${((value >>> (j*8)) & 0xff).toString(16)}`).slice(-2); return result; }).join("").toUpperCase();
}

function buildSign(timestamp, nonce, payload) {
  return md5(`${APP_ID}${timestamp}${nonce}${JSON.stringify(objKeySort(payload))}${JT_KEY}`);
}

async function responseBody(response) {
  const text = await response.text();
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${text.slice(0, 200)}`);
  return text;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await responseBody(response);
  try { return JSON.parse(text); } catch { throw new Error(`resposta JSON invalida: ${text.slice(0, 120)}`); }
}

async function fetchPacoteVicio(env, service, params) {
  const apiKey = required(env, "PACOTEVICIO_API_KEY");
  const url = new URL(env.PACOTEVICIO_URL || PACOTEVICIO_URL);
  for (const [key, value] of Object.entries(params)) url.searchParams.set(key, value);
  return fetchJson(url, {
    headers: {
      Accept: "application/json",
      "X-RapidAPI-Key": apiKey,
      "X-RapidAPI-Host": env.PACOTEVICIO_RAPIDAPI_HOST || PACOTEVICIO_HOST,
    },
  }).catch((error) => { throw new Error(`${service}: ${error.message}`); });
}

async function fetchJtOfficial(env, waybill) {
  const cpf = required(env, "CPF");
  const payload = { cpf, waybillNo: waybill, langType: "PT" };
  const timestamp = String(Date.now());
  const nonce = String(Math.random());
  return fetchJson(JT_URL, {
    method: "POST",
    headers: {
      Accept: "application/json, text/plain, */*",
      "Content-Type": "application/json",
      Origin: "https://www.jtexpress.com.br",
      Referer: "https://www.jtexpress.com.br/",
      "User-Agent": "Mozilla/5.0 (compatible; jt-monitor/2.0)",
      appId: APP_ID,
      clientSource: "web",
      countryId: "1",
      langType: "PT",
      timezone: "GMT-0300",
      key: JT_KEY,
      timestamp,
      nonce,
      sign: buildSign(timestamp, nonce, payload),
    },
    body: JSON.stringify(payload),
  });
}

async function fetchJt(env, waybill) {
  const provider = String(env.JT_PROVIDER || (env.PACOTEVICIO_API_KEY ? "pacotevicio" : "official")).toLowerCase();
  if (provider === "official") return fetchJtOfficial(env, waybill);
  return fetchPacoteVicio(env, "J&T", {
    tracking_code: waybill,
    confidence_level: env.PACOTEVICIO_CONFIDENCE_LEVEL || "medium",
    document: required(env, "CPF").replace(/\D/g, ""),
  });
}

async function fetchJadlog(_env, cte) {
  const response = await fetch(JADLOG_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Origin: "https://www.jadlog.com.br",
      Referer: "https://www.jadlog.com.br/jadlog/captcha",
      "User-Agent": "Mozilla/5.0 (compatible; jt-monitor/2.0)",
    },
    body: new URLSearchParams({ cte }).toString(),
  });
  return responseBody(response);
}

async function fetchLoggi(env, code) {
  const base = String(env.LOGGI_URL || LOGGI_URL).replace(/\/$/, "");
  const url = new URL(`${base}/${encodeURIComponent(code)}`);
  url.searchParams.set("application_id", env.SUPERFRETE_APPLICATION_ID || "100");
  return fetchJson(url, {
    headers: { Accept: "application/json, text/plain, */*", Referer: "https://rastreamento.superfrete.com/" },
  });
}

async function fetchCorreios(env, code) {
  return fetchPacoteVicio(env, "Correios", {
    tracking_code: code,
    confidence_level: env.PACOTEVICIO_CONFIDENCE_LEVEL || "medium",
  });
}

export function extractJtEvents(data) {
  const root = data?.jtexpress_object || data?.data || data || {};
  const events = [];
  for (const detail of root.details || []) {
    const items = detail.pathInfo || detail.traces || [detail];
    for (const item of items) {
      events.push({
        time: item.scanTime || item.acceptTime || item.time || "",
        status: item.status || item.scanTypeName || item.scanType || "",
        desc: item.customerTracking || item.acceptAddress || item.desc || "",
        deliveryName: item.deliveryName || detail.deliveryName || "",
      });
    }
  }
  return events;
}

export function extractJadlogEvents(html) {
  const events = [];
  const pattern = /class="txt-status">(.*?)<br[^>]*>\s*<small class="txt-data">(.*?)<\/small>/gis;
  for (const match of String(html || "").matchAll(pattern)) {
    const status = stripHtml(match[1]);
    if (status) events.push({ time: stripHtml(match[2]), status, desc: "", deliveryName: "" });
  }
  return events;
}

export function extractLoggiEvents(data) {
  const rawEvents = data?.provider_tracking?.tracking?.eventos || [];
  return rawEvents.filter((event) => event && typeof event === "object").map((event) => {
    const status = stripHtml(event.status || "");
    const desc = [event.descricao, event.unidade]
      .filter((part) => part && part !== event.status)
      .map(stripHtml)
      .join(" | ");
    return { time: event.data || event.time || "", status, desc, deliveryName: "" };
  });
}

function correiosUnitText(unit) {
  if (!unit || typeof unit !== "object") return "";
  const parts = [];
  if (unit.tipo) parts.push(String(unit.tipo));
  const city = unit.endereco?.cidade;
  const uf = unit.endereco?.uf;
  if (city && uf) parts.push(`${city}/${uf}`);
  else if (city || uf) parts.push(String(city || uf));
  return parts.join(" - ");
}

function correiosEventTime(event) {
  let raw = event.dtHrCriado || event.data || event.time || event.timeStr || "";
  if (raw && typeof raw === "object") raw = raw.date || raw.datetime || "";
  const text = stripHtml(raw);
  const brazilian = text.match(/(\d{2})\/(\d{2})\/(\d{2})\s+(\d{2}:\d{2})/);
  return brazilian ? `20${brazilian[3]}-${brazilian[2]}-${brazilian[1]} ${brazilian[4]}` : text.slice(0, 16);
}

export function extractCorreiosEvents(data) {
  const root = Array.isArray(data) ? data : data?.correios_object || data?.data || data || {};
  const rawEvents = Array.isArray(root) ? root : root.eventos || root.events || root.historico || [];
  return rawEvents.filter((event) => event && typeof event === "object").map((event) => {
    const status = event.descricaoFrontEnd || event.descricaoWeb || event.descricao || event.status || event.statusDesc || "";
    const desc = [event.descricao !== status ? event.descricao : "", event.detalhe, correiosUnitText(event.unidade)]
      .filter(Boolean).map(stripHtml).join(" | ");
    return { time: correiosEventTime(event), status: stripHtml(status), desc, deliveryName: "" };
  });
}

function buildUpdateMessage(carrier, code, label, events, trackingUrl) {
  const lines = [`📦 ${carrier} - ${label || code}`];
  for (const event of events.slice(0, 3)) {
    const text = cleanText(event.status, event.desc);
    lines.push(`\n${pickEmoji(text)} ${formatDateTime(event.time)}\n${text}`);
  }
  lines.push(`\n🔗 ${trackingUrl}${code}`);
  return lines.join("\n");
}

function buildDeliveredMessage(carrier, code, label, trackingUrl) {
  return `✅ ${carrier} - ${label || code}\n\nSua encomenda foi entregue com sucesso! 🎉\n\n🔗 ${trackingUrl}${code}`;
}

function buildInitialMessage(carrier, code, label, events, trackingUrl) {
  const lines = [`📦 ${carrier} - ${label || code}`, "\n🔔 Monitoramento iniciado!"];
  const latestEvent = events[0];
  if (latestEvent) {
    const text = cleanText(latestEvent.status, latestEvent.desc);
    lines.push(`\nStatus atual:\n${pickEmoji(text)} ${formatDateTime(latestEvent.time)}\n${text}`);
  } else {
    lines.push("\nAinda não há movimentações disponíveis para esta encomenda.");
  }
  lines.push(`\n🔗 ${trackingUrl}${code}`);
  return lines.join("\n");
}

function buildErrorMessage(carrier, code, label, trackingUrl) {
  return `⚠️ ${carrier} - ${label || code}\n\nFalha ao consultar rastreio por ${MAX_FAIL} vezes seguidas. Verifique manualmente.\n\n🔗 ${trackingUrl}${code}`;
}

export async function sendWhatsApp(env, message) {
  const instanceId = required(env, "GREEN_API_INSTANCE_ID");
  const token = required(env, "GREEN_API_TOKEN");
  const phones = parseList(required(env, "WHATSAPP_PHONE")).map((phone) => phone.replace(/\D/g, "")).filter(Boolean);
  if (!phones.length) throw new Error("WHATSAPP_PHONE nao contem numero valido");
  const apiUrl = String(env.GREEN_API_URL || "https://api.green-api.com").replace(/\/$/, "");
  const url = `${apiUrl}/waInstance${instanceId}/sendMessage/${token}`;
  for (const phone of phones) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chatId: `${phone}@c.us`, message }),
    });
    const body = await response.text();
    console.log(`[green-api] phone=${phone} status=${response.status} body=${body.slice(0, 200)}`);
    if (!response.ok) throw new Error(`Green API recusou o envio (HTTP ${response.status}): ${body.slice(0, 200)}`);
  }
}

const CARRIERS = {
  jt: { name: "J&T", trackingUrl: JT_TRACKING_URL, fetcher: fetchJt, parser: extractJtEvents, delivered: isDelivered },
  jadlog: { name: "Jadlog", trackingUrl: JADLOG_TRACKING_URL, fetcher: fetchJadlog, parser: extractJadlogEvents, delivered: isJadlogDelivered },
  loggi: { name: "Loggi", trackingUrl: LOGGI_TRACKING_URL, fetcher: fetchLoggi, parser: extractLoggiEvents, delivered: isDelivered },
  correios: { name: "Correios/Sedex", trackingUrl: CORREIOS_TRACKING_URL, fetcher: fetchCorreios, parser: extractCorreiosEvents, delivered: isDelivered },
};

async function loadState(env, carrier, code) {
  let state = await env.TRACKING_STATE.get(`tracking:${carrier}:${code}`, "json");
  // Compatibilidade com o Worker antigo, que salvava a J&T usando apenas o código.
  if (!state && carrier === "jt") state = await env.TRACKING_STATE.get(code, "json");
  return state;
}

async function saveState(env, carrier, code, state) {
  await env.TRACKING_STATE.put(`tracking:${carrier}:${code}`, JSON.stringify(state));
}

async function trackOne(env, carrierId, code, label) {
  const carrier = CARRIERS[carrierId];
  const state = await loadState(env, carrierId, code);
  if (state?.delivered) {
    console.log(`[skip] ${carrierId} ${code} ja entregue`);
    return { carrier: carrierId, code, status: "delivered-skip" };
  }

  let events;
  try {
    const raw = await carrier.fetcher(env, code);
    events = carrier.parser(raw);
    if (state?.events?.length && !events.length) throw new Error("resposta vazia apos existir historico");
  } catch (error) {
    const failCount = (state?.failCount || state?.fail_count || 0) + 1;
    const failedState = { ...(state || {}), failCount, lastErrorAt: new Date().toISOString() };
    await saveState(env, carrierId, code, failedState);
    console.error(`[erro] ${carrierId} ${code}: ${error.message}`);
    if (failCount === MAX_FAIL) {
      try { await sendWhatsApp(env, buildErrorMessage(carrier.name, code, label, carrier.trackingUrl)); }
      catch (notifyError) { console.error(`[erro] alerta de falha ${carrierId} ${code}: ${notifyError.message}`); }
    }
    return { carrier: carrierId, code, status: "error", error: error.message, failCount };
  }

  const now = new Date().toISOString();
  const deliveredEvent = events.find(carrier.delivered);
  if (!state) {
    const initialMessage = deliveredEvent
      ? buildDeliveredMessage(carrier.name, code, label, carrier.trackingUrl)
      : buildInitialMessage(carrier.name, code, label, events, carrier.trackingUrl);
    // Só confirma o histórico depois do WhatsApp. Se o envio falhar, a próxima
    // rodada tenta novamente e o primeiro aviso nunca é perdido.
    await sendWhatsApp(env, initialMessage);
    await saveState(env, carrierId, code, {
      events,
      failCount: 0,
      firstSeenAt: now,
      lastCheckedAt: now,
      lastStatus: events[0]?.status || "",
      delivered: Boolean(deliveredEvent),
      deliveredAt: deliveredEvent?.time || null,
    });
    console.log(`[iniciado] ${carrierId} ${code}: status inicial enviado; ${events.length} eventos salvos`);
    return { carrier: carrierId, code, status: deliveredEvent ? "delivered" : "initialized", events: events.length };
  }

  const newEvents = diffEvents(state.events || [], events);
  const nextState = {
    ...state,
    events,
    failCount: 0,
    lastCheckedAt: now,
    lastStatus: events[0]?.status || state.lastStatus || "",
  };
  if (!newEvents.length) {
    await saveState(env, carrierId, code, nextState);
    console.log(`[ok] ${carrierId} ${code}: sem mudancas`);
    return { carrier: carrierId, code, status: "unchanged", events: events.length };
  }

  const newDelivery = newEvents.find(carrier.delivered);
  const message = newDelivery
    ? buildDeliveredMessage(carrier.name, code, label, carrier.trackingUrl)
    : buildUpdateMessage(carrier.name, code, label, newEvents, carrier.trackingUrl);
  try {
    await sendWhatsApp(env, message);
  } catch (error) {
    // Mantém os eventos antigos para tentar a mesma notificação no próximo cron.
    await saveState(env, carrierId, code, { ...state, notificationFailCount: (state.notificationFailCount || 0) + 1, lastNotificationErrorAt: now });
    throw error;
  }
  if (newDelivery) {
    nextState.delivered = true;
    nextState.deliveredAt = newDelivery.time || now;
  }
  nextState.notificationFailCount = 0;
  await saveState(env, carrierId, code, nextState);
  console.log(`[novo] ${carrierId} ${code}: ${newEvents.length} eventos`);
  return { carrier: carrierId, code, status: newDelivery ? "delivered" : "notified", newEvents: newEvents.length };
}

export function configuredTrackings(env) {
  const groups = [
    ["jt", parseList(env.WAYBILL_NO), parseLabels(env.WAYBILL_LABELS)],
    ["jadlog", parseList(env.JADLOG_CTE), parseLabels(env.JADLOG_LABELS)],
    ["loggi", parseList(env.LOGGI_CODES, true), parseLabels(env.LOGGI_LABELS)],
    ["correios", parseList(env.CORREIOS_CODES, true), parseLabels(env.CORREIOS_LABELS)],
  ];
  return groups.flatMap(([carrier, codes, labels]) => codes.map((code) => ({ carrier, code, label: labels[code] || "" })));
}

export async function runAll(env) {
  if (!env.TRACKING_STATE) throw new Error("binding TRACKING_STATE ausente");
  const results = [];
  for (const item of configuredTrackings(env)) {
    try { results.push(await trackOne(env, item.carrier, item.code, item.label)); }
    catch (error) {
      console.error(`[erro] ${item.carrier} ${item.code}: ${error.message}`);
      results.push({ carrier: item.carrier, code: item.code, status: "error", error: error.message });
    }
  }
  return results;
}

function authorized(request, env) {
  const runToken = env.RUN_TOKEN;
  if (!runToken) return false;
  return request.headers.get("Authorization") === `Bearer ${runToken}`;
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), { status, headers: { "Content-Type": "application/json; charset=utf-8" } });
}

export default {
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(runAll(env));
  },

  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (pathname === "/") {
      const counts = configuredTrackings(env).reduce((result, item) => ({ ...result, [item.carrier]: (result[item.carrier] || 0) + 1 }), {});
      return jsonResponse({ service: "jt-monitor", status: "ok", trackings: counts });
    }
    if (!["/run", "/test-whatsapp"].includes(pathname)) return jsonResponse({ error: "not found" }, 404);
    if (request.method !== "POST") return jsonResponse({ error: "method not allowed" }, 405);
    if (!authorized(request, env)) return jsonResponse({ error: "unauthorized" }, 401);
    if (pathname === "/test-whatsapp") {
      await sendWhatsApp(env, "Teste do jt-monitor: Cloudflare Worker e Green API configurados com sucesso!");
      return jsonResponse({ status: "sent" });
    }
    return jsonResponse({ status: "completed", results: await runAll(env) });
  },
};
