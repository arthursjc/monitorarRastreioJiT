const JT_URL = "https://official.jtjms-br.com/official/logisticsTracking/v2/getDetailByWaybillNo";
const APP_ID = "3B29A9C5728BF3E1DB0C4D66B79748B7";
const JT_KEY = "94bbcac67ab47c736d530efe3e1dc358";

// ── MD5 (pure JS, sem dependencias externas) ─────────────────────────────────
function md5(str) {
  function safeAdd(x, y) { const lsw = (x & 0xffff) + (y & 0xffff); return (((x >> 16) + (y >> 16) + (lsw >> 16)) << 16) | (lsw & 0xffff); }
  function bitRotateLeft(num, cnt) { return (num << cnt) | (num >>> (32 - cnt)); }
  function md5cmn(q, a, b, x, s, t) { return safeAdd(bitRotateLeft(safeAdd(safeAdd(a, q), safeAdd(x, t)), s), b); }
  function md5ff(a, b, c, d, x, s, t) { return md5cmn((b & c) | (~b & d), a, b, x, s, t); }
  function md5gg(a, b, c, d, x, s, t) { return md5cmn((b & d) | (c & ~d), a, b, x, s, t); }
  function md5hh(a, b, c, d, x, s, t) { return md5cmn(b ^ c ^ d, a, b, x, s, t); }
  function md5ii(a, b, c, d, x, s, t) { return md5cmn(c ^ (b | ~d), a, b, x, s, t); }
  function strToUtf8(s) {
    const bytes = [];
    for (let i = 0; i < s.length; i++) {
      let c = s.charCodeAt(i);
      if (c < 128) { bytes.push(c); }
      else if (c < 2048) { bytes.push((c >> 6) | 192, (c & 63) | 128); }
      else { bytes.push((c >> 12) | 224, ((c >> 6) & 63) | 128, (c & 63) | 128); }
    }
    return bytes;
  }
  function bytesToWords(bytes) {
    const words = new Array(Math.ceil(bytes.length / 4)).fill(0);
    for (let i = 0; i < bytes.length; i++) words[i >> 2] |= bytes[i] << ((i % 4) * 8);
    return words;
  }
  const bytes = strToUtf8(str);
  const len = bytes.length;
  bytes.push(0x80);
  while (bytes.length % 64 !== 56) bytes.push(0);
  const lenBits = len * 8;
  bytes.push(lenBits & 0xff, (lenBits >> 8) & 0xff, (lenBits >> 16) & 0xff, (lenBits >> 24) & 0xff, 0, 0, 0, 0);
  const m = bytesToWords(bytes);
  let a = 0x67452301, b = 0xefcdab89, c = 0x98badcfe, d = 0x10325476;
  for (let i = 0; i < m.length; i += 16) {
    const [aa, bb, cc, dd] = [a, b, c, d];
    a = md5ff(a,b,c,d,m[i],7,-680876936);     d = md5ff(d,a,b,c,m[i+1],12,-389564586);  c = md5ff(c,d,a,b,m[i+2],17,606105819);   b = md5ff(b,c,d,a,m[i+3],22,-1044525330);
    a = md5ff(a,b,c,d,m[i+4],7,-176418897);   d = md5ff(d,a,b,c,m[i+5],12,1200080426);  c = md5ff(c,d,a,b,m[i+6],17,-1473231341); b = md5ff(b,c,d,a,m[i+7],22,-45705983);
    a = md5ff(a,b,c,d,m[i+8],7,1770035416);   d = md5ff(d,a,b,c,m[i+9],12,-1958414417); c = md5ff(c,d,a,b,m[i+10],17,-42063);     b = md5ff(b,c,d,a,m[i+11],22,-1990404162);
    a = md5ff(a,b,c,d,m[i+12],7,1804603682);  d = md5ff(d,a,b,c,m[i+13],12,-40341101);  c = md5ff(c,d,a,b,m[i+14],17,-1502002290);b = md5ff(b,c,d,a,m[i+15],22,1236535329);
    a = md5gg(a,b,c,d,m[i+1],5,-165796510);   d = md5gg(d,a,b,c,m[i+6],9,-1069501632);  c = md5gg(c,d,a,b,m[i+11],14,643717713);  b = md5gg(b,c,d,a,m[i],20,-373897302);
    a = md5gg(a,b,c,d,m[i+5],5,-701558691);   d = md5gg(d,a,b,c,m[i+10],9,38016083);    c = md5gg(c,d,a,b,m[i+15],14,-660478335); b = md5gg(b,c,d,a,m[i+4],20,-405537848);
    a = md5gg(a,b,c,d,m[i+9],5,568446438);    d = md5gg(d,a,b,c,m[i+14],9,-1019803690); c = md5gg(c,d,a,b,m[i+3],14,-187363961);  b = md5gg(b,c,d,a,m[i+8],20,1163531501);
    a = md5gg(a,b,c,d,m[i+13],5,-1444681467); d = md5gg(d,a,b,c,m[i+2],9,-51403784);    c = md5gg(c,d,a,b,m[i+7],14,1735328473);  b = md5gg(b,c,d,a,m[i+12],20,-1926607734);
    a = md5hh(a,b,c,d,m[i+5],4,-378558);      d = md5hh(d,a,b,c,m[i+8],11,-2022574463); c = md5hh(c,d,a,b,m[i+11],16,1839030562); b = md5hh(b,c,d,a,m[i+14],23,-35309556);
    a = md5hh(a,b,c,d,m[i+1],4,-1530992060);  d = md5hh(d,a,b,c,m[i+4],11,1272893353);  c = md5hh(c,d,a,b,m[i+7],16,-155497632);  b = md5hh(b,c,d,a,m[i+10],23,-1094730640);
    a = md5hh(a,b,c,d,m[i+13],4,681279174);   d = md5hh(d,a,b,c,m[i],11,-358537222);    c = md5hh(c,d,a,b,m[i+3],16,-722521979);  b = md5hh(b,c,d,a,m[i+6],23,76029189);
    a = md5hh(a,b,c,d,m[i+9],4,-640364487);   d = md5hh(d,a,b,c,m[i+12],11,-421815835); c = md5hh(c,d,a,b,m[i+15],16,530742520);  b = md5hh(b,c,d,a,m[i+2],23,-995338651);
    a = md5ii(a,b,c,d,m[i],6,-198630844);      d = md5ii(d,a,b,c,m[i+7],10,1126891415);  c = md5ii(c,d,a,b,m[i+14],15,-1416354905);b = md5ii(b,c,d,a,m[i+5],21,-57434055);
    a = md5ii(a,b,c,d,m[i+12],6,1700485571);  d = md5ii(d,a,b,c,m[i+3],10,-1894986606); c = md5ii(c,d,a,b,m[i+10],15,-1051523);   b = md5ii(b,c,d,a,m[i+1],21,-2054922799);
    a = md5ii(a,b,c,d,m[i+8],6,1873313359);   d = md5ii(d,a,b,c,m[i+15],10,-30611744);  c = md5ii(c,d,a,b,m[i+6],15,-1560198380); b = md5ii(b,c,d,a,m[i+13],21,1309151649);
    a = md5ii(a,b,c,d,m[i+4],6,-145523070);   d = md5ii(d,a,b,c,m[i+11],10,-1120210379);c = md5ii(c,d,a,b,m[i+2],15,718787259);   b = md5ii(b,c,d,a,m[i+9],21,-343485551);
    a = safeAdd(a, aa); b = safeAdd(b, bb); c = safeAdd(c, cc); d = safeAdd(d, dd);
  }
  return [a, b, c, d].map(n => {
    let s = "";
    for (let j = 0; j < 4; j++) s += ("0" + ((n >> (j * 8)) & 0xff).toString(16)).slice(-2);
    return s;
  }).join("").toUpperCase();
}

