"""Auto-poster de Threads (Meta) via Threads API.

Threads (Meta, 2023) tiene 275M usuarios activos en 2026, crece rápido en la
comunidad ES. Formato tipo X pero más orientado a texto largo. Perfecto para
publicar el hook + court_source + link YT.

Setup one-time (10 min, PIGGYBACK del setup de IG):
1. developers.facebook.com/apps → tu App
2. Add Product: "Threads" (separado de Instagram)
3. Generar token para Threads:
   - Permisos requeridos: threads_basic, threads_content_publish
4. Añadir a GitHub Secrets:
   - THREADS_ACCESS_TOKEN (mismo formato que IG, pero token separado)
   - THREADS_USER_ID (obtener con Graph Explorer sobre /me)

Después: cada upload YT se publica también en Threads (thread de 2 posts:
main + reply con court_source). Rate limit generoso.
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

import requests


def _create_thread(access_token: str, user_id: str, text: str,
                    reply_to: Optional[str] = None) -> Optional[str]:
    """Crea un container de post en Threads. Devuelve container_id."""
    params = {
        "media_type": "TEXT",
        "text": text[:500],  # Threads permite hasta 500 chars
        "access_token": access_token,
    }
    if reply_to:
        params["reply_to_id"] = reply_to
    r = requests.post(
        f"https://graph.threads.net/v1.0/{user_id}/threads",
        params=params, timeout=30,
    )
    data = r.json()
    if r.status_code != 200 or "id" not in data:
        print(f"  threads: container fail {r.status_code} — {str(data)[:200]}")
        return None
    return data["id"]


def _publish_thread(access_token: str, user_id: str, container_id: str) -> Optional[str]:
    """Publica el container. Devuelve media_id."""
    # Threads necesita ~30s de procesamiento antes de publicar
    time.sleep(30)
    r = requests.post(
        f"https://graph.threads.net/v1.0/{user_id}/threads_publish",
        params={"creation_id": container_id, "access_token": access_token},
        timeout=30,
    )
    data = r.json()
    if r.status_code != 200:
        print(f"  threads: publish fail {r.status_code} — {str(data)[:200]}")
        return None
    return data.get("id")


def post_short_to_threads(video_title: str, video_url: str,
                          teaser: str = "", dry_run: bool = False) -> dict[str, Any] | None:
    """Publica un thread (post + reply) en Threads. Devuelve dict o None."""
    # THREADS_TOKEN es el nombre nuevo (setup 2025 con "Generate Token" en
    # el panel developer). THREADS_ACCESS_TOKEN es el legacy — mantenemos
    # ambos para no romper entornos antiguos.
    access_token = os.environ.get("THREADS_TOKEN") or os.environ.get("THREADS_ACCESS_TOKEN")
    user_id = os.environ.get("THREADS_USER_ID")
    if not (access_token and user_id):
        print("  threads: skip — faltan THREADS_TOKEN o THREADS_USER_ID")
        return None

    from . import social_post
    main_text, reply_text = social_post.build_viral_post(
        video_title, video_url, teaser=teaser, cross_platform=""
    )
    # Threads permite 500 chars — nuestro main ya está dentro
    main_text = main_text[:500]
    reply_text = reply_text[:500]

    if dry_run:
        print(f"  threads DRY-RUN — main {len(main_text)} chars:\n{main_text}")
        print(f"  threads DRY-RUN — reply {len(reply_text)} chars:\n{reply_text}")
        return {"dry_run": True, "main": main_text, "reply": reply_text}

    # Main post
    container = _create_thread(access_token, user_id, main_text)
    if not container:
        return None
    main_id = _publish_thread(access_token, user_id, container)
    if not main_id:
        return None
    print(f"  threads: ✅ main → {main_id}")

    # Reply thread
    try:
        reply_container = _create_thread(access_token, user_id, reply_text, reply_to=main_id)
        if reply_container:
            reply_id = _publish_thread(access_token, user_id, reply_container)
            if reply_id:
                print(f"  threads: ✅ reply → {reply_id}")
    except Exception as e:
        print(f"  threads: ⚠ reply falló ({type(e).__name__}: {e}) — main OK")

    url = f"https://threads.net/@{user_id}/post/{main_id}"
    return {"main_id": main_id, "url": url, "text": main_text}
