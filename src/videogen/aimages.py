"""Generación de imágenes con IA vía Pollinations.ai (gratis, sin API key).

Genera imágenes fotorrealistas relevantes al contenido de cada segmento, para
usarlas como fondo dinámico (en vez de stock de Pexels o fondos planos).

Fix 13/09/26: imágenes se veían todas iguales entre canales/videos:
  - Estilo por canal (noir true crime, tech motor, documental historia…)
  - Seed derivada del slug (no fija 0) → variación real
  - Rotación entre modelos flux / flux-realism / turbo
  - Prompts más ricos con composición + iluminación específica
  - Cache scoped por slug (no global)
"""
from __future__ import annotations

import hashlib
import os
import random
import time
import urllib.parse
from pathlib import Path

import requests

from .config import pollinations_token

POLLINATIONS = "https://gen.pollinations.ai/image/{prompt}"
POLLINATIONS_ANON = "https://image.pollinations.ai/prompt/{prompt}"


# ─── Estilo visual por canal ───
# Cada nicho tiene un tratamiento visual distinto. Cambiar aquí = todas
# las imágenes de ese canal se transforman coherentemente.
CHANNEL_STYLES: dict[str, dict] = {
    "": {  # WaitWhy — true crime
        "style": ("dark noir atmosphere, high contrast, moody shadows, "
                  "cinematic film grain, muted color palette, dramatic side lighting, "
                  "1970s-80s crime documentary aesthetic"),
        "models": ["flux", "flux-realism"],
        "avoid": "no bright cheerful colors, no cartoon",
    },
    "YT_TAX": {
        "style": ("clean editorial infographic style, warm office lighting, "
                  "modern minimalist composition, teal and gold accents, "
                  "professional business aesthetic, spanish office context"),
        "models": ["flux", "flux-realism", "turbo"],
        "avoid": "no crime scenes, no dark tones",
    },
    "YT_LEGAL": {
        "style": ("formal courtroom aesthetic, marble columns, wooden desks, "
                  "serious documentary lighting, blue-grey palette, "
                  "spanish legal context, thoughtful professional atmosphere"),
        "models": ["flux", "flux-realism"],
        "avoid": "no crime scenes, no dark tones, no violence",
    },
    "YT_AYUDAS": {
        "style": ("bright hopeful atmosphere, warm golden hour lighting, "
                  "spanish family homes, community feel, soft focus background, "
                  "documentary photography style, welcoming warm palette"),
        "models": ["flux", "turbo"],
        "avoid": "no dark tones, no corporate sterility",
    },
    "YT_MOTOR": {
        "style": ("automotive photography, dramatic side lighting on cars, "
                  "asphalt reflections, spanish urban and rural roads, "
                  "high-end car magazine aesthetic, orange and blue color grading"),
        "models": ["flux-realism", "flux"],
        "avoid": "no cartoons, no crashes",
    },
    "YT_POV": {
        "style": ("period-accurate historical scene, museum quality painting style "
                  "or vintage sepia photography, dramatic renaissance lighting, "
                  "historically accurate costumes and settings, epic documentary feel"),
        "models": ["flux", "flux-realism"],
        "avoid": "no modern elements, no anachronisms",
    },
    "YT_RANKING": {
        "style": ("bold infographic composition, vibrant contrasting colors, "
                  "clean modern data visualization aesthetic, dynamic diagonal lines, "
                  "eye-catching editorial magazine style, high saturation"),
        "models": ["turbo", "flux"],
        "avoid": "no cluttered background",
    },
    "YT_AMBIENT": {
        "style": ("serene minimalist nature scene, soft pastel colors, "
                  "misty atmospheric lighting, dreamy shallow depth of field, "
                  "meditation aesthetic, cool blue and lavender palette"),
        "models": ["flux", "flux-realism"],
        "avoid": "no people, no urban elements, no bright saturation",
    },
    "YT_IA": {
        "style": ("modern tech workspace, laptop screens glowing, futuristic UI overlays, "
                  "cyan and purple color palette, cyberpunk light accents, "
                  "clean minimalist tech aesthetic, spanish office context"),
        "models": ["turbo", "flux", "flux-realism"],
        "avoid": "no dark dystopian, no cartoons",
    },
}

# Sufijo genérico común (composición vertical + calidad + limpieza)
STYLE_COMMON = (
    "highly detailed, sharp focus, professional composition, "
    "natural undistorted proportions, vertical 9:16 composition, "
    "no text, no watermark, no logo, no border"
)


def _channel_style() -> dict:
    prefix = os.environ.get("YT_CHANNEL_PREFIX", "").strip()
    return CHANNEL_STYLES.get(prefix, CHANNEL_STYLES[""])


