"""Reply-boost Bluesky a threads trending ES sobre corrupción/true crime.

⚠️ Contraviene la política previa del growth loop ("NO comentarios automáticos
— spammy"). Se hace con SALVAGUARDAS DURAS para no dar la sensación de bot:

- MAX 3 replies/día (Bluesky sensible a spam volumen)
- Solo posts en ES con hashtags true crime/corrupción
- Solo posts con >=8 likes (no random posts sin tracción)
- Solo cuentas con <5000 followers (evita spamear a periodistas famosos)
- Solo posts publicados últimas 24h
- Templates aportan DATO CITABLE + fuente pública. NUNCA solo link al canal.
- Ledger persistente evita reply 2× al mismo thread
- Dry-run por defecto (habilitar posting real con --live)

Palanca growth: reply útil en un post viral con 50+ likes → notif a los 50
viewers de ese thread → algo de curiosidad → visitan perfil → ven canal.
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from .config import ROOT

LEDGER = ROOT / "output" / "bsky_reply_boost_ledger.json"
LEDGER_MAX = 500
MAX_REPLIES_PER_DAY = 3
MIN_POST_LIKES = 8
MAX_AUTHOR_FOLLOWERS = 5000
MAX_POST_AGE_HOURS = 24

# Solo hashtags/keywords muy nuestros. Evitamos genéricos ("españa", "política")
# donde entrarían threads no relacionados.
TARGET_TAGS = [
    "estafas", "corrupción", "corrupcion",
    "gürtel", "gurtel", "bárcenas", "barcenas", "malaya", "koldo",
    "trueCrime", "trueCrimeEspaña",
]

# Templates que aportan valor (dato + fuente) NO promoción cruda.
# La mención al canal viene al final entre paréntesis, opcional según ratio.
_VALUE_REPLIES = [
    "Sumo un dato: el caso KIO movió 300M€ · fuente sentencia AN 3/2000.",
    "Complemento: en el caso Malaya la trama llegó a 2.400M€ · sent. TS 508/2021.",
    "Related: caso Erial (Zaplana) — 20,6M€ ocultos · sent. AN oct 2024.",
    "Contexto: el caso Bárcenas cifró 47M€ en Suiza · sent. TS 507/2020.",
    "Dato: caso Gürtel — 41 años de cárcel para Correa · sent. AN 20/2018.",
]

# Solo 1 de cada 3 replies incluye mención al canal (evita spam-look).
_CANAL_TAG = " (Toco casos así en @waitwhy_)"


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
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
    data["day_count"] = {k: v for k, v in data.get("day_count", {}).items() if k >= cutoff}
    LEDGER.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _client():
    from atproto import Client
    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not (handle and password):
        return None
    c = Client()
    c.login(handle, password)
    return c


def _pick_reply(idx: int) -> str:
    txt = random.choice(_VALUE_REPLIES)
    if idx % 3 == 0:
        txt = txt + _CANAL_TAG
    return txt[:300]  # límite Bluesky


def run_bsky_reply_boost(dry_run: bool = True) -> dict:
    """Ejecuta un pase de reply-boost. Dry-run por defecto (safe)."""
    try:
        c = _client()
    except Exception as e:
        return {"error": f"auth fail: {e}"}
    if not c:
        return {"error": "no BLUESKY_HANDLE/BLUESKY_APP_PASSWORD"}

    ledger = _load_ledger()
    replied_ids = set(ledger.get("replied", []))
    today = datetime.now(timezone.utc).date().isoformat()
    day_count = ledger.get("day_count", {})
    used_today = day_count.get(today, 0)

    if used_today >= MAX_REPLIES_PER_DAY:
        return {"skipped": "daily cap reached", "used_today": used_today}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_POST_AGE_HOURS)
    replied = 0
    checked = 0

    random.shuffle(TARGET_TAGS)
    for tag in TARGET_TAGS:
        if used_today + replied >= MAX_REPLIES_PER_DAY:
            break
        try:
            res = c.app.bsky.feed.search_posts({"q": f"#{tag}", "limit": 15,
                                                 "sort": "top", "lang": "es"})
        except Exception as e:
            print(f"  bsky-boost: search #{tag} fail {e}")
            continue
        posts = res.posts or []
        for post in posts:
            if used_today + replied >= MAX_REPLIES_PER_DAY:
                break
            checked += 1
            if post.uri in replied_ids:
                continue
            likes = getattr(post, "like_count", 0) or 0
            if likes < MIN_POST_LIKES:
                continue
            # Age check
            try:
                created = getattr(post.record, "created_at", None) or ""
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if created_dt < cutoff:
                    continue
            except Exception:
                continue
            # Author check
            author = getattr(post, "author", None)
            author_followers = getattr(author, "followers_count", None) or 0
            if author_followers > MAX_AUTHOR_FOLLOWERS:
                continue
            author_handle = getattr(author, "handle", "?")
            reply_text = _pick_reply(replied)
            if dry_run:
                print(f"  bsky-boost DRY #{tag} · @{author_handle} · {likes}L · {author_followers}foll")
                print(f"    → «{reply_text}»")
                replied += 1
                replied_ids.add(post.uri)
                continue
            try:
                from atproto import models
                reply_ref = models.AppBskyFeedPost.ReplyRef(
                    parent=models.ComAtprotoRepoStrongRef.Main(uri=post.uri, cid=post.cid),
                    root=models.ComAtprotoRepoStrongRef.Main(uri=post.uri, cid=post.cid),
                )
                c.send_post(reply_text, reply_to=reply_ref)
                replied += 1
                replied_ids.add(post.uri)
                print(f"  bsky-boost ✅ @{author_handle} #{tag} ({likes}L)")
            except Exception as e:
                print(f"  bsky-boost fail @{author_handle}: {e}")
                replied_ids.add(post.uri)

    day_count[today] = used_today + replied
    ledger["replied"] = list(replied_ids)
    ledger["day_count"] = day_count
    if not dry_run:
        _save_ledger(ledger)

    try:
        from . import notify_batch
        if replied and not dry_run:
            notify_batch.add(
                f"🦋 <b>Bluesky reply-boost</b>: {replied} replies "
                f"({used_today + replied}/{MAX_REPLIES_PER_DAY} hoy)"
            )
    except Exception:
        pass

    return {"checked": checked, "replied": replied,
            "used_today": used_today + replied, "dry_run": dry_run}
