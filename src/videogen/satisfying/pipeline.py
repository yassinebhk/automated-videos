"""Pipeline Infinite Fractals — satisfying fractal zoom (global, sin voz)."""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import ROOT
from . import generator


LEDGER = ROOT / "output" / "satisfying_ledger.json"
YT_PREFIX = "YT_SATISFYING"
DISPLAY_NAME = "Infinite Fractals"


def _load_ledger() -> dict[str, str]:
    if not LEDGER.exists():
        return {}
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(key: str) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    d = _load_ledger()
    d[key] = datetime.now(timezone.utc).isoformat()
    LEDGER.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def _pick_variant() -> dict:
    """Rota: elige la variante usada hace más tiempo (o nunca)."""
    used = _load_ledger()
    variants = generator.VARIANTS
    never = [v for v in variants if v["key"] not in used]
    if never:
        return random.choice(never)
    return min(variants, key=lambda v: used.get(v["key"], ""))


def _notify(text: str, urgent: bool = False) -> None:
    from ..notify_batch import add
    add(text, urgent=urgent)


def run_once() -> dict[str, Any]:
    """Genera + sube 1 fractal zoom al canal Infinite Fractals."""
    variant = _pick_variant()
    print(f"  satisfying: variant={variant['key']} ({variant['kind']})")
    meta = generator.generate_satisfying_video(generator.SATISFYING_ROOT, variant, seconds=30)
    if not meta:
        _notify(f"❌ Satisfying falló generación · {variant['key']}", urgent=True)
        return {"status": "gen_fail", "variant": variant["key"]}

    # YT upload opcional — si no hay YT_SATISFYING_REFRESH_TOKEN, va a IG+TT igual
    from ..upload_youtube import upload_video
    prev = os.environ.get("YT_CHANNEL_PREFIX", "")
    os.environ["YT_CHANNEL_PREFIX"] = YT_PREFIX
    has_creds = bool(os.environ.get(YT_PREFIX + "_REFRESH_TOKEN"))
    print(f"  satisfying: prefix={YT_PREFIX} · has_refresh={has_creds}")
    url = ""
    yt_status = "skip_no_creds"
    if has_creds:
        try:
            vid = upload_video(
                Path(meta["video_path"]), title=meta["title"][:100],
                description=meta["description"][:4900], tags=meta.get("tags", []),
                category_id="24", is_short=True, privacy="public",
            )
            url = f"https://youtube.com/shorts/{vid}"
            yt_status = "ok"
        except Exception as e:
            print(f"  satisfying upload fail: {type(e).__name__}: {e}")
            yt_status = f"fail: {type(e).__name__}"
    if prev:
        os.environ["YT_CHANNEL_PREFIX"] = prev
    else:
        os.environ.pop("YT_CHANNEL_PREFIX", None)

    _mark_used(variant["key"])
    yt_line = url if url else yt_status
    _notify(f"✅ <b>{DISPLAY_NAME}</b> · YT: {yt_line}\n<i>{meta['title'][:50]}</i>")
    # Crosspost IG (no requiere URL YT)
    try:
        from .. import crosspost_full
        cross = crosspost_full.crosspost_short_from_mp4(
            Path(meta["video_path"]), meta["title"], url,
            teaser=f"🌀 {variant['key']} fractal zoom",
            channel_label="satisfying", slug=meta["slug"],
        )
        _notify(f"🌀 <b>Satisfying · RRSS</b> {crosspost_full.summary_line(cross)}")
    except Exception as e:
        print(f"  satisfying crosspost fail: {e}")
    # TT video
    try:
        from ..notify_batch import send_video_for_tiktok
        send_video_for_tiktok(meta["video_path"], DISPLAY_NAME, meta["title"], url)
    except Exception as e:
        print(f"  satisfying: TT tg fail — {e}")
    try:
        from .. import social_reels
        social_reels.post_ig_reel(meta["video_path"], meta["title"], url, meta["slug"])
    except Exception as _e:
        print(f"  satisfying: ig fail — {_e}")
    return {"status": "ok", "slug": meta["slug"], "url": url,
            "variant": variant["key"], "yt_status": yt_status}
