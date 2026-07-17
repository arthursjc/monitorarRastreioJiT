#!/usr/bin/env python3
"""
Monitora rastreio J&T Express Brasil.
Variaveis de ambiente:
  WAYBILL_NO        Numeros separados por virgula
  WAYBILL_LABELS    Apelidos: "888030708823905=Tenis Nike,123=Livro"
  CPF               CPF do destinatario
  CORREIOS_CODES    Codigos Correios/Sedex separados por virgula
  CORREIOS_LABELS   Apelidos: "AD687043754BR=Pedido Sedex"
  PACOTEVICIO_API_KEY  Chave RapidAPI para rastreio Correios/J&T via PacoteVicio
  CALLMEBOT_PHONE   Ex: 5512988416345
  CALLMEBOT_APIKEY  API key CallMeBot
  STATE_DIR         Pasta de estado (default: state)
"""

import hashlib
import json
import os
import random
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests

JT_URL = "https://official.jtjms-br.com/official/logisticsTracking/v2/getDetailByWaybillNo"
APP_ID  = "3B29A9C5728BF3E1DB0C4D66B79748B7"
JT_KEY  = "94bbcac67ab47c736d530efe3e1dc358"
TRACKING_URL = "https://www.jtexpress.com.br/trajectquery?waybillNo="
MAX_FAIL = 3

JADLOG_URL = "https://www.jadlog.com.br/jadlog/rastreio"
JADLOG_TRACKING_URL = "https://www.jadlog.com.br/jadlog/rastreio?cte="
JADLOG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
    ),
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.jadlog.com.br/jadlog/captcha",
    "Origin": "https://www.jadlog.com.br",
}

CORREIOS_TRACKING_URL = "https://rastreamento.correios.com.br/app/index.php?objeto="
PACOTEVICIO_URL = "https://correios-rastreamento-de-encomendas.p.rapidapi.com/track"
PACOTEVICIO_HOST = "correios-rastreamento-de-encomendas.p.rapidapi.com"
PACOTEVICIO_JT_URL = "https://correios-rastreamento-de-encomendas.p.rapidapi.com/track"
PACOTEVICIO_JT_HOST = "correios-rastreamento-de-encomendas.p.rapidapi.com"
JT_PACOTEVICIO_MIN_INTERVAL_MINUTES = 120


DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Cache-Control": "max-age=2, must-revalidate",
    "Content-Type": "application/json",
    "Origin": "https://www.jtexpress.com.br",
    "Referer": "https://www.jtexpress.com.br/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "appId": APP_ID,
    "clientSource": "web",
    "countryId": "1",
    "langType": "PT",
    "timezone": "GMT-0300",
}

DELIVERY_KEYWORDS = ["entregue", "entrega realizada", "delivered", "pedido entregue"]

EMOJI_MAP = [
    (["entregue", "entrega realizada", "pedido entregue", "delivered"],    "✅"),
    (["saiu para entrega", "em rota", "retirou", "out for delivery"],      "🛵"),
    (["saída", "saiu", "enviada para"],                                    "📤"),
    (["chegada", "chegou", "recebido no"],                                 "📍"),
    (["coletado", "coleta", "etiqueta comprada", "postado"],               "📦"),
    (["tentativa", "ausente", "nao entregue", "falha", "ocorrencia"],      "❌"),
    (["devolucao", "devolvido", "retorno"],                                "🔄"),
    (["em transito", "transporte", "encaminhada", "transferencia"],        "🚚"),
]

