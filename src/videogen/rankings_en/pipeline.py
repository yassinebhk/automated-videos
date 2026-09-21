"""Pipeline Global Rankings EN — canal #11 (bar chart race en inglés).

Reusa el generador de `ranking` con branding EN. Sube a YT_RANKINGS_*.
Si faltan los secrets YT_RANKINGS_*, el upload falla y se notifica (aislado).
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from ..config import ROOT
from ..ranking import generator
from ..ranking.generator import RankingBranding
from . import topic_pool


RANKINGS_EN_LEDGER = ROOT / "output" / "rankings_en_ledger.json"
RANKINGS_EN_ROOT = ROOT / "output" / "rankings_en_uploaded"
COOLDOWN_DAYS = 90
YT_PREFIX = "YT_RANKINGS"
DISPLAY_NAME = "Global Rankings"


EN_BRANDING = RankingBranding(
    lang="en",
    intro_subtitle="Verified data · Global Rankings",
    outro_line1="Surprised?",
    outro_line2="Subscribe for more rankings",
    outro_brand="Global Rankings",
    source_label="Source",
    disclaimer="Approximate data from public sources. Verify before citing.",
    hashtags="#ranking #top10 #data #facts #statistics #barchartrace #Shorts",
    tags=["ranking", "top10", "data", "statistics", "barchartrace"],
)


def _load_ledger() -> dict[str, str]:
    if not RANKINGS_EN_LEDGER.exists():
        return {}
    try:
        return json.loads(RANKINGS_EN_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(key: str) -> None:
    RANKINGS_EN_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    d = _load_ledger()
    d[key] = datetime.now(timezone.utc).isoformat()
    RANKINGS_EN_LEDGER.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


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


def _upload(meta: dict) -> dict | None:
    # 21/09: sin canal YT propio → redirige a YT_AITOOLS (único canal EN
    # que tenemos). Override con env RANKINGS_EN_HOST_YT_PREFIX.
    from ..upload_youtube import upload_video
    host_prefix = YT_PREFIX
    if not os.environ.get(YT_PREFIX + "_REFRESH_TOKEN"):
        host_prefix = os.environ.get("RANKINGS_EN_HOST_YT_PREFIX", "YT_AITOOLS").strip()
    prev = os.environ.get("YT_CHANNEL_PREFIX", "")
    os.environ["YT_CHANNEL_PREFIX"] = host_prefix
    print(f"  rankings-en: YT host={host_prefix} · "
          f"has_refresh={bool(os.environ.get(host_prefix + '_REFRESH_TOKEN'))}")
    try:
        vid = upload_video(
            Path(meta["video_path"]),
            title=meta["title"][:100],
            description=meta["description"][:4900],
            tags=meta.get("tags", []),
            category_id="27",
            is_short=True,
            privacy="public",
        )
        return {"video_id": vid, "url": f"https://youtube.com/shorts/{vid}"}
    except Exception as e:
        print(f"  rankings-en upload fail: {type(e).__name__}: {e}")
        return None
    finally:
        if prev:
            os.environ["YT_CHANNEL_PREFIX"] = prev
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)


def _notify(text: str, urgent: bool = False) -> None:
    from ..notify_batch import add
    add(text, urgent=urgent)


def _send_tt_video(meta: dict, url: str) -> None:
    try:
        from ..notify_batch import send_video_for_tiktok
        vp = meta.get("video_path")
        if vp:
            send_video_for_tiktok(vp, DISPLAY_NAME, meta.get("title", ""), url)
    except Exception as e:
        print(f"  rankings-en: TT tg video fail — {e}")


def run_once() -> dict[str, Any]:
    """Genera + sube 1 bar chart race EN al canal Global Rankings.

    21/09: reactivado. Sin canal YT propio → redirige a YT_AITOOLS (único
    canal EN existente). Ver _upload() para el fallback host.
    """
    topic = _pick_topic()
    if not topic:
        return {"status": "no_topic"}

    print(f"  rankings-en: topic={topic['key']}")
    meta = generator.generate_ranking_video(
        topic, RANKINGS_EN_ROOT,
        duration_seconds=55, vertical=True,
        branding=EN_BRANDING,
    )
    if not meta:
        _notify(f"❌ Global Rankings falló generación · {topic['key']}", urgent=True)
        return {"status": "gen_fail", "topic_key": topic["key"]}

    print(f"  rankings-en: video generado · uploading canal {DISPLAY_NAME}…")
    up = _upload(meta)
    if not up:
        _notify(f"⚠️ Global Rankings {topic['key']} generado pero upload falló", urgent=True)
        return {"status": "upload_fail", "meta": meta}

    _mark_used(topic["key"])
    _notify(f"✅ <b>{DISPLAY_NAME}</b> · {up['url']}\n<i>{meta['title'][:60]}</i>")
    _send_tt_video(meta, up["url"])
    # Crosspost RRSS unificado (BS + MA + TH + IG @waitwhy_)
    try:
        from .. import crosspost_full
        teaser = f"📊 Global ranking · {topic.get('fuente','')} · verified data"
        cross = crosspost_full.crosspost_short_from_mp4(
            Path(meta["video_path"]), meta["title"], up["url"],
            teaser=teaser, channel_label="rankings-en", slug=meta["slug"],
        )
        _notify(f"📊 <b>Rankings EN · RRSS</b> {crosspost_full.summary_line(cross)}")
    except Exception as e:
        print(f"  rankings-en crosspost fail: {e}")
    try:
        from .. import social_reels
        social_reels.post_ig_reel(meta["video_path"], meta.get("title", ""), up["url"], meta["slug"], hashtags=meta.get("tags"), prefix=YT_PREFIX)
    except Exception as _e:
        print(f"  rankings-en: ig fail — {_e}")
    return {"status": "ok", "slug": meta["slug"], "url": up["url"], "topic_key": topic["key"]}
