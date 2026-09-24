"""Auto-reply a comentarios de las últimas 24-48h.

Por qué:
- Cada reply del creador dispara notify al viewer → CTR de vuelta al canal.
- YT algoritmo boostea videos con alta ratio comment-reply del creador.
- Palanca directa para YPP 500 subs: viewer que recibe reply personal
  vuelve → suscribe con probabilidad 3-5× más alta.

Anti-spam (crítico — YT puede baneen la cuenta por spam):
- Solo videos publicados hace 6h-72h (ni recién ni muy antiguos).
- Max 3 replies/video, max 15 replies/pase.
- Solo comentarios de >=2 palabras y NO del canal.
- Ledger persistente evita responder 2× al mismo comment.
- Reply templates variados + rotativos (nunca literal duplicado).
- 1 de cada 3 replies mete CTA sub sutil.

Requiere scope `youtube.force-ssl` (ya activo). Cron: cada 4h.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests

from .config import ROOT, SECRETS_DIR


LEDGER = ROOT / "output" / "engagement_ledger.json"
LEDGER_MAX = 2000  # entradas históricas
MIN_AGE_HOURS = 6
MAX_AGE_HOURS = 72
MAX_REPLIES_PER_VIDEO = 3
MAX_REPLIES_PER_PASS = 15
MIN_COMMENT_WORDS = 2


_REPLY_TEMPLATES = [
    "Justo eso. Lo peor: sigue impune.",
    "Buen ojo — casi nadie lo recuerda ya.",
    "Exacto, y encima nadie está en la cárcel.",
    "Comentario top — ¿qué otro caso conoces?",
    "Sí, es de los que enterraron con éxito.",
    "Tal cual. La sentencia quedó en nada.",
    "Bien visto. Lo enterraron rápido.",
    "Cierto, ni juicio decente hubo.",
    "Buen apunte. En el vídeo lo verificamos.",
    "Y lo peor es que se puede repetir.",
]

_REPLY_WITH_CTA = [
    "Justo eso. Suscríbete — mañana otro caso enterrado.",
    "Buen ojo. Sub y no te pierdes el siguiente 🔔",
    "Exacto — sub, mañana caso nuevo verificado.",
    "Tal cual. Sub si te enganchan estas historias.",
]


def _load_ledger() -> dict:
    if not LEDGER.exists():
        return {"replied": []}
    try:
        d = json.loads(LEDGER.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            return {"replied": []}
        return d
    except Exception:
        return {"replied": []}


def _save_ledger(data: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    if len(data.get("replied", [])) > LEDGER_MAX:
        data["replied"] = data["replied"][-LEDGER_MAX:]
    LEDGER.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _access_token() -> Optional[str]:
    tok_path = SECRETS_DIR / "youtube_token.json"
    if not tok_path.exists():
        return None
    tok = json.loads(tok_path.read_text())
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": tok["client_id"], "client_secret": tok["client_secret"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token",
    }, timeout=15).json()
    return r.get("access_token")


def _channel_id(access_token: str) -> Optional[str]:
    H = {"Authorization": f"Bearer {access_token}"}
    r = requests.get("https://www.googleapis.com/youtube/v3/channels",
                     params={"part": "id", "mine": "true"},
                     headers=H, timeout=15).json()
    items = r.get("items", [])
    return items[0]["id"] if items else None


def _recent_video_ids(access_token: str, min_hours: int, max_hours: int) -> list[str]:
    """Devuelve videos publicados en la ventana [min_hours, max_hours] atrás."""
    H = {"Authorization": f"Bearer {access_token}"}
    ch = requests.get("https://www.googleapis.com/youtube/v3/channels",
                      params={"part": "contentDetails", "mine": "true"},
                      headers=H, timeout=15).json()
    items = ch.get("items", [])
    if not items:
        return []
    upl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = requests.get("https://www.googleapis.com/youtube/v3/playlistItems",
                      params={"part": "contentDetails", "playlistId": upl,
                              "maxResults": 30},
                      headers=H, timeout=15).json()
    now = datetime.now(timezone.utc)
    out = []
    for it in pl.get("items", []):
        cd = it.get("contentDetails", {}) or {}
        vid = cd.get("videoId")
        pub = cd.get("videoPublishedAt")
        if not (vid and pub):
            continue
        try:
            pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except Exception:
            continue
        age = now - pub_dt
        if timedelta(hours=min_hours) <= age <= timedelta(hours=max_hours):
            out.append(vid)
    return out


def _list_video_comments(access_token: str, video_id: str, max_results: int = 30) -> list[dict]:
    """Devuelve top-level comments recientes del video."""
    H = {"Authorization": f"Bearer {access_token}"}
    r = requests.get("https://www.googleapis.com/youtube/v3/commentThreads",
                     params={"part": "snippet,replies", "videoId": video_id,
                             "order": "time", "maxResults": max_results,
                             "textFormat": "plainText"},
                     headers=H, timeout=15)
    if r.status_code != 200:
        return []
    return r.json().get("items", [])


def _has_channel_reply(thread: dict, channel_id: str) -> bool:
    replies = (thread.get("replies") or {}).get("comments", []) or []
    for rep in replies:
        snip = rep.get("snippet", {}) or {}
        if snip.get("authorChannelId", {}).get("value") == channel_id:
            return True
    return False


def _post_reply(access_token: str, parent_id: str, text: str) -> Optional[str]:
    H = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    body = {"snippet": {"parentId": parent_id, "textOriginal": text}}
    r = requests.post("https://www.googleapis.com/youtube/v3/comments",
                      params={"part": "snippet"}, headers=H, json=body, timeout=20)
    if r.status_code == 200:
        return r.json().get("id")
    print(f"  engagement: reply fail {r.status_code} — {r.text[:180]}")
    return None


def _pick_reply(idx: int) -> str:
    if idx % 3 == 2:
        return random.choice(_REPLY_WITH_CTA)
    return random.choice(_REPLY_TEMPLATES)


def run_engagement_pass(max_total: int = MAX_REPLIES_PER_PASS,
                        dry_run: bool = False) -> dict:
    """Ejecuta un pase de auto-reply. Devuelve dict con contadores."""
    tok = _access_token()
    if not tok:
        return {"error": "no token"}
    ch_id = _channel_id(tok)
    if not ch_id:
        return {"error": "no channel_id"}

    ledger = _load_ledger()
    already = set(ledger.get("replied", []))

    video_ids = _recent_video_ids(tok, MIN_AGE_HOURS, MAX_AGE_HOURS)
    if not video_ids:
        return {"videos_checked": 0, "replied": 0, "skipped": 0}

    replied_total = 0
    skipped_total = 0
    per_video_counts: dict[str, int] = {}

    for vid in video_ids:
        if replied_total >= max_total:
            break
        threads = _list_video_comments(tok, vid, max_results=30)
        for thread in threads:
            if replied_total >= max_total:
                break
            if per_video_counts.get(vid, 0) >= MAX_REPLIES_PER_VIDEO:
                break
            thread_id = thread.get("id")
            if not thread_id or thread_id in already:
                continue
            top = thread.get("snippet", {}).get("topLevelComment", {})
            snip = top.get("snippet", {})
            author_ch = (snip.get("authorChannelId") or {}).get("value")
            if author_ch == ch_id:
                already.add(thread_id)
                continue
            text = (snip.get("textDisplay") or "").strip()
            if len(text.split()) < MIN_COMMENT_WORDS:
                already.add(thread_id)
                continue
            if _has_channel_reply(thread, ch_id):
                already.add(thread_id)
                continue
            reply_text = _pick_reply(replied_total)
            if dry_run:
                print(f"  engagement DRY {vid} → «{text[:50]}» → reply «{reply_text}»")
                replied_total += 1
                per_video_counts[vid] = per_video_counts.get(vid, 0) + 1
                already.add(thread_id)
                continue
            rid = _post_reply(tok, thread_id, reply_text)
            if rid:
                replied_total += 1
                per_video_counts[vid] = per_video_counts.get(vid, 0) + 1
                already.add(thread_id)
                print(f"  engagement: ✅ {vid} reply {rid} → «{reply_text}»")
            else:
                skipped_total += 1
                already.add(thread_id)  # no reintentamos aunque falle

    ledger["replied"] = list(already)
    if not dry_run:
        _save_ledger(ledger)

    result = {"videos_checked": len(video_ids), "replied": replied_total,
              "skipped": skipped_total,
              "per_video": per_video_counts}
    try:
        from . import notify_batch
        if replied_total:
            notify_batch.add(
                f"💬 <b>Engagement pass</b>: {replied_total} replies en "
                f"{len(per_video_counts)} videos (últimas 6-72h)"
            )
    except Exception:
        pass
    return result
