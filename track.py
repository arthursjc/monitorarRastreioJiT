#!/usr/bin/env python3
"""
Monitora rastreio J&T Express Brasil.
Variaveis de ambiente:
  WAYBILL_NO        Numeros separados por virgula
  WAYBILL_LABELS    Apelidos: "888030708823905=Tenis Nike,123=Livro"
  CPF               CPF do destinatario
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
    "SN RAO": "Ribeirao Preto", "RAO": "Ribeirao Preto",
    "ARA-SP": "Araraquara",     "ARA": "Araraquara",
    "SJC-SP": "Sao Jose dos Campos", "SJC": "Sao Jose dos Campos",
    "SP BRE": "Barueri",        "BRE": "Barueri",
    "HQ":     "Sao Paulo",
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
    # Substitui delimitadores CJK
    text = text.replace("【", "(").replace("】", ")")
    # Remove siglas de hub entre colchetes
    text = re.sub(r"\[[A-Z]{2,3}[\s\-][A-Z]{2,3}\]", "", text)
    text = re.sub(r"\[[A-Z]{2,4}\]", "", text)
    # Resolve siglas soltas
    for sigla, cidade in HUB_MAP.items():
        text = text.replace(f"[{sigla}]", cidade)
        text = text.replace(sigla, "")
    # Remove prefixo de cidade no inicio: "[Cidade] texto" -> "texto"
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    # Remove colchetes vazios
    text = re.sub(r"\[\s*\]", "", text)
    # Remove anonimizacao: A****L
    text = re.sub(r"\b\w\*{2,}\w\b", "", text)
    # Remove telefone de reclamacao
    text = re.sub(r",?\s*se voce tiver[^.]*\.", "", text, flags=re.IGNORECASE)
    text = re.sub(r",?\s*ligue para[^.]*\.", "", text, flags=re.IGNORECASE)
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


def fetch_tracking(waybill, cpf):
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
    root = (data or {}).get("data") or {}
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
    for ev in new_events[:5]:
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
    phone = env("CALLMEBOT_PHONE", required=True)
    apikey = env("CALLMEBOT_APIKEY", required=True)
    # Garante + no inicio
    if not phone.startswith("+"):
        phone = "+" + phone
    params = {"phone": phone, "text": message, "apikey": apikey}
    url = "https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode(params)
    r = requests.get(url, timeout=20)
    print(f"[callmebot] status={r.status_code} body={r.text[:200]}")


# ── tracker principal ─────────────────────────────────────────────────────────

def track_one(waybill, cpf, state_dir, label):
    state_path = Path(state_dir) / f"{waybill}.json"
    state = load_state(state_path)

    if state.get("delivered"):
        print(f"[skip] {waybill} ja entregue")
        return

    try:
        data = fetch_tracking(waybill, cpf)
    except Exception as e:
        print(f"[erro] {waybill} fetch falhou: {e}", file=sys.stderr)
        fail_count = state.get("fail_count", 0) + 1
        state["fail_count"] = fail_count
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
    cpf = env("CPF", required=True)
    state_dir = env("STATE_DIR", "state")
    waybills = [w.strip() for w in env("WAYBILL_NO", required=True).split(",") if w.strip()]
    labels = parse_labels(env("WAYBILL_LABELS", ""))

    for waybill in waybills:
        track_one(waybill, cpf, state_dir, labels.get(waybill))


if __name__ == "__main__":
    main()
