"""Auto-poster de Mastodon — red descentralizada con comunidad española activa.

Mastodon:
- API 100% abierta, sin App Review, sin captcha
- Registro en cualquier instancia (mastodon.social, mstdn.es, masto.es…)
- Token de acceso generado en 2 clicks desde Settings → Development
- Comunidad hispanohablante fuerte en periodismo, política, historia
- Sin límite duro de posts, rate-limit generoso (300 posts/día por defecto)

Estrategia:
- Post automático tras cada YT upload con hook + link + hashtags
- Al ser texto <= 500 chars, cabe el mismo mensaje que Bluesky
"""
from __future__ import annotations

import os
import re
from typing import Any


def post_short_to_mastodon(video_title: str, video_url: str,
                            teaser: str = "", dry_run: bool = False) -> dict[str, Any] | None:
    """Postea un toot a Mastodon + reply thread con contexto extra."""
    instance = os.environ.get("MASTODON_INSTANCE", "https://mastodon.social").rstrip("/")
    token = os.environ.get("MASTODON_ACCESS_TOKEN")
    if not token:
        print("  mastodon: skip — falta MASTODON_ACCESS_TOKEN")
        return None

    from . import social_post
    # Cross-mention: apuntar a Bluesky si está configurado
    bsky = os.environ.get("BLUESKY_HANDLE", "")
    cross = f"@{bsky} en Bluesky" if bsky else ""
    main_text, reply_text = social_post.build_viral_post(
        video_title, video_url, teaser=teaser, cross_platform=cross
    )
    # Mastodon acepta hasta 500 chars — usamos el build_viral pero ampliamos
    main_text = main_text[:499]

    if dry_run:
        print(f"  mastodon DRY-RUN — {instance}")
        print(f"    MAIN ({len(main_text)} chars):\n{main_text}")
        print(f"    REPLY ({len(reply_text)} chars):\n{reply_text}")
        return {"dry_run": True, "main": main_text, "reply": reply_text, "instance": instance}

    try:
        import requests
    except ImportError:
        print("  mastodon: requests no instalado")
        return None

    try:
        H = {"Authorization": f"Bearer {token}"}
        # Main post
        r = requests.post(f"{instance}/api/v1/statuses", headers=H,
                          data={"status": main_text, "visibility": "public"},
                          timeout=15)
        r.raise_for_status()
        data = r.json()
        post_url = data.get("url") or data.get("uri")
        main_id = data.get("id")
        print(f"  mastodon: ✅ main → {post_url}")

        # Reply thread — contexto extra
        try:
            rr = requests.post(f"{instance}/api/v1/statuses", headers=H,
                               data={"status": reply_text,
                                     "in_reply_to_id": main_id,
                                     "visibility": "public"},
                               timeout=15)
            rr.raise_for_status()
            print(f"  mastodon: ✅ reply thread posted")
        except Exception as e:
            print(f"  mastodon: ⚠ reply thread falló ({e}) — main OK igual")

        return {"url": post_url, "id": main_id, "instance": instance}
    except Exception as e:
        print(f"  mastodon: ❌ post falló ({type(e).__name__}: {str(e)[:200]})")
        return None
