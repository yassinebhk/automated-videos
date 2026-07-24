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


def _build_status(video_title: str, video_url: str) -> str:
    """Compone el toot (500 chars max en Mastodon)."""
    m = re.search(r"#(\d+):\s*(.+)", video_title)
    if m:
        num = m.group(1)
        case = m.group(2).strip()
        hook = f"📺 Estafas Españolas #{num}\n\n{case}"
    else:
        hook = video_title[:250]

    tags = "#TrueCrime #España #Estafas #Historia #Corrupción"
    text = f"{hook[:280]}\n\n{video_url}\n\n{tags}"
    return text[:499]


def post_short_to_mastodon(video_title: str, video_url: str,
                            dry_run: bool = False) -> dict[str, Any] | None:
    """Postea un toot a Mastodon con enlace al Short."""
    instance = os.environ.get("MASTODON_INSTANCE", "https://mastodon.social").rstrip("/")
    token = os.environ.get("MASTODON_ACCESS_TOKEN")
    if not token:
        print("  mastodon: skip — falta MASTODON_ACCESS_TOKEN")
        return None

    status = _build_status(video_title, video_url)

    if dry_run:
        print(f"  mastodon DRY-RUN — {instance}")
        print(f"    ({len(status)} chars):\n{status}")
        return {"dry_run": True, "text": status, "instance": instance}

    try:
        import requests
    except ImportError:
        print("  mastodon: requests no instalado")
        return None

    try:
        r = requests.post(
            f"{instance}/api/v1/statuses",
            headers={"Authorization": f"Bearer {token}"},
            data={"status": status, "visibility": "public"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        post_url = data.get("url") or data.get("uri")
        print(f"  mastodon: ✅ posted → {post_url}")
        return {"url": post_url, "id": data.get("id"), "instance": instance}
    except Exception as e:
        print(f"  mastodon: ❌ post falló ({type(e).__name__}: {str(e)[:200]})")
        return None
