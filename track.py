#!/usr/bin/env python3
"""
Monitora o rastreio de encomendas J&T Express Brasil.
Compara o estado atual com o anterior salvo em state/<waybill>.json
e dispara um alerta no WhatsApp via CallMeBot quando houver evento novo.

Variaveis de ambiente esperadas:
  CALLMEBOT_PHONE    Numero com codigo do pais, sem +. Ex: 5511999999999
  CALLMEBOT_APIKEY   API key do CallMeBot
  WAYBILL_NO         Um ou mais numeros de rastreio separados por virgula.
                     Ex: 888030695848780
                     Ex: 888030695848780,888030695848781
  CPF                CPF do destinatario. Ex: 41795685867

Opcionais:
  STATE_DIR          Pasta dos arquivos de estado. Default: state
"""

import hashlib
import json
import os
import random
import sys
import time
import urllib.parse
from pathlib import Path

import requests

JT_URL = "https://official.jtjms-br.com/official/logisticsTracking/v2/getDetailByWaybillNo"

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
        "Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
    ),
    "appId": "3B29A9C5728BF3E1DB0C4D66B79748B7",
    "clientSource": "web",
    "countryId": "1",
    "langType": "PT",
    "timezone": "GMT-0300",
}

APP_ID = "3B29A9C5728BF3E1DB0C4D66B79748B7"
JT_KEY = "94bbcac67ab47c736d530efe3e1dc358"


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        print(f"[erro] variavel {name} obrigatoria nao definida", file=sys.stderr)
        sys.exit(2)
    return value


def _obj_key_sort(data):
    if not isinstance(data, dict) or not data:
        return data
    result = {}
    for k in sorted(data.keys()):
        v = data[k]
        if isinstance(v, list):
            result[k] = [_obj_key_sort(i) if isinstance(i, dict) else i for i in v]
        elif isinstance(v, dict):
            result[k] = _obj_key_sort(v)
        elif v is not None:
            result[k] = v
    return result


def build_sign(timestamp, nonce, payload):
    clean = {k: v for k, v in payload.items() if v is not None}
    sorted_payload = _obj_key_sort(clean)
    body = json.dumps(sorted_payload, separators=(",", ":"), ensure_ascii=False)
    raw = f"{APP_ID}{timestamp}{nonce}{body}{JT_KEY}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def build_headers(payload):
    timestamp = str(int(time.time() * 1000))
    nonce = f"0.{random.randint(10**14, 10**15 - 1)}"
    sign = build_sign(timestamp, nonce, payload)
    headers = dict(DEFAULT_HEADERS)
    headers["key"] = JT_KEY
    headers["timestamp"] = timestamp
    headers["nonce"] = nonce
    headers["sign"] = sign
    return headers


def fetch_tracking(waybill, cpf):
    payload = {
        "cpf": cpf,
        "waybillNo": waybill,
        "langType": "PT",
    }
    headers = build_headers(payload)
    r = requests.post(JT_URL, headers=headers, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def extract_events(data):
    events = []
    root = data.get("data") if isinstance(data, dict) else None
    if not root:
        return events

    details = root.get("details") if isinstance(root, dict) else None
    if not isinstance(details, list):
        return events

    for d in details:
        sub = d.get("pathInfo") or d.get("traces")
        if sub:
            for p in sub:
                events.append({
                    "time": p.get("scanTime") or p.get("acceptTime") or p.get("time"),
                    "status": p.get("scanTypeName") or p.get("scanType") or p.get("status"),
                    "desc": p.get("customerTracking") or p.get("acceptAddress") or p.get("desc") or "",
                })
        else:
            events.append({
                "time": d.get("scanTime") or d.get("acceptTime") or d.get("time"),
                "status": d.get("scanTypeName") or d.get("scanType") or d.get("status"),
                "desc": d.get("customerTracking") or d.get("acceptAddress") or d.get("desc") or "",
            })

    return events


def load_state(path):
    p = Path(path)
    if not p.exists():
        return {"events": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"events": []}


def save_state(path, state):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def event_key(ev):
    return f"{ev.get('time','')}|{ev.get('status','')}|{ev.get('desc','')}"


def diff_events(old, new):
    old_keys = {event_key(e) for e in old}
    return [e for e in new if event_key(e) not in old_keys]


def send_whatsapp(message):
    phone = env("CALLMEBOT_PHONE", required=True)
    apikey = env("CALLMEBOT_APIKEY", required=True)
    url = "https://api.callmebot.com/whatsapp.php"
    params = {"phone": phone, "text": message, "apikey": apikey}
    full = url + "?" + urllib.parse.urlencode(params)
    r = requests.get(full, timeout=20)
    print(f"[callmebot] status={r.status_code} body={r.text[:200]}")
    r.raise_for_status()


def track_one(waybill, cpf, state_dir):
    state_path = Path(state_dir) / f"{waybill}.json"

    try:
        data = fetch_tracking(waybill, cpf)
    except requests.HTTPError as e:
        print(f"[erro] {waybill} HTTP {e.response.status_code}: {e.response.text[:400]}", file=sys.stderr)
        return
    except Exception as e:
        print(f"[erro] {waybill} fetch falhou: {e}", file=sys.stderr)
        return

    new_events = extract_events(data)
    print(f"[ok] {waybill} {len(new_events)} eventos no rastreio")

    state = load_state(state_path)
    old_events = state.get("events", [])
    new_only = diff_events(old_events, new_events)

    if not new_only:
        print(f"[ok] {waybill} sem mudancas")
        save_state(state_path, {"events": new_events, "raw": data})
        return

    print(f"[novo] {waybill} {len(new_only)} eventos novos")
    lines = [f"Rastreio J&T {waybill} atualizado:"]
    for ev in new_only[:5]:
        lines.append(f"- {ev.get('time','')}: {ev.get('status','')} {ev.get('desc','')}".strip())
    message = "\n".join(lines)

    try:
        send_whatsapp(message)
    except Exception as e:
        print(f"[erro] {waybill} envio whatsapp falhou: {e}", file=sys.stderr)

    save_state(state_path, {"events": new_events, "raw": data})


def main():
    cpf = env("CPF", required=True)
    state_dir = env("STATE_DIR", "state")
    waybills_raw = env("WAYBILL_NO", required=True)
    waybills = [w.strip() for w in waybills_raw.split(",") if w.strip()]

    for waybill in waybills:
        track_one(waybill, cpf, state_dir)


if __name__ == "__main__":
    main()
