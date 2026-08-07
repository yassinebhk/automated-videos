"""Auto-poster de X (Twitter) — API v2 con OAuth 1.0a.

Por qué X: audiencia hispanohablante enorme (~50M usuarios ES/LATAM), engagement
alto en política/crimen/economía → nicho perfecto para WaitWhy. Free tier
"Basic" da 500 tweets/mes = ~16/día, sobra para 2 shorts + 1 long-form/día.

Setup (10 min):
1. developer.twitter.com/en/portal/dashboard → Sign up → Free tier
2. Create App → generar 4 keys:
   - Consumer Key (X_API_KEY)
   - Consumer Secret (X_API_SECRET)
   - Access Token (X_ACCESS_TOKEN) — con permission "Read and Write"
   - Access Token Secret (X_ACCESS_SECRET)
3. Añadir los 4 como GitHub Secrets: gh secret set X_API_KEY, etc.

Después de setup: cada upload YT genera automáticamente un tweet con hook +
imagen del thumbnail + link. Rate limit 500/mes = plenty.
"""
from __future__ import annotations

import io
import os
from typing import Any, Optional


def _extract_video_id(video_url: str) -> Optional[str]:
    """Extrae el video_id de una URL de YT (shorts o watch)."""
    import re
    m = re.search(r"(?:shorts/|watch\?v=|youtu\.be/)([\w-]{11})", video_url)
    return m.group(1) if m else None


def _download_thumbnail(video_id: str) -> Optional[bytes]:
    """Descarga la thumbnail max-res del video. Fallback a hqdefault."""
    import requests
    for name in ("maxresdefault", "hqdefault", "mqdefault"):
        try:
            r = requests.get(f"https://img.youtube.com/vi/{video_id}/{name}.jpg", timeout=10)
            if r.status_code == 200 and len(r.content) > 5000:
                return r.content
        except Exception:
            continue
    return None


def post_short_to_x(video_title: str, video_url: str,
                    teaser: str = "", dry_run: bool = False) -> dict[str, Any] | None:
    """Publica un tweet con hook + imagen thumbnail + link al video.
    Devuelve dict con detalles o None si falla/faltan creds.
    """
    keys = {
        "consumer_key":       os.environ.get("X_API_KEY"),
        "consumer_secret":    os.environ.get("X_API_SECRET"),
        "access_token":       os.environ.get("X_ACCESS_TOKEN"),
        "access_token_secret": os.environ.get("X_ACCESS_SECRET"),
    }
    missing = [k for k, v in keys.items() if not v]
    if missing:
        print(f"  x: skip — faltan creds X_{'/'.join(m.upper() for m in missing)}")
        return None

    from . import social_post
    main_text, _ = social_post.build_viral_post(
        video_title, video_url, teaser=teaser, cross_platform=""
    )
    # X permite 280 chars — nuestro main ya está dentro
    if len(main_text) > 280:
        main_text = main_text[:277] + "…"

    if dry_run:
        print(f"  x DRY-RUN — {len(main_text)} chars:\n{main_text}")
        return {"dry_run": True, "text": main_text}

    try:
        import tweepy
    except ImportError:
        print("  x: tweepy no instalado, skip (añade tweepy>=4.14 a pyproject.toml)")
        return None

    # Descargar thumbnail YT para adjuntar como imagen
    vid = _extract_video_id(video_url)
    media_id = None
    if vid:
        thumb_bytes = _download_thumbnail(vid)
        if thumb_bytes:
            try:
                # API v1.1 para media upload (v2 no soporta media upload aún en 2026)
                auth_v1 = tweepy.OAuth1UserHandler(
                    keys["consumer_key"], keys["consumer_secret"],
                    keys["access_token"], keys["access_token_secret"],
                )
                api_v1 = tweepy.API(auth_v1)
                media = api_v1.media_upload(
                    filename=f"{vid}.jpg",
                    file=io.BytesIO(thumb_bytes),
                )
                media_id = media.media_id
                print(f"  x: thumbnail uploaded → media_id {media_id}")
            except Exception as e:
                print(f"  x: media upload falló ({type(e).__name__}: {str(e)[:120]}) — post sin imagen")

    # V2 client para el tweet propiamente
    try:
        client_v2 = tweepy.Client(
            consumer_key=keys["consumer_key"],
            consumer_secret=keys["consumer_secret"],
            access_token=keys["access_token"],
            access_token_secret=keys["access_token_secret"],
        )
        resp = client_v2.create_tweet(
            text=main_text,
            media_ids=[media_id] if media_id else None,
        )
        if resp and resp.data:
            tweet_id = resp.data["id"]
            url = f"https://x.com/i/status/{tweet_id}"
            print(f"  x: ✅ posted → {url}")
            return {"tweet_id": tweet_id, "url": url, "text": main_text}
        print(f"  x: create_tweet no devolvió data → {resp}")
        return None
    except Exception as e:
        err = str(e)[:200]
        print(f"  x: ❌ post falló ({type(e).__name__}: {err})")
        return None
