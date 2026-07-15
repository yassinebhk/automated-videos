"""Generación de imágenes con IA vía Pollinations.ai (gratis, sin API key).

Genera imágenes fotorrealistas relevantes al contenido de cada segmento, para
usarlas como fondo dinámico (en vez de stock de Pexels o fondos planos).
"""
from __future__ import annotations

import hashlib
import time
import urllib.parse
from pathlib import Path

import requests

from .config import pollinations_token

# Dos endpoints:
#  - autenticado (sk_ key, sin rate limits) si hay POLLINATIONS_TOKEN en .env
#  - anónimo gratis (funciona sin clave, con límite por ráfaga) por defecto
POLLINATIONS = "https://gen.pollinations.ai/image/{prompt}"
POLLINATIONS_ANON = "https://image.pollinations.ai/prompt/{prompt}"

STYLE_SUFFIX = (
    "photorealistic, cinematic, dramatic lighting, highly detailed, sharp focus, "
    "professional photography, natural undistorted proportions, vertical 9:16 composition, "
    "no text, no watermark, no logo"
)


def _cache_key(prompt: str, seed: int) -> str:
    return hashlib.sha1(f"{prompt}|{seed}".encode("utf-8")).hexdigest()[:12]


def generate_image(
    prompt: str,
    dest_dir: Path,
    seed: int = 0,
    width: int = 1080,
    height: int = 1920,
    retries: int = 3,
) -> Path | None:
    """Genera una imagen con Pollinations. Cacheada por (prompt, seed)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(prompt, seed)
    out = dest_dir / f"{key}.jpg"
    if out.exists() and out.stat().st_size > 5000:
        return out

    full_prompt = f"{prompt}, {STYLE_SUFFIX}"
    encoded = urllib.parse.quote(full_prompt, safe="")
    params = {
        "width": width,
        "height": height,
        "nologo": "true",
        "seed": seed,
        "model": "flux",
    }
    headers = {}
    token = pollinations_token()
    if token:
        url = POLLINATIONS.format(prompt=encoded)
        headers["Authorization"] = f"Bearer {token}"
        params["key"] = token
    else:
        # Endpoint anónimo gratis (verificado: responde 200 con image/jpeg)
        url = POLLINATIONS_ANON.format(prompt=encoded)

    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=120)
            ct = resp.headers.get("content-type", "")
            if resp.status_code == 200 and "image" in ct and len(resp.content) > 5000:
                out.write_bytes(resp.content)
                return out
            # 402/429 = rate limit por ráfaga → backoff más largo
            backoff = 8 * (attempt + 1) if resp.status_code in (402, 429) else 3 * (attempt + 1)
            print(f"  pollinations attempt {attempt+1}: HTTP {resp.status_code}, espera {backoff}s")
        except Exception as e:
            backoff = 5 * (attempt + 1)
            print(f"  pollinations attempt {attempt+1} timeout/error: {str(e)[:60]}")
        time.sleep(backoff)
    return None


def build_image_prompt(segment_text: str, visual_keywords: list[str]) -> str:
    """Construye un prompt de imagen rico a partir del segmento.

    Prioriza las visual_keywords (concretas) y añade contexto del texto.
    """
    kws = ", ".join(visual_keywords[:3]) if visual_keywords else ""
    return kws or segment_text[:120]


def build_hero_prompt(scripts) -> str:
    """Prompt de imagen para el frame 'wow' del teaser.

    Usa las visual_keywords (en inglés, que Flux entiende mejor) del teaser y
    el hook, con el topic como respaldo. Devuelve solo el sujeto/escena; el
    estilo cinematográfico lo añade generate_image (STYLE_SUFFIX).
    """
    en = getattr(scripts, "en", None)
    kws: list[str] = []
    for seg_name in ("teaser", "hook"):
        seg = getattr(en, seg_name, None) if en else None
        if seg and getattr(seg, "visual_keywords", None):
            kws.extend(seg.visual_keywords)
    uniq = list(dict.fromkeys(k.strip() for k in kws if k.strip()))[:4]
    base = ", ".join(uniq) if uniq else ""
    return base or getattr(scripts, "topic", "money concept")


def generate_hero_clip(scripts, work_dir, duration: float = 3.5):
    """Genera la imagen IA del teaser y la convierte en un clip con zoom suave.

    Devuelve un VideoClip listo para anteponer al primer segmento, o None si
    Pollinations no respondió. La imagen se cachea (compartida entre idiomas).
    """
    from . import graphics

    prompt = build_hero_prompt(scripts)
    img = generate_image(prompt, work_dir / "ai_hero", seed=7)
    if not img:
        return None
    try:
        return graphics.scene_to_clip(img, duration, work_dir / "ai_hero" / "hero.mp4")
    except Exception:
        return None