HUB_MAP = {
    "SN RAO": "Ribeirão Preto", "RAO": "Ribeirão Preto",
    "ARA-SP": "Araraquara",     "ARA": "Araraquara",
    "SJC-SP": "São José dos Campos", "SJC": "São José dos Campos",
    "SP BRE": "Barueri",        "BRE": "Barueri",
    "HQ":     "São Paulo",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        print(f"[erro] variavel {name} obrigatoria nao definida", file=sys.stderr)
        sys.exit(2)
    return value


def parse_labels(raw):
    labels = {}
    if not raw:
        return labels
    for part in raw.split(","):
        if "=" in part:
            k, _, v = part.partition("=")
            labels[k.strip()] = v.strip()
    return labels


def pick_emoji(text):
    lower = text.lower()
    for keywords, emoji in EMOJI_MAP:
        if any(k in lower for k in keywords):
            return emoji
    return "📬"


def format_datetime(raw):
    if not raw:
        return ""
    try:
        raw = str(raw).replace("T", " ")
        dt = datetime.strptime(raw[:16], "%Y-%m-%d %H:%M")
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return str(raw)


def clean_text(status, desc):
    import re
    text = f"{status or ''} {desc or ''}".strip()
    # Substitui delimitadores CJK por espaco
    text = text.replace("【", " ").replace("】", " ")
    # Substitui siglas conhecidas pelo nome da cidade, mas so se a cidade ainda nao aparece no texto
    import unicodedata
    def _norm(s):
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    text_norm = _norm(text)
    for sigla, cidade in HUB_MAP.items():
        replacement = "" if _norm(cidade) in text_norm else cidade
        text = text.replace(f"[{sigla}]", replacement)
    # Remove siglas desconhecidas entre colchetes (so maiusculas/digitos/traco)
    text = re.sub(r"\[[A-Z0-9]{1,4}[\s\-][A-Z0-9]{1,4}\]", "", text)
    text = re.sub(r"\[[A-Z0-9]{2,5}\]", "", text)
    # Colchetes com texto legivel (cidade) → remove os colchetes, mantém o texto
    text = re.sub(r"\[([^\]]+)\]", r"\1", text)
    # Remove anonimizacao: A****L
    text = re.sub(r"\b\w\*{2,}\w\b", "", text)
    # Remove aviso de reclamacao que aparece apos ponto final
    text = re.sub(r"\.?\s*[Ss]e voc\S+ tiver.*", "", text)
    text = re.sub(r",?\s*ligue para.*", "", text, flags=re.IGNORECASE)
    # Remove palavras/pontuacao sobrando no final (repeticao para multiplos casos)
    for _ in range(3):
        text = re.sub(r"[,\s]+(para|de|do|da|operador|enviada|e)\s*$", "", text, flags=re.IGNORECASE)
        text = text.rstrip(" ,.")
    # Limpa espacos
    text = re.sub(r"\s{2,}", " ", text).strip()
    if len(text) > 150:
        text = text[:147] + "..."
    return text


def is_delivered(ev):
    text = f"{ev.get('status','')} {ev.get('desc','')}".lower()
    return any(k in text for k in DELIVERY_KEYWORDS)


# ── sign / fetch ──────────────────────────────────────────────────────────────

def obj_key_sort(data):
    if not isinstance(data, dict):
        return data
    result = {}
    for k in sorted(data.keys()):
        v = data[k]
        if isinstance(v, list):
            result[k] = [obj_key_sort(i) if isinstance(i, dict) else i for i in v]
        elif isinstance(v, dict):
            result[k] = obj_key_sort(v)
        elif v is not None:
            result[k] = v
    return result


def build_sign(timestamp, nonce, payload):
    clean = {k: v for k, v in payload.items() if v is not None}
    body = json.dumps(obj_key_sort(clean), separators=(",", ":"), ensure_ascii=False)
    raw = f"{APP_ID}{timestamp}{nonce}{body}{JT_KEY}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def pacotevicio_headers(host):
    api_key = env("PACOTEVICIO_API_KEY", required=True)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-RapidAPI-Key": api_key,
    }
    if host:
        headers["X-RapidAPI-Host"] = host
    return headers


def fetch_pacotevicio(service, url, host, params):
    r = requests.get(
        url,
        headers=pacotevicio_headers(host),
        params=params,
        timeout=45,
    )
    if r.status_code in (401, 403):
        raise RuntimeError(f"PacoteVicio recusou a chave RapidAPI para {service}")
    if r.status_code == 429:
        raise RuntimeError(f"PacoteVicio limitou as consultas de {service} (HTTP 429)")
    r.raise_for_status()
    return r.json()


