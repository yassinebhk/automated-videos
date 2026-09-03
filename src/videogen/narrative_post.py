"""Publica un hilo narrativo (5 posts encadenados) sobre un caso español
en Bluesky + Threads + Mastodon. Sin video: puro texto, formato thread.

Estrategia: los feeds premian los hilos porque generan más tiempo de lectura
y más interacción que un post + link. Cada plataforma soporta reply-chain:
- Bluesky: models.AppBskyFeedPost.ReplyRef {root, parent}
- Mastodon: in_reply_to_id
- Threads: reply_to_id en el /threads

Rota entre casos usando ledger para no repetir <14 días.
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .config import ROOT

NARRATIVE_LOG = ROOT / "output" / "narrative_post_log.json"
STATS_HISTORY = ROOT / "output" / "stats_history.jsonl"
COOLDOWN_DAYS = 14


def _load_ledger() -> dict[str, str]:
    if not NARRATIVE_LOG.exists():
        return {}
    try:
        return json.loads(NARRATIVE_LOG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(video_id: str) -> None:
    NARRATIVE_LOG.parent.mkdir(parents=True, exist_ok=True)
    data = _load_ledger()
    data[video_id] = datetime.now(timezone.utc).isoformat()
    NARRATIVE_LOG.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                              encoding="utf-8")


def _recently_used(video_id: str) -> bool:
    entry = _load_ledger().get(video_id)
    if not entry:
        return False
    try:
        ts = datetime.fromisoformat(entry)
    except Exception:
        return False
    return (datetime.now(timezone.utc) - ts) < timedelta(days=COOLDOWN_DAYS)


def _pick_video() -> dict | None:
    """Elige un video YT reciente con views, no reutilizado en 14 días."""
    if not STATS_HISTORY.exists():
        return None
    cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).timestamp()
    latest: dict[str, dict] = {}
    for line in STATS_HISTORY.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("platform") != "youtube" or r.get("kind") != "video":
            continue
        vid = r.get("video_id") or ""
        if not vid:
            continue
        ts = int(r.get("ts") or 0)
        if ts < cutoff:
            continue
        prev = latest.get(vid)
        if not prev or ts > int(prev.get("ts") or 0):
            latest[vid] = r
    def _is_true_crime(title: str) -> bool:
        low = (title or "").lower()
        # Filtra por marcadores del pivote true crime (evita videos del canal viejo)
        return ("caso " in low or "· #" in low or " · #" in low
                or "estafa" in low or "fraude" in low or "corrupción" in low)
    fresh = [v for v in latest.values()
             if not _recently_used(v["video_id"])
             and int(v.get("views") or 0) > 30
             and _is_true_crime(v.get("title") or "")]
    if not fresh:
        return None
    # Weighted: views + freshness. Random para variedad.
    return random.choice(fresh[:20])


def _generate_thread(video: dict) -> list[str] | None:
    """Genera 5 posts encadenados vía Gemini. Devuelve lista de strings."""
    title = video.get("title") or ""
    yt_url = f"https://youtu.be/{video.get('video_id')}"
    try:
        from google import genai
        from google.genai import types
        from .config import gemini_key
        key = gemini_key()
        if not key:
            return None
        client = genai.Client(api_key=key)
        prompt = (
            f"Escribe un HILO de exactamente 5 posts sobre este caso español real, para redes sociales.\n\n"
            f"Título del video: {title}\n"
            f"Link YT (solo va en el último post): {yt_url}\n\n"
            f"REGLAS estrictas:\n"
            f"- Post 1: HOOK. Máx 240 chars. Dato brutal, cifra o pregunta que rompa el scroll. Termina con '👇 Hilo:'\n"
            f"- Post 2: contexto (quién, cuándo, dónde). Máx 280 chars.\n"
            f"- Post 3: el mecanismo del fraude/crimen (cómo lo hicieron). Máx 280 chars.\n"
            f"- Post 4: consecuencia + cifra clave. Máx 280 chars.\n"
            f"- Post 5: cierre + reflexión + link YT al final. Máx 240 chars.\n\n"
            f"PROHIBIDO:\n"
            f"- Empezar con '¿Sabías...?', 'Todos hemos...', 'Increíble...', 'Brutal...'\n"
            f"- Usar hashtags dentro del texto\n"
            f"- Emojis excesivos (máx 1 por post)\n"
            f"- Meta-comentarios tipo 'este hilo va sobre...'\n\n"
            f"FORMATO OUTPUT (importante):\n"
            f"Devuelve 5 posts separados EXACTAMENTE por la línea '---' (tres guiones).\n"
            f"Nada más, ni encabezado ni numeración.\n"
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=1.1, max_output_tokens=1200),
        )
        text = (resp.text or "").strip()
        posts = [p.strip() for p in text.split("---") if p.strip()]
        if len(posts) < 4:
            print(f"  narrative: solo {len(posts)} posts generados — insuficiente")
            return None
        # Asegura link YT en el último
        posts = posts[:5]
        if yt_url not in posts[-1]:
            posts[-1] = f"{posts[-1]}\n\n{yt_url}"
        # Trim length
        posts = [p[:295] for p in posts]
        return posts
    except Exception as e:
        print(f"  narrative: Gemini fail {type(e).__name__}: {e}")
        return None


def _post_bluesky_thread(posts: list[str]) -> bool:
    handle = os.environ.get("BLUESKY_HANDLE")
    pwd = os.environ.get("BLUESKY_APP_PASSWORD")
    if not (handle and pwd):
        return False
    try:
        from atproto import Client
        from atproto import models
        c = Client()
        c.login(handle, pwd)
        first = c.send_post(text=posts[0][:300])
        root_ref = {"uri": first.uri, "cid": first.cid}
        parent_ref = root_ref
        for post in posts[1:]:
            reply = models.AppBskyFeedPost.ReplyRef(
                parent=models.ComAtprotoRepoStrongRef.Main(**parent_ref),
                root=models.ComAtprotoRepoStrongRef.Main(**root_ref),
            )
            r = c.send_post(text=post[:300], reply_to=reply)
            parent_ref = {"uri": r.uri, "cid": r.cid}
        return True
    except Exception as e:
        print(f"  narrative bluesky: {type(e).__name__}: {e}")
        return False


def _post_mastodon_thread(posts: list[str]) -> bool:
    import requests as _req
    instance = os.environ.get("MASTODON_INSTANCE", "https://mastodon.social").rstrip("/")
    token = os.environ.get("MASTODON_ACCESS_TOKEN")
    if not token:
        return False
    try:
        prev_id = None
        for post in posts:
            data = {"status": post[:500], "visibility": "public"}
            if prev_id:
                data["in_reply_to_id"] = prev_id
            r = _req.post(f"{instance}/api/v1/statuses",
                          headers={"Authorization": f"Bearer {token}"},
                          data=data, timeout=30)
            if r.status_code >= 300:
                print(f"  narrative mastodon: HTTP {r.status_code} {r.text[:200]}")
                return False
            prev_id = r.json().get("id")
        return True
    except Exception as e:
        print(f"  narrative mastodon: {type(e).__name__}: {e}")
        return False


def _post_threads_thread(posts: list[str]) -> bool:
    import requests as _req
    import time as _t
    tok = os.environ.get("THREADS_TOKEN")
    uid = os.environ.get("THREADS_USER_ID")
    if not (tok and uid):
        return False
    base = "https://graph.threads.net/v1.0"
    try:
        prev_id = None
        for post in posts:
            params = {"media_type": "TEXT", "text": post[:500], "access_token": tok}
            if prev_id:
                params["reply_to_id"] = prev_id
            c = _req.post(f"{base}/{uid}/threads", params=params, timeout=30).json()
            if "id" not in c:
                print(f"  narrative threads: create sin id {c}")
                return False
            _t.sleep(20)
            p = _req.post(f"{base}/{uid}/threads_publish",
                          params={"creation_id": c["id"], "access_token": tok},
                          timeout=30).json()
            if "id" not in p:
                print(f"  narrative threads: publish sin id {p}")
                return False
            prev_id = p["id"]
            _t.sleep(5)
        return True
    except Exception as e:
        print(f"  narrative threads: {type(e).__name__}: {e}")
        return False


def run_once() -> dict[str, Any]:
    video = _pick_video()
    if not video:
        return {"status": "no_candidate"}
    posts = _generate_thread(video)
    if not posts:
        return {"status": "gen_fail", "video_id": video.get("video_id")}
    print(f"  narrative: hilo de {len(posts)} posts sobre {video.get('title','')[:60]}")
    result = {
        "video_id": video.get("video_id"),
        "title": (video.get("title") or "")[:80],
        "posts_count": len(posts),
        "bluesky": _post_bluesky_thread(posts),
        "mastodon": _post_mastodon_thread(posts),
        "threads": _post_threads_thread(posts),
    }
    if any([result["bluesky"], result["mastodon"], result["threads"]]):
        _mark_used(video["video_id"])
    return result
