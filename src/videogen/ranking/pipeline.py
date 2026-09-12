"""Pipeline canal TopRanking ES — bar chart races."""
from __future__ import annotations

import json
import os
import random
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from ..config import ROOT
from . import generator, topic_pool

RANKING_LEDGER = ROOT / "output" / "ranking_ledger.json"
COOLDOWN_DAYS = 90


def _load_ledger() -> dict[str, str]:
    if not RANKING_LEDGER.exists():
        return {}
    try:
        return json.loads(RANKING_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(key: str) -> None:
    RANKING_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    d = _load_ledger()
    d[key] = datetime.now(timezone.utc).isoformat()
    RANKING_LEDGER.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def _recently_used(key: str) -> bool:
    entry = _load_ledger().get(key)
    if not entry:
        return False
    try:
        ts = datetime.fromisoformat(entry)
    except Exception:
        return False
    return (datetime.now(timezone.utc) - ts) < timedelta(days=COOLDOWN_DAYS)


def _pick_topic() -> dict | None:
    all_t = topic_pool.all_topics()
    fresh = [t for t in all_t if not _recently_used(t["key"])]
    if not fresh:
        fresh = all_t
    return random.choice(fresh)


def _upload_ranking(meta: dict) -> dict | None:
    """Sube al canal TopRanking ES usando YT_RANKING_* creds."""
    from ..upload_youtube import upload_video, set_thumbnail
    prev_prefix = os.environ.get("YT_CHANNEL_PREFIX", "")
    os.environ["YT_CHANNEL_PREFIX"] = "YT_RANKING"
    try:
        vid = upload_video(
            Path(meta["video_path"]),
            title=meta["title"][:100],
            description=meta["description"][:4900],
            tags=meta.get("tags", []),
            category_id="27",  # Education
            is_short=True,
            privacy="public",
        )
        return {"video_id": vid, "url": f"https://youtube.com/shorts/{vid}"}
    except Exception as e:
        print(f"  ranking upload fail: {type(e).__name__}: {e}")
        return None
    finally:
        if prev_prefix:
            os.environ["YT_CHANNEL_PREFIX"] = prev_prefix
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)


def _notify(text: str, urgent: bool = False) -> None:
    """Encola notificación (batched al final del proceso).
    urgent=True → envía inmediatamente (fallos críticos)."""
    from ..notify_batch import add
    add(text, urgent=urgent)


def run_once() -> dict[str, Any]:
    """Genera + sube 1 ranking al canal TopRanking ES."""
    topic = _pick_topic()
    if not topic:
        return {"status": "no_topic"}

    print(f"  ranking: topic={topic['key']}")
    meta = generator.generate_ranking_video(
        topic, generator.RANKING_ROOT,
        duration_seconds=55, vertical=True,
    )
    if not meta:
        _notify(f"❌ Ranking falló generación · {topic['key']}", urgent=True)
        return {"status": "gen_fail", "topic_key": topic["key"]}

    print(f"  ranking: video generado · uploading canal TopRanking ES…")
    up = _upload_ranking(meta)
    if not up:
        _notify(f"⚠️ Ranking {topic['key']} generado pero upload falló",
                 urgent=True)
        return {"status": "upload_fail", "meta": meta}

    _mark_used(topic["key"])

    # Cross-post RRSS
    cross = _crosspost(meta["title"], up["url"], topic)
    cross_summary = " · ".join(f"{k}{'✅' if v else '❌'}" for k, v in cross.items())
    _notify(f"✅ <b>TopRanking ES</b> · {up['url']}\n"
            f"<i>{meta['title'][:60]}</i> · RRSS {cross_summary}")
    # MP4 → Telegram para subir manual a TikTok
    try:
        from ..notify_batch import send_video_for_tiktok
        vp = meta.get("video_path")
        if vp:
            send_video_for_tiktok(vp, "TopRanking ES", meta.get("title", ""), up["url"])
    except Exception as e:
        print(f"  ranking: TT tg video fail — {e}")
    return {"status": "ok", "slug": meta["slug"], "url": up["url"],
            "topic_key": topic["key"], "crosspost": cross}


def _crosspost(title: str, url: str, topic: dict) -> dict[str, bool]:
    """Cross-post ranking a Bluesky/Mastodon/Threads con marca 📊."""
    result: dict[str, bool] = {}
    teaser = f"📊 Ranking · {topic.get('fuente','')} · dato clave: {topic.get('cifra_ancla','')}"
    for name, poster_mod, icon in [
        ("bluesky", "videogen.bluesky_poster", "🦋"),
        ("mastodon", "videogen.mastodon_poster", "🐘"),
        ("threads", "videogen.threads_poster", "🧵"),
    ]:
        try:
            import importlib
            mod = importlib.import_module(poster_mod)
            fn = getattr(mod, f"post_short_to_{name}")
            r = fn(title, url, teaser=teaser)
            result[icon] = bool(r)
        except Exception as e:
            print(f"  ranking {name} fail: {e}")
            result[icon] = False
    return result