# ── jadlog fetch / parse ──────────────────────────────────────────────────────

def fetch_jadlog(cte):
    r = requests.post(JADLOG_URL, headers=JADLOG_HEADERS, data={"cte": cte}, timeout=20)
    r.raise_for_status()
    return r.text


def extract_jadlog_events(html):
    import re as _re
    events = []
    pattern = r'class="txt-status">(.*?)<br[^>]*>\s*<small class="txt-data">(.*?)</small>'
    for status_raw, date_raw in _re.findall(pattern, html, _re.DOTALL):
        status = _re.sub(r"<[^>]+>", "", status_raw).strip()
        date_str = date_raw.strip()
        if status:
            events.append({"time": date_str, "status": status, "desc": "", "deliveryName": ""})
    return events


def is_jadlog_delivered(ev):
    import unicodedata
    def norm(s):
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    text = norm(f"{ev.get('status','')} {ev.get('desc','')}")
    # Entrega final ao destinatario — exclui eventos de ponto de coleta/apoio
    return "destinatario" in text


def format_datetime_jadlog(raw):
    # "19/05/2026 - 16:39" → "19/05 16:39"
    if not raw:
        return ""
    try:
        date_part, time_part = raw.strip().split(" - ", 1)
        day, month, _ = date_part.split("/")
        return f"{day}/{month} {time_part.strip()}"
    except Exception:
        return str(raw)


def build_jadlog_message(cte, label, new_events):
    name = label or cte
    lines = [f"📦 Jadlog - {name}"]
    for ev in new_events[:3]:
        status = ev.get("status", "")
        emoji = pick_emoji(status)
        dt = format_datetime_jadlog(ev.get("time"))
        lines.append(f"\n{emoji} {dt}\n{status}")
    lines.append(f"\n🔗 {JADLOG_TRACKING_URL}{cte}")
    return "\n".join(lines)


def build_jadlog_delivered_message(cte, label):
    name = label or cte
    return (
        f"✅ Jadlog - {name}\n\n"
        f"Sua encomenda foi entregue! 🎉\n\n"
        f"🔗 {JADLOG_TRACKING_URL}{cte}"
    )


def build_jadlog_error_message(cte, label):
    name = label or cte
    return (
        f"⚠️ Jadlog - {name}\n\n"
        f"Falha ao consultar rastreio por {MAX_FAIL} vezes seguidas. Verifique manualmente.\n\n"
        f"🔗 {JADLOG_TRACKING_URL}{cte}"
    )


# ── correios / sedex fetch / parse ────────────────────────────────────────────

def fetch_correios(code):
    params = {
        "tracking_code": code,
        "confidence_level": env("PACOTEVICIO_CONFIDENCE_LEVEL", "medium"),
    }
    return fetch_pacotevicio(
        "Correios",
        env("PACOTEVICIO_URL", PACOTEVICIO_URL),
        env("PACOTEVICIO_RAPIDAPI_HOST", PACOTEVICIO_HOST),
        params,
    )


