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


def post_short_to_bluesky(video_title: str, video_url: str,
                          teaser: str = "", dry_run: bool = False) -> dict[str, Any] | None:
    """Postea un enlace al Short en Bluesky. Devuelve dict con detalles o None."""
    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not (handle and password):
        print("  bluesky: skip — faltan credenciales (BLUESKY_HANDLE/APP_PASSWORD)")
        return None

    from . import social_post
    # Cross-mention: apuntar a Mastodon si está configurado
    masto = os.environ.get("MASTODON_INSTANCE", "").rstrip("/")
    cross = ""
    if masto and os.environ.get("MASTODON_ACCESS_TOKEN"):
        cross = f"@automated_videos@{masto.replace('https://','')}"
    main_text, reply_text = social_post.build_viral_post(
        video_title, video_url, teaser=teaser, cross_platform=cross
    )

    if dry_run:
        print(f"  bluesky DRY-RUN — {handle}")
        print(f"    MAIN ({len(main_text)} chars):\n{main_text}")
        print(f"    REPLY ({len(reply_text)} chars):\n{reply_text}")
        return {"dry_run": True, "main": main_text, "reply": reply_text, "handle": handle}

    try:
        from atproto import Client, client_utils, models
    except ImportError:
        print("  bluesky: atproto no instalado, skip")
        return None

    try:
        c = Client()
        c.login(handle, password)

        # Main post: rich text con hashtags como facets + link clickable
        tb = client_utils.TextBuilder()
        for chunk in _tokenize_for_facets(main_text, video_url):
            kind, val = chunk
            if kind == "url":
                tb.link(val, val)
            elif kind == "tag":
                tb.tag(val, val.lstrip("#"))
            else:
                tb.text(val)
        resp_main = c.send_post(tb)
        rkey = resp_main.uri.split("/")[-1]
        main_url = f"https://bsky.app/profile/{handle}/post/{rkey}"
        print(f"  bluesky: ✅ main → {main_url}")

        # Reply del thread: contexto extra
        try:
            parent_ref = models.create_strong_ref(resp_main)
            reply_ref = models.AppBskyFeedPost.ReplyRef(
                parent=parent_ref, root=parent_ref
            )
            resp_reply = c.send_post(reply_text, reply_to=reply_ref)
            print(f"  bluesky: ✅ reply thread posted")
        except Exception as e:
            print(f"  bluesky: ⚠ reply thread falló ({e}) — main OK igual")

        return {"handle": handle, "url": main_url, "uri": resp_main.uri, "cid": resp_main.cid}
    except Exception as e:
        print(f"  bluesky: ❌ post falló ({type(e).__name__}: {str(e)[:200]})")
        return None


def _tokenize_for_facets(text: str, url: str):
    """Divide el texto en (kind, value) para TextBuilder — reconoce URL y #tags."""
    import re as _re
    idx = 0
    for m in _re.finditer(r"(https?://\S+)|(#[A-Za-zÁÉÍÓÚÑáéíóúñ]+)", text):
        s, e = m.span()
        if s > idx:
            yield ("text", text[idx:s])
        if m.group(1):
            yield ("url", m.group(1))
        else:
            yield ("tag", m.group(2))
        idx = e
    if idx < len(text):
        yield ("text", text[idx:])