// ── Sign (replica saveIn.js) ──────────────────────────────────────────────────
function objKeySort(data) {
  if (!data || typeof data !== "object") return data;
  const result = {};
  for (const k of Object.keys(data).sort()) {
    const v = data[k];
    if (Array.isArray(v)) result[k] = v.map(i => typeof i === "object" ? objKeySort(i) : i);
    else if (v !== null && typeof v === "object") result[k] = objKeySort(v);
    else if (v !== null) result[k] = v;
  }
  return result;
}

function buildSign(timestamp, nonce, payload) {
  const clean = Object.fromEntries(Object.entries(payload).filter(([, v]) => v !== null));
  const sorted = objKeySort(clean);
  const body = JSON.stringify(sorted);
  return md5(`${APP_ID}${timestamp}${nonce}${body}${JT_KEY}`);
}

// ── J&T fetch ─────────────────────────────────────────────────────────────────
async function fetchTracking(waybill, cpf) {
  const payload = { cpf, waybillNo: waybill, langType: "PT" };
  const timestamp = String(Date.now());
  const nonce = String(Math.random());
  const sign = buildSign(timestamp, nonce, payload);

  const headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Cache-Control": "max-age=2, must-revalidate",
    "Content-Type": "application/json",
    "Origin": "https://www.jtexpress.com.br",
    "Referer": "https://www.jtexpress.com.br/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
    "appId": APP_ID,
    "clientSource": "web",
    "countryId": "1",
    "langType": "PT",
    "timezone": "GMT-0300",
    "key": JT_KEY,
    "timestamp": timestamp,
    "nonce": nonce,
    "sign": sign,
  };

  const res = await fetch(JT_URL, { method: "POST", headers, body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Parser de eventos ─────────────────────────────────────────────────────────
function extractEvents(data) {
  const events = [];
  const root = data?.data;
  if (!root) return events;
  const details = root.details;
  if (!Array.isArray(details)) return events;
  for (const d of details) {
    const sub = d.pathInfo || d.traces;
    if (sub) {
      for (const p of sub) events.push({ time: p.scanTime || p.acceptTime || p.time, status: p.scanTypeName || p.scanType || p.status, desc: p.customerTracking || p.acceptAddress || p.desc || "" });
    } else {
      events.push({ time: d.scanTime || d.acceptTime || d.time, status: d.scanTypeName || d.scanType || d.status, desc: d.customerTracking || d.acceptAddress || d.desc || "" });
    }
  }
  return events;
}

function eventKey(ev) { return `${ev.time}|${ev.status}|${ev.desc}`; }

function diffEvents(oldEvents, newEvents) {
  const oldKeys = new Set(oldEvents.map(eventKey));
  return newEvents.filter(e => !oldKeys.has(eventKey(e)));
}

// ── GREEN-API ─────────────────────────────────────────────────────────────────
async function sendWhatsapp(message, phone, token) {
  // token format: "idInstance:apiTokenInstance"
  const [idInstance, apiToken] = token.split(":");
  const phoneList = phone.split(",").map(p => p.trim()).filter(Boolean);
  for (const rawPhone of phoneList) {
    const chatId = rawPhone.replace(/^\+/, "").replace(/\D/g, "") + "@c.us";
    const url = `https://api.green-api.com/waInstance${idInstance}/sendMessage/${apiToken}`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chatId, message }),
    });
    const body = await res.text();
    console.log(`[greenapi] phone=${rawPhone} status=${res.status} body=${body.slice(0, 200)}`);
  }
}

