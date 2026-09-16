"""Helper compartido: postear un Short como Reel de Instagram (Graph API oficial).

Construye un caption LIMPIO por canal (título del vídeo + hasta 5 hashtags
relevantes, barajados para no repetir el mismo set) — NO usa build_viral_post
(que es true-crime de WaitWhy). Soporta cuenta IG por canal via prefix.
Best-effort: nunca rompe el pipeline.
"""
from __future__ import annotations

import os
import random
from pathlib import Path


def _caption(title: str, hashtags) -> str:
    tags = [str(h).lstrip("#") for h in (hashtags or []) if str(h).strip()]
    random.shuffle(tags)
    tagline = " ".join(f"#{t}" for t in tags[:5])
    return (f"{title}\n\n{tagline}").strip() if tagline else (title or "")


def post_ig_reel(mp4_path, title: str, url: str, slug: str,
                 hashtags=None, teaser: str = "", prefix: str = "") -> bool:
    p = Path(mp4_path)
    if not p.exists():
        print(f"  ig reel: mp4 no existe {mp4_path}")
        return False
    caption = _caption(title, hashtags)
    prev = os.environ.get("YT_CHANNEL_PREFIX")
    if prefix:
        os.environ["YT_CHANNEL_PREFIX"] = prefix
    try:
        from .instagram_poster import post_reel_to_instagram
        return bool(post_reel_to_instagram(title, url, p, slug,
                                            teaser=teaser, caption_override=caption))
    except Exception as e:
        print(f"  ig reel fail: {type(e).__name__}: {e}")
        return False
    finally:
        if prefix:
            if prev is not None:
                os.environ["YT_CHANNEL_PREFIX"] = prev
            else:
                os.environ.pop("YT_CHANNEL_PREFIX", None)
