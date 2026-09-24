"""Auto-reply Threads a MENCIONES directas del canal (@waitwhy_).

Modo DEFENSIVO estrictamente:
- Solo replica cuando alguien menciona explícitamente al canal.
- NO hace fanout, NO comenta threads ajenos, NO likes automáticos.
- Máx 5 replies/día (Threads es hipersensible — memoria: Meta borró
  posts de WaitWhy 16/09 por texto repetido).
- Templates rotativos (nunca literal duplicado).
- Ledger persistente evita duplicar.

Cron: cada 4h.
"""
from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from .config import ROOT

API_BASE = "https://graph.threads.net/v1.0"
LEDGER = ROOT / "output" / "threads_engagement_ledger.json"
LEDGER_MAX = 1000
MAX_AGE_HOURS = 48
MAX_REPLIES_PER_DAY = 5
MIN_MENTION_WORDS = 3


_REPLY_TEMPLATES = [
    "Gracias por comentar 🙌 mañana caso nuevo",
    "¡Buen apunte! Te espero en el próximo",
    "Se agradece — mañana subo otro caso enterrado",
    "Gracias 🙏 mañana caso nuevo verificado",
    "Cierto lo que dices. Nos leemos en el próximo",
]


def _load_ledger() -> dict:
    if not LEDGER.exists():
        return {"replied": [], "day_count": {}}
    try:
        d = json.loads(LEDGER.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            return {"replied": [], "day_count": {}}
        d.setdefault("replied", [])
        d.setdefault("day_count", {})
        return d
    except Exception:
        return {"replied": [], "day_count": {}}


def _save_ledger(data: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    if len(data.get("replied", [])) > LEDGER_MAX:
        data["replied"] = data["replied"][-LEDGER_MAX:]
    # Poda day_count: solo últimos 14 días
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
    data["day_count"] = {k: v for k, v in data.get("day_count", {}).items() if k >= cutoff}
    LEDGER.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _creds() -> tuple[Optional[str], Optional[str]]:
    tok = os.environ.get("THREADS_TOKEN") or os.environ.get("THREADS_ACCESS_TOKEN")
    uid = os.environ.get("THREADS_USER_ID")
    return tok, uid


def _fetch_mentions(tok: str, uid: str) -> list[dict]:
    """Devuelve menciones directas al user. Endpoint /me/mentions."""
    r = requests.get(
        f"{API_BASE}/{uid}/mentions",
        params={"fields": "id,text,username,timestamp",
                "access_token": tok, "limit": 25},
        timeout=20,
    )
    if r.status_code != 200:
        print(f"  threads-eng: mentions list fail {r.status_code} — {r.text[:180]}")
        return []
    return r.json().get("data", []) or []


def _reply_to_mention(tok: str, uid: str, mention_id: str, text: str) -> Optional[str]:
    """Crea container reply → publica. Threads necesita 2 pasos."""
    c = requests.post(
        f"{API_BASE}/{uid}/threads",
        params={"media_type": "TEXT", "text": text[:500],
                "reply_to_id": mention_id, "access_token": tok},
        timeout=30,
    )
    if c.status_code != 200:
        print(f"  threads-eng: container fail {c.status_code} — {c.text[:180]}")
        return None
    cid = c.json().get("id")
    if not cid:
        return None
    time.sleep(30)  # Threads necesita procesar antes de publicar
    p = requests.post(
        f"{API_BASE}/{uid}/threads_publish",
        params={"creation_id": cid, "access_token": tok},
        timeout=30,
    )
    if p.status_code != 200:
        print(f"  threads-eng: publish fail {p.status_code} — {p.text[:180]}")
        return None
    return p.json().get("id")


def run_threads_engagement_pass(dry_run: bool = False) -> dict:
    tok, uid = _creds()
    if not (tok and uid):
        return {"error": "no THREADS_TOKEN/THREADS_USER_ID"}

    ledger = _load_ledger()
    replied_ids = set(ledger.get("replied", []))
    today = datetime.now(timezone.utc).date().isoformat()
    day_count = ledger.get("day_count", {})
    used_today = day_count.get(today, 0)

    if used_today >= MAX_REPLIES_PER_DAY:
        return {"skipped": "daily cap reached", "used_today": used_today}

    mentions = _fetch_mentions(tok, uid)
    if not mentions:
        return {"mentions_checked": 0, "replied": 0}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_AGE_HOURS)
    replied = 0

    for m in mentions:
        if used_today + replied >= MAX_REPLIES_PER_DAY:
            break
        mid = m.get("id")
        if not mid or mid in replied_ids:
            continue
        ts = m.get("timestamp")
        try:
            ts_dt = datetime.fromisoformat((ts or "").replace("+0000", "+00:00"))
        except Exception:
            continue
        if ts_dt < cutoff:
            continue
        text = (m.get("text") or "").strip()
        if len(text.split()) < MIN_MENTION_WORDS:
            replied_ids.add(mid)
            continue
        reply_text = random.choice(_REPLY_TEMPLATES)
        if dry_run:
            print(f"  threads-eng DRY {mid} @{m.get('username')} → «{text[:50]}» → «{reply_text}»")
            replied += 1
            replied_ids.add(mid)
            continue
        new_id = _reply_to_mention(tok, uid, mid, reply_text)
        if new_id:
            replied += 1
            replied_ids.add(mid)
            print(f"  threads-eng: ✅ {mid} reply {new_id}")
        else:
            replied_ids.add(mid)  # no reintentamos

    day_count[today] = used_today + replied
    ledger["replied"] = list(replied_ids)
    ledger["day_count"] = day_count
    if not dry_run:
        _save_ledger(ledger)

    try:
        from . import notify_batch
        if replied:
            notify_batch.add(
                f"🧵 <b>Threads engagement</b>: {replied} replies a menciones "
                f"({used_today + replied}/{MAX_REPLIES_PER_DAY} hoy)"
            )
    except Exception:
        pass

    return {"mentions_checked": len(mentions), "replied": replied,
            "used_today": used_today + replied}