def _strip_html(raw):
    import html
    import re
    text = re.sub(r"<br\s*/?>", " ", raw or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _parse_correios_datetime(raw):
    import re
    text = _strip_html(raw)
    if not text:
        return ""
    try:
        dt = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    m = re.search(r"(\d{2})/(\d{2})/(\d{2})\s+(\d{2}:\d{2})", text)
    if not m:
        return text
    day, month, year, hour = m.groups()
    return f"20{year}-{month}-{day} {hour}"


def _correios_unit_text(unit):
    if not isinstance(unit, dict):
        return ""

    parts = []
    unit_type = unit.get("tipo")
    if unit_type:
        parts.append(str(unit_type))

    address = unit.get("endereco") or {}
    if isinstance(address, dict):
        city = address.get("cidade")
        uf = address.get("uf")
        if city and uf:
            parts.append(f"{city}/{uf}")
        elif city:
            parts.append(str(city))
        elif uf:
            parts.append(str(uf))

    return " - ".join(parts)


def _correios_event_time(ev):
    raw = ev.get("dtHrCriado") or ev.get("data") or ev.get("time") or ev.get("timeStr")
    if isinstance(raw, dict):
        raw = raw.get("date") or raw.get("datetime")
    return _parse_correios_datetime(raw)


def extract_correios_events(data):
    events = []

    if isinstance(data, dict):
        root = data.get("correios_object") or data.get("data") or data
        raw_events = root.get("eventos") or root.get("events") or root.get("historico") or []
    elif isinstance(data, list):
        raw_events = data
    else:
        raw_events = []

    for ev in raw_events:
        if not isinstance(ev, dict):
            continue

        status = (
            ev.get("descricaoFrontEnd")
            or ev.get("descricaoWeb")
            or ev.get("descricao")
            or ev.get("status")
            or ev.get("statusDesc")
            or ""
        )
        desc_parts = [
            ev.get("descricao") if ev.get("descricao") != status else "",
            ev.get("detalhe"),
            _correios_unit_text(ev.get("unidade")),
        ]
        desc = " | ".join(_strip_html(part) for part in desc_parts if part)
        events.append({
            "time": _correios_event_time(ev),
            "status": _strip_html(status),
            "desc": desc,
            "deliveryName": "",
        })
    return events


def build_correios_message(code, label, new_events):
    name = label or code
    lines = [f"📦 Correios/Sedex - {name}"]
    for ev in new_events[:3]:
        text = clean_text(ev.get("status"), ev.get("desc"))
        emoji = pick_emoji(text)
        dt = format_datetime(ev.get("time"))
        lines.append(f"\n{emoji} {dt}\n{text}")
    lines.append(f"\n🔗 {CORREIOS_TRACKING_URL}{code}")
    return "\n".join(lines)


def build_correios_delivered_message(code, label):
    name = label or code
    return (
        f"✅ Correios/Sedex - {name}\n\n"
        f"Sua encomenda foi entregue! 🎉\n\n"
        f"🔗 {CORREIOS_TRACKING_URL}{code}"
    )


def build_correios_error_message(code, label):
    name = label or code
    return (
        f"⚠️ Correios/Sedex - {name}\n\n"
        f"Falha ao consultar rastreio por {MAX_FAIL} vezes seguidas. Verifique manualmente.\n\n"
        f"🔗 {CORREIOS_TRACKING_URL}{code}"
    )


def track_one_correios(code, state_dir, label):
    state_path = Path(state_dir) / f"correios_{code}.json"
    state = load_state(state_path)

    if state.get("delivered"):
        print(f"[skip] correios {code} ja entregue")
        return

    try:
        data = fetch_correios(code)
    except Exception as e:
        print(f"[erro] correios {code} fetch falhou: {e}", file=sys.stderr)
        fail_count = state.get("fail_count", 0) + 1
        state["fail_count"] = fail_count
        save_state(state_path, state)
        if fail_count >= MAX_FAIL:
            print(f"[alerta] correios {code} {fail_count} falhas, notificando")
            try:
                send_whatsapp(build_correios_error_message(code, label))
            except Exception:
                pass
        return

    new_events = extract_correios_events(data)
    print(f"[ok] correios {code} {len(new_events)} eventos")

    old_events = state.get("events", [])
    new_only = diff_events(old_events, new_events)

    state.update({
        "events": new_events,
        "fail_count": 0,
        "first_seen_at": state.get("first_seen_at") or datetime.utcnow().isoformat(),
        "last_status": new_events[0].get("status") if new_events else state.get("last_status"),
        "delivered": state.get("delivered", False),
        "delivered_at": state.get("delivered_at"),
    })

    if not new_only:
        print(f"[ok] correios {code} sem mudancas")
        save_state(state_path, state)
        return

    print(f"[novo] correios {code} {len(new_only)} eventos novos")

    delivery_ev = next((e for e in new_only if is_delivered(e)), None)
    if delivery_ev:
        state["delivered"] = True
        state["delivered_at"] = delivery_ev.get("time") or datetime.utcnow().isoformat()
        print(f"[entregue] correios {code}")
        try:
            send_whatsapp(build_correios_delivered_message(code, label))
        except Exception as e:
            print(f"[erro] envio whatsapp: {e}", file=sys.stderr)
    else:
        try:
            send_whatsapp(build_correios_message(code, label, new_only))
        except Exception as e:
            print(f"[erro] envio whatsapp: {e}", file=sys.stderr)

    save_state(state_path, state)


def track_one_jadlog(cte, state_dir, label):
    state_path = Path(state_dir) / f"jadlog_{cte}.json"
    state = load_state(state_path)

    if state.get("delivered"):
        print(f"[skip] jadlog {cte} ja entregue")
        return

    try:
        html = fetch_jadlog(cte)
    except Exception as e:
        print(f"[erro] jadlog {cte} fetch falhou: {e}", file=sys.stderr)
        fail_count = state.get("fail_count", 0) + 1
        state["fail_count"] = fail_count
        save_state(state_path, state)
        if fail_count >= MAX_FAIL:
            print(f"[alerta] jadlog {cte} {fail_count} falhas, notificando")
            try:
                send_whatsapp(build_jadlog_error_message(cte, label))
            except Exception:
                pass
        return

    new_events = extract_jadlog_events(html)
    print(f"[ok] jadlog {cte} {len(new_events)} eventos")

    old_events = state.get("events", [])
    new_only = diff_events(old_events, new_events)

    state.update({
        "events": new_events,
        "fail_count": 0,
        "first_seen_at": state.get("first_seen_at") or datetime.utcnow().isoformat(),
        "last_status": new_events[-1].get("status") if new_events else state.get("last_status"),
        "delivered": state.get("delivered", False),
        "delivered_at": state.get("delivered_at"),
    })

    if not new_only:
        print(f"[ok] jadlog {cte} sem mudancas")
        save_state(state_path, state)
        return

    print(f"[novo] jadlog {cte} {len(new_only)} eventos novos")

    delivery_ev = next((e for e in new_only if is_jadlog_delivered(e)), None)
    if delivery_ev:
        state["delivered"] = True
        state["delivered_at"] = delivery_ev.get("time") or datetime.utcnow().isoformat()
        print(f"[entregue] jadlog {cte}")
        try:
            send_whatsapp(build_jadlog_delivered_message(cte, label))
        except Exception as e:
            print(f"[erro] envio whatsapp: {e}", file=sys.stderr)
    else:
        try:
            send_whatsapp(build_jadlog_message(cte, label, new_only))
        except Exception as e:
            print(f"[erro] envio whatsapp: {e}", file=sys.stderr)

    save_state(state_path, state)


# ── J&T fetch ─────────────────────────────────────────────────────────────────

def jt_provider():
    default = "pacotevicio" if env("PACOTEVICIO_API_KEY") else "official"
    return env("JT_PROVIDER", default).strip().lower()


def fetch_tracking(waybill, cpf, provider=None):
    provider = provider or jt_provider()
    if provider == "official":
        return fetch_tracking_official(waybill, cpf)
    return fetch_tracking_pacotevicio(waybill, cpf)


def fetch_tracking_pacotevicio(waybill, cpf):
    params = {
        "tracking_code": waybill,
        "confidence_level": env("PACOTEVICIO_CONFIDENCE_LEVEL", "medium"),
        "document": "".join(ch for ch in str(cpf) if ch.isdigit()),
    }
    return fetch_pacotevicio(
        "J&T",
        env("PACOTEVICIO_JT_URL", PACOTEVICIO_JT_URL),
        env("PACOTEVICIO_JT_HOST", PACOTEVICIO_JT_HOST),
        params,
    )


def fetch_tracking_official(waybill, cpf):
    payload = {"cpf": cpf, "waybillNo": waybill, "langType": "PT"}
    timestamp = str(int(time.time() * 1000))
    nonce = f"0.{random.randint(10**14, 10**15-1)}"
    sign = build_sign(timestamp, nonce, payload)
    headers = dict(DEFAULT_HEADERS)
    headers.update({"key": JT_KEY, "timestamp": timestamp, "nonce": nonce, "sign": sign})
    r = requests.post(JT_URL, headers=headers, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def extract_events(data):
    events = []
    root = (data or {}).get("jtexpress_object") or (data or {}).get("data") or (data or {})
    for d in (root.get("details") or []):
        sub = d.get("pathInfo") or d.get("traces")
        items = sub if sub else [d]
        for p in items:
            events.append({
                "time":   p.get("scanTime") or p.get("acceptTime") or p.get("time"),
                "status": p.get("status") or p.get("scanTypeName") or p.get("scanType") or "",
                "desc":   p.get("customerTracking") or p.get("acceptAddress") or p.get("desc") or "",
                "deliveryName": p.get("deliveryName") or d.get("deliveryName") or "",
            })
    return events


def event_key(ev):
    return f"{ev.get('time','')}|{ev.get('status','')}|{ev.get('desc','')}"


def diff_events(old, new):
    old_keys = {event_key(e) for e in old}
    return [e for e in new if event_key(e) not in old_keys]


def should_skip_recent_check(state, key, min_minutes):
    if min_minutes <= 0:
        return False
    raw = state.get(key)
    if not raw:
        return False
    try:
        last = datetime.fromisoformat(str(raw))
        elapsed = (datetime.utcnow() - last).total_seconds() / 60
        return elapsed < min_minutes
    except Exception:
        return False


# ── estado ────────────────────────────────────────────────────────────────────

def load_state(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path, state):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ── mensagens ─────────────────────────────────────────────────────────────────

def build_message(waybill, label, new_events):
    name = label or waybill
    lines = [f"📦 J&T - {name}"]
    for ev in new_events[:3]:
        text = clean_text(ev.get("status"), ev.get("desc"))
        emoji = pick_emoji(text)
        dt = format_datetime(ev.get("time"))
        lines.append(f"\n{emoji} {dt}\n{text}")
    lines.append(f"\n🔗 {TRACKING_URL}{waybill}")
    return "\n".join(lines)


def build_delivered_message(waybill, label):
    name = label or waybill
    return f"✅ J&T - {name}\n\nSua encomenda foi entregue com sucesso! 🎉\n\n🔗 {TRACKING_URL}{waybill}"


def build_error_message(waybill, label):
    name = label or waybill
    return f"⚠️ J&T - {name}\n\nFalha ao consultar rastreio por {MAX_FAIL} vezes seguidas. Verifique manualmente.\n\n🔗 {TRACKING_URL}{waybill}"


# ── WhatsApp ──────────────────────────────────────────────────────────────────

def send_whatsapp(message):
    phone = env("CALLMEBOT_PHONE", required=True).strip().lstrip("+")
    apikey = env("CALLMEBOT_APIKEY", required=True).strip()
    # Monta URL manualmente para evitar double-encoding do requests
    text_encoded = urllib.parse.quote(message, safe="")
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={text_encoded}&apikey={apikey}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
    r = requests.get(url, headers=headers, timeout=20)
    print(f"[callmebot] status={r.status_code} body={r.text[:200]}")

    if r.status_code == 403:
        # Fallback: mensagem simples sem emojis para diagnostico
        simple = urllib.parse.quote(f"J&T tracker: {message[:80]}", safe="")
        url2 = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={simple}&apikey={apikey}"
        r2 = requests.get(url2, headers=headers, timeout=20)
        print(f"[callmebot-fallback] status={r2.status_code} body={r2.text[:200]}")


# ── tracker principal ─────────────────────────────────────────────────────────

def track_one(waybill, cpf, state_dir, label):
    state_path = Path(state_dir) / f"{waybill}.json"
    state = load_state(state_path)
    provider = jt_provider()
    min_interval = int(env("JT_PACOTEVICIO_MIN_INTERVAL_MINUTES", JT_PACOTEVICIO_MIN_INTERVAL_MINUTES))

    if state.get("delivered"):
        print(f"[skip] {waybill} ja entregue")
        return

    if provider == "pacotevicio" and should_skip_recent_check(state, "last_checked_at", min_interval):
        print(f"[skip] {waybill} consulta J&T recente; aguardando intervalo de {min_interval} min")
        return

    try:
        data = fetch_tracking(waybill, cpf, provider)
    except Exception as e:
        print(f"[erro] {waybill} fetch falhou: {e}", file=sys.stderr)
        fail_count = state.get("fail_count", 0) + 1
        state["fail_count"] = fail_count
        if provider == "pacotevicio":
            state["last_checked_at"] = datetime.utcnow().isoformat()
        save_state(state_path, state)
        if fail_count >= MAX_FAIL:
            print(f"[alerta] {waybill} {fail_count} falhas, notificando")
            try:
                send_whatsapp(build_error_message(waybill, label))
            except Exception:
                pass
        return

    new_events = extract_events(data)
    print(f"[ok] {waybill} {len(new_events)} eventos")

    old_events = state.get("events", [])
    new_only = diff_events(old_events, new_events)

    state.update({
        "events": new_events,
        "fail_count": 0,
        "first_seen_at": state.get("first_seen_at") or datetime.utcnow().isoformat(),
        "last_checked_at": datetime.utcnow().isoformat() if provider == "pacotevicio" else state.get("last_checked_at"),
        "last_status": new_events[0].get("status") if new_events else state.get("last_status"),
        "delivered": state.get("delivered", False),
        "delivered_at": state.get("delivered_at"),
    })

    if not new_only:
        print(f"[ok] {waybill} sem mudancas")
        save_state(state_path, state)
        return

    print(f"[novo] {waybill} {len(new_only)} eventos novos")

    delivery_ev = next((e for e in new_only if is_delivered(e)), None)
    if delivery_ev:
        state["delivered"] = True
        state["delivered_at"] = delivery_ev.get("time") or datetime.utcnow().isoformat()
        print(f"[entregue] {waybill}")
        try:
            send_whatsapp(build_delivered_message(waybill, label))
        except Exception as e:
            print(f"[erro] envio whatsapp: {e}", file=sys.stderr)
    else:
        try:
            send_whatsapp(build_message(waybill, label, new_only))
        except Exception as e:
            print(f"[erro] envio whatsapp: {e}", file=sys.stderr)

    save_state(state_path, state)


def main():
    state_dir = env("STATE_DIR", "state")

    waybill_raw = env("WAYBILL_NO", "")
    if waybill_raw:
        cpf = env("CPF", required=True)
        waybills = [w.strip() for w in waybill_raw.split(",") if w.strip()]
        labels = parse_labels(env("WAYBILL_LABELS", ""))
        for waybill in waybills:
            track_one(waybill, cpf, state_dir, labels.get(waybill))

    jadlog_raw = env("JADLOG_CTE", "")
    if jadlog_raw:
        jadlog_ctes = [c.strip() for c in jadlog_raw.split(",") if c.strip()]
        jadlog_labels = parse_labels(env("JADLOG_LABELS", ""))
        for cte in jadlog_ctes:
            track_one_jadlog(cte, state_dir, jadlog_labels.get(cte))

    correios_raw = env("CORREIOS_CODES", "")
    if correios_raw:
        correios_codes = [c.strip().upper() for c in correios_raw.split(",") if c.strip()]
        correios_labels = parse_labels(env("CORREIOS_LABELS", ""))
        for code in correios_codes:
            track_one_correios(code, state_dir, correios_labels.get(code))


if __name__ == "__main__":
    main()
