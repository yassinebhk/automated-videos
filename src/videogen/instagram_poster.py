"""Auto-poster de Instagram Reels via Meta Graph API.

Por qué IG: audiencia masiva en España (12M usuarios activos ES). Reels es el
formato prioritario del algoritmo de IG desde 2023 → mismos shorts verticales
9:16 que ya generamos funcionan directo. Zero re-encoding.

Setup one-time (15 min):
1. facebook.com/business/tools/meta-business-suite → conectar tu FB Page
2. La cuenta IG debe ser "Business" o "Creator" (no personal) — cambio gratis
   en la app IG: Ajustes → Cuenta → Cambiar a cuenta profesional.
3. developers.facebook.com/apps → Create App (type: Business)
4. Add Product: "Instagram" → habilitar Instagram Graph API
5. Generar long-lived access token (60 días, auto-refresh vía cron):
   - Marca los permisos: instagram_content_publish, instagram_basic,
     pages_show_list, pages_read_engagement
6. Obtener el INSTAGRAM_BUSINESS_ACCOUNT_ID (via Graph Explorer o script)
7. Añadir a GitHub Secrets:
   - IG_ACCESS_TOKEN (long-lived, ~60 días)
   - IG_BUSINESS_ACCOUNT_ID

Después: cada Short YT se publica también como Reel en IG con la misma
descripción + hashtags. Rate limit: 25 posts/día = suficiente.

NOTA: IG requiere que el video esté HOSTED en una URL pública. Usamos el
mismo host de GitHub Pages que el podcast (docs/reels/<id>.mp4) para servir
los archivos. El video es <100MB por Short, no impacta.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any, Optional

import requests

from .config import ROOT


REELS_HOST_DIR = ROOT / "docs" / "reels"
# Sirvido por jsDelivr CDN (mirror de GitHub raw) con Content-Type correcto.
# GH Pages exigía dominio custom para nuestro caso; jsDelivr no.
PUBLIC_REELS_BASE = "https://cdn.jsdelivr.net/gh/yassinebhk/automated-videos@main/docs/reels"

# Instagram Business Login usa graph.instagram.com (v21+).
# El endpoint clásico graph.facebook.com/v21.0 es para "Facebook Login for
# Business" — otra ruta, otro token. Nosotros usamos IG Business Login.
IG_API_BASE = "https://graph.instagram.com/v21.0"


def _prepare_public_reel(local_mp4: Path, slug: str) -> Optional[str]:
    """Copia el vídeo a docs/reels/<slug>.mp4 para exponerlo vía GH Pages.
    Devuelve la URL pública o None si falla."""
    if not local_mp4.exists():
        return None
    REELS_HOST_DIR.mkdir(parents=True, exist_ok=True)
    dst = REELS_HOST_DIR / f"{slug}.mp4"
    if not dst.exists() or dst.stat().st_size != local_mp4.stat().st_size:
        shutil.copy2(local_mp4, dst)
    return f"{PUBLIC_REELS_BASE}/{slug}.mp4"


def _create_media_container(access_token: str, ig_account_id: str,
                             video_url: str, caption: str) -> Optional[str]:
    """Paso 1 de IG publish: subir el video a un container. Devuelve container_id."""
    r = requests.post(
        f"{IG_API_BASE}/{ig_account_id}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption[:2200],  # límite IG
            "share_to_feed": "true",
            "access_token": access_token,
        }, timeout=60,
    )
    data = r.json()
    if r.status_code != 200 or "id" not in data:
        print(f"  ig: container fail {r.status_code} — {str(data)[:200]}")
        return None
    return data["id"]


def _wait_container_ready(access_token: str, container_id: str, max_wait: int = 240) -> bool:
    """IG procesa el video en su lado. Esperar hasta status=FINISHED."""
    start = time.time()
    while time.time() - start < max_wait:
        r = requests.get(
            f"{IG_API_BASE}/{container_id}",
            params={"fields": "status_code,status", "access_token": access_token},
            timeout=20,
        )
        d = r.json()
        st = d.get("status_code", "").upper()
        if st == "FINISHED":
            return True
        if st == "ERROR":
            print(f"  ig: container ERROR — {d.get('status', '')[:200]}")
            return False
        time.sleep(5)
    print(f"  ig: container timeout tras {max_wait}s")
    return False


def _publish_container(access_token: str, ig_account_id: str, container_id: str) -> Optional[str]:
    """Paso 2: publicar el container. Devuelve media_id."""
    r = requests.post(
        f"{IG_API_BASE}/{ig_account_id}/media_publish",
        params={"creation_id": container_id, "access_token": access_token},
        timeout=30,
    )
    d = r.json()
    if r.status_code != 200:
        print(f"  ig: publish fail {r.status_code} — {str(d)[:200]}")
        return None
    return d.get("id")


def post_reel_to_instagram(video_title: str, video_url: str,
                            local_mp4: Path, slug: str,
                            teaser: str = "", dry_run: bool = False) -> dict[str, Any] | None:
    """Publica un Reel en IG. Requiere que el video esté disponible en URL
    pública — lo copiamos a docs/reels/<slug>.mp4 que sirve GH Pages.
    """
    # IG_TOKEN + IG_USER_ID vienen del setup con Instagram Business Login
    # (developers.facebook.com → app → Instagram → API setup). Los nombres
    # legacy IG_ACCESS_TOKEN + IG_BUSINESS_ACCOUNT_ID se mantienen como
    # fallback por si el entorno los tiene con la nomenclatura antigua.
    access_token = os.environ.get("IG_TOKEN") or os.environ.get("IG_ACCESS_TOKEN")
    ig_account_id = os.environ.get("IG_USER_ID") or os.environ.get("IG_BUSINESS_ACCOUNT_ID")
    if not (access_token and ig_account_id):
        print("  ig: skip — faltan IG_TOKEN o IG_USER_ID")
        return None

    from . import social_post
    caption, _ = social_post.build_viral_post(
        video_title, video_url, teaser=teaser, cross_platform=""
    )
    # IG permite hasta 30 hashtags — nuestro build_viral_post ya los mete
    caption = caption[:2200]

    if dry_run:
        print(f"  ig DRY-RUN — {len(caption)} chars:\n{caption}")
        return {"dry_run": True, "caption": caption}

    # 1) Copiar mp4 a docs/reels/ para servir vía GH Pages
    public_url = _prepare_public_reel(local_mp4, slug)
    if not public_url:
        print(f"  ig: no local mp4 → {local_mp4}")
        return None

    # 2) Container
    container_id = _create_media_container(access_token, ig_account_id, public_url, caption)
    if not container_id:
        return None

    # 3) Esperar procesamiento
    if not _wait_container_ready(access_token, container_id):
        return None

    # 4) Publish
    media_id = _publish_container(access_token, ig_account_id, container_id)
    if not media_id:
        return None

    url = f"https://instagram.com/reel/{media_id}"
    print(f"  ig: ✅ Reel published → {url}")
    return {"media_id": media_id, "url": url, "caption": caption}
