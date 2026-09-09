"""Community-driven: encuesta semanal Bluesky/Threads/Mastodon con 4 casos
candidatos. El usuario elige. El más votado se convierte en Short al día
siguiente y se anuncia como "vosotros lo pedisteis".

Flow:
- DOMINGO 18 UTC: publica encuesta con 4 casos preseleccionados por Gemini.
- LUNES 11 UTC: lee resultados (likes en cada opción por hilo), elige ganador,
  guarda en output/community_pick.json para que autogen del día lo use.
- Autogen normal: si community_pick.json existe y es <36h, usa ese topic
  con marca [COMMUNITY_PICK], luego lo consume.

Objetivo: convertir 125 followers Bluesky en comunidad que ESPERA contenido,
suma engagement, y convierte follows → subs YT.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .config import ROOT

POLL_LEDGER = ROOT / "output" / "community_poll_log.json"
COMMUNITY_PICK = ROOT / "output" / "community_pick.json"
POLL_STATE = ROOT / "output" / "community_poll_state.json"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _pick_candidates_from_pool(n: int = 4) -> list[dict]:
    """Elige 4 candidatos del case_ledger no usados en 180 días."""
    from . import case_ledger
    try:
        avail = case_ledger.available_cases_for_prompt(days=180, sample_size=n * 4)
    except Exception as e:
        print(f"  community: pool fail {e}")
        return []
    import random
    random.shuffle(avail)
    picks = []
    for c in avail[:n]:
        picks.append({
            "key": c.get("key") or c.get("name") or "",
            "title": c.get("name") or c.get("title") or "",
            "hook": c.get("hook") or c.get("summary") or "",
        })
    return picks


def _generate_poll_text(candidates: list[dict]) -> str:
    """Compone el post de encuesta con 4 emojis-numerados como reacciones."""
    lines = [
        "🗳️ ENCUESTA SEMANAL — vosotros elegís el caso de esta semana:",
        "",
    ]
    icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    for i, c in enumerate(candidates[:4]):
        title = c["title"][:60]
        hook = (c["hook"] or "")[:80]
        if hook:
            lines.append(f"{icons[i]} {title} — {hook}")
        else:
            lines.append(f"{icons[i]} {title}")
    lines.extend([
        "",
        "👇 Da LIKE al comment con el número de tu caso favorito.",
        "El más votado sale mañana en el canal WaitWhy 🎬",
    ])
    return "\n".join(lines)


def _post_poll_bluesky(text: str, candidates: list[dict]) -> tuple[str, str] | None:
    """Publica encuesta Bluesky + reply con 4 comentarios (uno por opción,
    para que el usuario haga like al que prefiera). Devuelve (root_uri, root_cid).
    """
    from atproto import Client
    from atproto import models as bmodels
    handle = os.environ.get("BLUESKY_HANDLE")
    pwd = os.environ.get("BLUESKY_APP_PASSWORD")
    if not (handle and pwd):
        return None
    try:
        c = Client()
        c.login(handle, pwd)
        root = c.send_post(text=text[:300])
        root_ref = {"uri": root.uri, "cid": root.cid}
        # Publica 4 replies (uno por opción) para que el usuario like el suyo
        icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        option_refs = []
        for i, cand in enumerate(candidates[:4]):
            reply_text = f"{icons[i]} {cand['title'][:180]}"
            reply = bmodels.AppBskyFeedPost.ReplyRef(
                parent=bmodels.ComAtprotoRepoStrongRef.Main(**root_ref),
                root=bmodels.ComAtprotoRepoStrongRef.Main(**root_ref),
            )
            r = c.send_post(text=reply_text[:300], reply_to=reply)
            option_refs.append({"index": i, "uri": r.uri, "cid": r.cid,
                                 "title": cand["title"], "key": cand["key"]})
        return root.uri, root.cid, option_refs
    except Exception as e:
        print(f"  community bluesky: {type(e).__name__}: {e}")
        return None


def _post_poll_mastodon(text: str) -> str | None:
    """Mastodon soporta polls nativas — más limpio que reply-chain."""
    import requests as _req
    instance = os.environ.get("MASTODON_INSTANCE", "https://mastodon.social").rstrip("/")
    token = os.environ.get("MASTODON_ACCESS_TOKEN")
    if not token:
        return None
    return None  # Placeholder — Mastodon poll requires diferente flow


def create_poll() -> dict:
    """DOMINGO — publica encuesta con 4 candidatos."""
    candidates = _pick_candidates_from_pool(4)
    if len(candidates) < 4:
        return {"status": "not_enough_candidates", "count": len(candidates)}
    text = _generate_poll_text(candidates)
    print(f"  community: encuesta con {len(candidates)} opciones")
    bs = _post_poll_bluesky(text, candidates)
    if not bs:
        return {"status": "post_fail"}
    root_uri, root_cid, option_refs = bs
    state = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root_uri": root_uri,
        "root_cid": root_cid,
        "options": option_refs,
        "resolved": False,
    }
    _save_json(POLL_STATE, state)
    _notify(f"🗳️ <b>Encuesta community publicada</b>\n"
            f"{len(candidates)} opciones · esperando likes hasta mañana 11 UTC")
    return {"status": "posted", "options": len(candidates)}


def _read_bluesky_reply_likes(uri: str) -> int:
    """Lee el like_count de un post Bluesky (getPostThread)."""
    from atproto import Client
    handle = os.environ.get("BLUESKY_HANDLE")
    pwd = os.environ.get("BLUESKY_APP_PASSWORD")
    if not (handle and pwd):
        return 0
    try:
        c = Client()
        c.login(handle, pwd)
        thread = c.get_post_thread(uri=uri, depth=0)
        post = thread.thread.post
        return int(post.like_count or 0)
    except Exception as e:
        print(f"  community read likes: {type(e).__name__}: {e}")
        return 0


def resolve_poll() -> dict:
    """LUNES — lee likes de las 4 replies, elige ganador, escribe community_pick.json."""
    state = _load_json(POLL_STATE, None)
    if not state or state.get("resolved"):
        return {"status": "no_active_poll"}
    options = state.get("options", [])
    if not options:
        return {"status": "no_options"}
    # Lee likes de cada reply
    results = []
    for opt in options:
        likes = _read_bluesky_reply_likes(opt["uri"])
        results.append({**opt, "likes": likes})
    # Ordena por likes desc
    results.sort(key=lambda r: -r["likes"])
    winner = results[0]
    # Guarda pick para que autogen lo use
    pick = {
        "title": winner["title"],
        "key": winner.get("key", ""),
        "topic": f"[COMMUNITY_PICK] {winner['title']} — el caso que vosotros elegisteis esta semana",
        "chosen_at": datetime.now(timezone.utc).isoformat(),
        "consumed": False,
        "votes": {r["title"]: r["likes"] for r in results},
    }
    _save_json(COMMUNITY_PICK, pick)
    # Marca resolved
    state["resolved"] = True
    state["winner"] = winner["title"]
    state["final_votes"] = pick["votes"]
    _save_json(POLL_STATE, state)
    # Notif
    lines = [
        f"🏆 <b>Ganador encuesta community</b>",
        f"→ <i>{winner['title'][:80]}</i> ({winner['likes']} likes)",
        "",
        "Votos:",
    ]
    for r in results:
        lines.append(f"  • {r['title'][:50]}: {r['likes']}")
    _notify("\n".join(lines))
    # Post reply anunciando ganador
    _post_winner_announcement(state["root_uri"], state["root_cid"], winner)
    return {"status": "resolved", "winner": winner["title"], "likes": winner["likes"]}


def _post_winner_announcement(root_uri: str, root_cid: str, winner: dict) -> None:
    from atproto import Client
    from atproto import models as bmodels
    handle = os.environ.get("BLUESKY_HANDLE")
    pwd = os.environ.get("BLUESKY_APP_PASSWORD")
    if not (handle and pwd):
        return
    try:
        c = Client()
        c.login(handle, pwd)
        text = (f"🏆 GANADOR: {winner['title'][:180]}\n\n"
                f"Vídeo hoy mismo en el canal WaitWhy 🎬")
        reply = bmodels.AppBskyFeedPost.ReplyRef(
            parent=bmodels.ComAtprotoRepoStrongRef.Main(uri=root_uri, cid=root_cid),
            root=bmodels.ComAtprotoRepoStrongRef.Main(uri=root_uri, cid=root_cid),
        )
        c.send_post(text=text[:300], reply_to=reply)
    except Exception as e:
        print(f"  community announce: {type(e).__name__}: {e}")


def consume_pick_if_available() -> str | None:
    """Llamado por autogen: si hay community_pick pendiente <36h, devuelve topic
    y lo marca consumido. Si no, None (autogen sigue flujo normal)."""
    pick = _load_json(COMMUNITY_PICK, None)
    if not pick or pick.get("consumed"):
        return None
    try:
        chosen = datetime.fromisoformat(pick["chosen_at"])
    except Exception:
        return None
    if (datetime.now(timezone.utc) - chosen) > timedelta(hours=36):
        return None
    pick["consumed"] = True
    pick["consumed_at"] = datetime.now(timezone.utc).isoformat()
    _save_json(COMMUNITY_PICK, pick)
    print(f"  community: consumiendo pick '{pick['title']}'")
    return pick["topic"]


def _notify(text: str) -> None:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data=json.dumps({"chat_id": int(chat), "text": text,
                              "parse_mode": "HTML"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass
