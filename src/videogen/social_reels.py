"""Helper compartido: postear un Short como Reel de Instagram (auto, Graph API).

Reusa instagram_poster (copia mp4 a docs/reels vía GH Pages + Graph API container).
Best-effort: nunca rompe el pipeline. Las creds IG (IG_TOKEN/IG_USER_ID) llegan por
.env en todos los jobs. Caption = título del vídeo (varía por vídeo) + teaser →
evita texto repetido que Meta borra (ver memoria threads-borrado-contenido-repetido).
"""
from __future__ import annotations

from pathlib import Path


def post_ig_reel(mp4_path, title: str, url: str, slug: str, teaser: str = "") -> bool:
    try:
        from .instagram_poster import post_reel_to_instagram
        p = Path(mp4_path)
        if not p.exists():
            print(f"  ig reel: mp4 no existe {mp4_path}")
            return False
        return bool(post_reel_to_instagram(title, url, p, slug, teaser=teaser))
    except Exception as e:
        print(f"  ig reel fail: {type(e).__name__}: {e}")
        return False