def _seed_from_slug(prompt: str, slug_or_hint: str = "") -> int:
    """Deriva un seed pseudo-aleatorio del slug del video + prompt.
    Sin slug usa timestamp → siempre nueva imagen (rompe cache).
    """
    key = f"{slug_or_hint}|{prompt}"
    if not slug_or_hint:
        key += f"|{int(time.time())}"
    h = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 999_999_999


def _cache_key(prompt: str, seed: int) -> str:
    return hashlib.sha1(f"{prompt}|{seed}".encode("utf-8")).hexdigest()[:12]


def generate_image(
    prompt: str,
    dest_dir: Path,
    seed: int | None = None,
    width: int = 1080,
    height: int = 1920,
    retries: int = 3,
    slug_hint: str = "",
) -> Path | None:
    """Genera una imagen con Pollinations. Estilo según YT_CHANNEL_PREFIX.

    seed: si None, se deriva de (slug + prompt) → cada video tiene composición
    única aunque comparta keywords con otros. Pasar seed explícito solo si se
    quiere reproducibilidad exacta (tests).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    style = _channel_style()
    style_str = style["style"]
    avoid = style.get("avoid", "")
    models = style.get("models", ["flux"])

    if seed is None:
        seed = _seed_from_slug(prompt, slug_hint or dest_dir.name)

    # Cache scoped por dest_dir (video-específico), no global. Evita reusar
    # imágenes entre videos distintos aunque el prompt coincida.
    key = _cache_key(prompt, seed)
    out = dest_dir / f"{key}.jpg"
    if out.exists() and out.stat().st_size > 5000:
        return out

    # Prompt final rico: sujeto + estilo canal + calidad + negatives
    parts = [prompt.strip(), style_str, STYLE_COMMON]
    if avoid:
        parts.append(avoid)
    full_prompt = ", ".join(parts)
    encoded = urllib.parse.quote(full_prompt, safe="")

    # Rota entre modelos válidos para el canal (variedad visual)
    model = random.choice(models)

    params = {
        "width": width,
        "height": height,
        "nologo": "true",
        "seed": seed,
        "model": model,
    }
    headers = {}
    token = pollinations_token()
    if token:
        url = POLLINATIONS.format(prompt=encoded)
        headers["Authorization"] = f"Bearer {token}"
        params["key"] = token
    else:
        url = POLLINATIONS_ANON.format(prompt=encoded)

    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=120)
            ct = resp.headers.get("content-type", "")
            if resp.status_code == 200 and "image" in ct and len(resp.content) > 5000:
                out.write_bytes(resp.content)
                return out
            backoff = 8 * (attempt + 1) if resp.status_code in (402, 429) else 3 * (attempt + 1)
            print(f"  pollinations attempt {attempt+1}: HTTP {resp.status_code} model={model}, espera {backoff}s")
        except Exception as e:
            backoff = 5 * (attempt + 1)
            print(f"  pollinations attempt {attempt+1} timeout/error: {str(e)[:60]}")
        time.sleep(backoff)
    return None


def build_image_prompt(segment_text: str, visual_keywords: list[str]) -> str:
    """Construye un prompt de imagen rico a partir del segmento.

    Mejor que solo keywords: añade contexto de escena del texto para que
    Flux tenga más señal. Prioriza keywords (concretas) sobre texto (verboso).
    """
    kws = [k.strip() for k in (visual_keywords or []) if k.strip()][:4]
    kws_part = ", ".join(kws)
    # Extrae "escena" del texto: primeras palabras impactantes (nombres propios,
    # números, verbos concretos). Recorta para no exceder rate limits Pollinations.
    text_snip = " ".join(segment_text.split()[:15]).strip()
    if kws_part and text_snip:
        return f"{kws_part}, scene depicting: {text_snip}"
    return kws_part or text_snip or "abstract concept"


def build_hero_prompt(scripts) -> str:
    """Prompt de imagen para el frame 'wow' del teaser."""
    en = getattr(scripts, "en", None)
    kws: list[str] = []
    for seg_name in ("teaser", "hook"):
        seg = getattr(en, seg_name, None) if en else None
        if seg and getattr(seg, "visual_keywords", None):
            kws.extend(seg.visual_keywords)
    uniq = list(dict.fromkeys(k.strip() for k in kws if k.strip()))[:4]
    base = ", ".join(uniq) if uniq else ""
    return base or getattr(scripts, "topic", "concept scene")


def generate_hero_clip(scripts, work_dir, duration: float = 3.5):
    """Genera la imagen IA del teaser y la convierte en un clip con zoom suave."""
    from . import graphics

    prompt = build_hero_prompt(scripts)
    # Seed derivada del slug del video → cada teaser único
    slug = work_dir.name if hasattr(work_dir, "name") else ""
    img = generate_image(prompt, work_dir / "ai_hero", slug_hint=f"hero:{slug}")
    if not img:
        return None
    try:
        return graphics.scene_to_clip(img, duration, work_dir / "ai_hero" / "hero.mp4")
    except Exception:
        return None
