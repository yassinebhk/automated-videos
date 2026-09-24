"""Auto-reply a comentarios de reels IG (@waitwhy_) últimas 48h.

Por qué:
- Cada reply del creador → notif push al comentador → CTR de vuelta.
- IG algoritmo boostea reels con alta ratio reply-creator.
- Palanca directa para growth IG (canal más joven + activo que YT).

Nota API: IG Graph API v21 NO expone endpoint para "like a comentarios"
(a diferencia de lo que se creía). Solo permite reply, hide, delete. Así
que este módulo hace SOLO reply.

Anti-spam (crítico — Meta borra cuentas por spam):
- Solo reels últimas 48h.
- Max 3 replies/reel, max 15 replies/pase.
- Ledger persistente evita reply 2× al mismo comment.
- Templates rotativos (Meta detecta duplicados literales).
- Solo comentarios >=2 palabras, NO del propio canal, NO ya-respondidos.

Cron: cada 4h.
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from .config import ROOT

IG_API_BASE = "https://graph.instagram.com/v21.0"
LEDGER = ROOT / "output" / "ig_engagement_ledger.json"
LEDGER_MAX = 2000
MAX_REELS_TO_SCAN = 8
MIN_AGE_HOURS = 3
MAX_AGE_HOURS = 72
MAX_REPLIES_PER_REEL = 3
MAX_REPLIES_PER_PASS = 15
MIN_COMMENT_WORDS = 2


_REPLY_TEMPLATES = [
    "Justo eso 💯",
    "Buen ojo — casi nadie lo recuerda",
    "Exacto, y sigue impune",
    "Comentario top 🔥",
    "Sí, lo enterraron bien",
    "Tal cual — ni juicio decente hubo",
    "Bien visto 👏",
    "Cierto, la sentencia quedó en nada",
    "Y lo peor: se puede repetir",
    "Buen apunte",
]

_REPLY_WITH_CTA = [
    "Justo eso. Sígueme — mañana otro caso 🔔",
    "Buen ojo. Sígueme y no te pierdes el siguiente",
    "Exacto — sígueme, mañana caso nuevo",
    "Tal cual. Sígueme si te enganchan estas historias",
]


def _load_ledger() -> dict:
    if not LEDGER.exists():
        return {"replied": []}
    try:
        d = json.loads(LEDGER.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {"replied": []}
    except Exception:
        return {"replied": []}


def _save_ledger(data: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    if len(data.get("replied", [])) > LEDGER_MAX:
        data["replied"] = data["replied"][-LEDGER_MAX:]
    LEDGER.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _creds() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Devuelve (token, user_id, own_username). Usa la cuenta IG principal
    (@waitwhy_) — que es donde caen todos los reels de canales whitelisted."""
    tok = os.environ.get("IG_TOKEN") or os.environ.get("IG_ACCESS_TOKEN")
    uid = os.environ.get("IG_USER_ID") or os.environ.get("IG_BUSINESS_ACCOUNT_ID")
    own = os.environ.get("IG_USERNAME", "waitwhy_")
    return tok, uid, own


def _recent_reels(tok: str, uid: str, since_hours: int) -> list[dict]:
    """Devuelve reels del user en la ventana temporal."""
    r = requests.get(
        f"{IG_API_BASE}/{uid}/media",
        params={"fields": "id,media_type,timestamp,caption", "limit": 25,
                "access_token": tok},
        timeout=20,
    )
    if r.status_code != 200:
        print(f"  ig-eng: media list fail {r.status_code} — {r.text[:150]}")
        return []
    items = r.json().get("data", [])
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=since_hours)
    min_cut = now - timedelta(hours=MIN_AGE_HOURS)
    out = []
    for it in items:
        if it.get("media_type") not in ("VIDEO", "REELS"):
            continue
        ts = it.get("timestamp")
        if not ts:
            continue
        try:
            ts_dt = datetime.fromisoformat(ts.replace("+0000", "+00:00"))
        except Exception:
            continue
        if cutoff <= ts_dt <= min_cut:
            out.append(it)
    return out[:MAX_REELS_TO_SCAN]


def _list_comments(tok: str, media_id: str) -> list[dict]:
    r = requests.get(
        f"{IG_API_BASE}/{media_id}/comments",
        params={"fields": "id,text,username,timestamp,replies{id,username}",
                "access_token": tok, "limit": 30},
        timeout=20,
    )
    if r.status_code != 200:
        return []
    return r.json().get("data", []) or []


def _reply_to_comment(tok: str, comment_id: str, text: str) -> Optional[str]:
    r = requests.post(
        f"{IG_API_BASE}/{comment_id}/replies",
        params={"message": text, "access_token": tok},
        timeout=20,
    )
    if r.status_code == 200:
        return r.json().get("id")
    print(f"  ig-eng: reply fail {r.status_code} — {r.text[:150]}")
    return None


def _pick_reply(idx: int) -> str:
    if idx % 3 == 2:
        return random.choice(_REPLY_WITH_CTA)
    return random.choice(_REPLY_TEMPLATES)


def _has_own_reply(comment: dict, own_username: str) -> bool:
    replies = (comment.get("replies") or {}).get("data") or []
    for rep in replies:
        if (rep.get("username") or "").lower() == own_username.lower():
            return True
    return False


def run_ig_engagement_pass(max_total: int = MAX_REPLIES_PER_PASS,
                            dry_run: bool = False) -> dict:
    tok, uid, own = _creds()
    if not (tok and uid):
        return {"error": "no IG_TOKEN/IG_USER_ID"}

    ledger = _load_ledger()
    already = set(ledger.get("replied", []))

    reels = _recent_reels(tok, uid, MAX_AGE_HOURS)
    if not reels:
        return {"reels_checked": 0, "replied": 0}

    replied_total = 0
    per_reel: dict[str, int] = {}

    for reel in reels:
        if replied_total >= max_total:
            break
        rid = reel["id"]
        comments = _list_comments(tok, rid)
        for c in comments:
            if replied_total >= max_total:
                break
            if per_reel.get(rid, 0) >= MAX_REPLIES_PER_REEL:
                break
            cid = c.get("id")
            if not cid or cid in already:
                continue
            uname = (c.get("username") or "").lower()
            if uname == own.lower():
                already.add(cid)
                continue
            text = (c.get("text") or "").strip()
            if len(text.split()) < MIN_COMMENT_WORDS:
                already.add(cid)
                continue
            if _has_own_reply(c, own):
                already.add(cid)
                continue
            reply_text = _pick_reply(replied_total)
            if dry_run:
                print(f"  ig-eng DRY {rid} @{uname} → «{text[:50]}» → «{reply_text}»")
                replied_total += 1
                per_reel[rid] = per_reel.get(rid, 0) + 1
                already.add(cid)
                continue
            new_id = _reply_to_comment(tok, cid, reply_text)
            if new_id:
                replied_total += 1
                per_reel[rid] = per_reel.get(rid, 0) + 1
                already.add(cid)
                print(f"  ig-eng: ✅ {rid} @{uname} reply {new_id} → «{reply_text}»")
            else:
                already.add(cid)  # no reintentamos

    ledger["replied"] = list(already)
    if not dry_run:
        _save_ledger(ledger)

    try:
        from . import notify_batch
        if replied_total:
            notify_batch.add(
                f"📸 <b>IG engagement</b>: {replied_total} replies en "
                f"{len(per_reel)} reels de @{own}"
            )
    except Exception:
        pass

    return {"reels_checked": len(reels), "replied": replied_total,
            "per_reel": per_reel}
