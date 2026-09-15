"""Pipeline Pádel Pro ES — consejo + jugada animada."""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import ROOT
from . import generator, topic_pool

LEDGER = ROOT / "output" / "padel_ledger.json"
YT_PREFIX = "YT_PADEL"
DISPLAY_NAME = "Pádel Pro ES"


def _load_ledger() -> dict[str, str]:
    if not LEDGER.exists():
        return {}
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(key: str) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    d = _load_ledger(); d[key] = datetime.now(timezone.utc).isoformat()
    LEDGER.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def _pick_topic() -> dict:
    used = _load_ledger()
    pool = topic_pool.all_topics()
    never = [t for t in pool if t["key"] not in used]
    if never:
        return random.choice(never)
    return min(pool, key=lambda t: used.get(t["key"], ""))


def _notify(text: str, urgent: bool = False) -> None:
    from ..notify_batch import add
    add(text, urgent=urgent)


def run_once() -> dict[str, Any]:
    topic = _pick_topic()
    print(f"  padel: topic={topic['key']}")
    meta = generator.generate_padel_video(topic, generator.PADEL_ROOT)
    if not meta:
        _notify(f"❌ Pádel falló generación · {topic['key']}", urgent=True)
        return {"status": "gen_fail", "topic_key": topic["key"]}

    from ..upload_youtube import upload_video
    prev = os.environ.get("YT_CHANNEL_PREFIX", "")
    os.environ["YT_CHANNEL_PREFIX"] = YT_PREFIX
    print(f"  padel: prefix={YT_PREFIX} · has_refresh={bool(os.environ.get(YT_PREFIX + '_REFRESH_TOKEN'))}")
    try:
        vid = upload_video(Path(meta["video_path"]), title=meta["title"][:100],
                           description=meta["description"][:4900], tags=meta.get("tags", []),
                           category_id="17", is_short=True, privacy="public")
        url = f"https://youtube.com/shorts/{vid}"
    except Exception as e:
        print(f"  padel upload fail: {type(e).__name__}: {e}")
        _notify(f"⚠️ Pádel {topic['key']} generado, upload falló", urgent=True)
        return {"status": "upload_fail", "topic_key": topic["key"]}
    finally:
        if prev:
            os.environ["YT_CHANNEL_PREFIX"] = prev
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)

    _mark_used(topic["key"])
    _notify(f"✅ <b>{DISPLAY_NAME}</b> · {url}\n<i>{topic['titulo']}</i>")
    try:
        from ..notify_batch import send_video_for_tiktok
        send_video_for_tiktok(meta["video_path"], DISPLAY_NAME, topic["titulo"], url)
    except Exception as e:
        print(f"  padel: TT tg fail — {e}")
    return {"status": "ok", "slug": meta["slug"], "url": url, "topic_key": topic["key"]}
