"""Auto-poster de Bluesky — tráfico externo gratis via AT Protocol.

Bluesky (2026) tiene ~35M users, API 100% abierta, sin App Review, sin
captcha. Se autentica con handle + app-password (generado en Settings → App
Passwords) sin exponer la contraseña principal de la cuenta.

Estrategia:
- Después de cada upload YT, si BLUESKY_HANDLE + BLUESKY_APP_PASSWORD están
  configurados, se postea el vídeo con:
    - Card enlace (embed) al YT Short → thumbnail + título + descripción de
      Bluesky auto-generados con OpenGraph
    - Texto corto (280 chars max) con hook + hashtags relevantes
- Un post por Short (sin cooldown — cada Short = 1 post).
- Rate limits de Bluesky: 3000/día (más que sobrado).
"""
from __future__ import annotations

import os
from typing import Any


def _build_post_text(video_title: str, video_url: str) -> str:
    """Compone el texto del post (max 300 chars incluyendo URL y hashtags).

    Bluesky da mucho valor a hashtags temáticos y hooks emocionales cortos —
    el algoritmo prioriza engagement inmediato.
    """
    # Extraer caso del title "Estafas Españolas #47: X"
    import re
    m = re.search(r"#(\d+):\s*(.+)", video_title)
    if m:
        num = m.group(1)
        case = m.group(2).strip()
        hook = f"📺 Estafas Españolas #{num}\n\n{case}"
    else:
        hook = video_title[:180]

    # Hashtags cortos y temáticos
    tags = "#truecrime #España #estafas #historia"
    # URL cuenta como ~30 chars, hashtags ~40. Deja ~230 para el hook.
    text = f"{hook[:200]}\n\n{video_url}\n\n{tags}"
    # Bluesky limit = 300 grapheme clusters (aprox 300 chars)
    return text[:299]


def post_short_to_bluesky(video_title: str, video_url: str,
                          dry_run: bool = False) -> dict[str, Any] | None:
    """Postea un enlace al Short en Bluesky. Devuelve dict con detalles o None."""
    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not (handle and password):
        print("  bluesky: skip — faltan credenciales (BLUESKY_HANDLE/APP_PASSWORD)")
        return None

    text = _build_post_text(video_title, video_url)

    if dry_run:
        print(f"  bluesky DRY-RUN — {handle}")
        print(f"    Text ({len(text)} chars):\n{text}")
        return {"dry_run": True, "text": text, "handle": handle}

    try:
        from atproto import Client, client_utils
    except ImportError:
        print("  bluesky: atproto no instalado, skip")
        return None

    try:
        c = Client()
        c.login(handle, password)

        # Build rich text con facets (link clickeable + hashtags como facets)
        tb = client_utils.TextBuilder()
        # Extraer partes: pre-URL, URL, post-URL con hashtags
        lines = text.split("\n\n")
        # lines: [hook, url, hashtags]
        if len(lines) >= 3:
            tb.text(lines[0] + "\n\n")
            tb.link(video_url, video_url)
            tb.text("\n\n")
            for tag in lines[2].split():
                tb.tag(tag, tag.lstrip("#"))
                tb.text(" ")
        else:
            tb.text(text)

        resp = c.send_post(tb)
        # Construir URL del post: https://bsky.app/profile/handle/post/rkey
        rkey = resp.uri.split("/")[-1]
        post_url = f"https://bsky.app/profile/{handle}/post/{rkey}"
        print(f"  bluesky: ✅ posted → {post_url}")
        return {"handle": handle, "url": post_url, "uri": resp.uri, "cid": resp.cid}
    except Exception as e:
        print(f"  bluesky: ❌ post falló ({type(e).__name__}: {str(e)[:200]})")
        return None