// ── Track de uma encomenda ────────────────────────────────────────────────────
async function trackOne(waybill, cpf, phone, apikey, kv) {
  let data;
  try {
    data = await fetchTracking(waybill, cpf);
  } catch (e) {
    console.error(`[erro] ${waybill} fetch falhou: ${e.message}`);
    return;
  }

  const newEvents = extractEvents(data);
  console.log(`[ok] ${waybill} ${newEvents.length} eventos`);

  const stored = await kv.get(waybill, "json") || { events: [] };
  const newOnly = diffEvents(stored.events || [], newEvents);

  if (!newOnly.length) {
    console.log(`[ok] ${waybill} sem mudancas`);
  } else {
    console.log(`[novo] ${waybill} ${newOnly.length} eventos novos`);
    const lines = [`Rastreio J&T ${waybill} atualizado:`];
    for (const ev of newOnly.slice(0, 5)) lines.push(`- ${ev.time}: ${ev.status} ${ev.desc}`.trim());
    await sendWhatsapp(lines.join("\n"), phone, apikey);
  }

  await kv.put(waybill, JSON.stringify({ events: newEvents }));
}

// ── Entry point ───────────────────────────────────────────────────────────────
export default {
  async scheduled(event, env, ctx) {
    const waybills = env.WAYBILL_NO.split(",").map(w => w.trim()).filter(Boolean);
    for (const waybill of waybills) {
      await trackOne(waybill, env.CPF, env.WHAPI_PHONE, env.WHAPI_TOKEN, env.JT_STATE);
    }
  },

  // permite testar via HTTP GET /run
  async fetch(request, env, ctx) {
    if (new URL(request.url).pathname === "/run") {
      const waybills = env.WAYBILL_NO.split(",").map(w => w.trim()).filter(Boolean);
      for (const waybill of waybills) {
        await trackOne(waybill, env.CPF, env.WHAPI_PHONE, env.WHAPI_TOKEN, env.JT_STATE);
      }
      return new Response("ok", { status: 200 });
    }
    return new Response("jt-tracker", { status: 200 });
  },
};
