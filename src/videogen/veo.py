"""Generación de hook clip con Veo 3.1 vía Google AI Studio (free tier).

Se llama solo para los primeros ~5s del video (el hook) para darle un punch
visual único. El resto del B-roll sigue siendo Pexels.

Si Gemini API no está configurada o falla (rate-limit, error), retorna None
y el caller hace fallback a Pexels.
"""
from __future__ import annotations

import time
from pathlib import Path

from .config import gemini_key
from .models import VideoClip


def generate_hook_clip(
    visual_prompt: str,
    dest_dir: Path,
    aspect_ratio: str = "9:16",
    duration_seconds: int = 8,
    timeout_seconds: int = 300,
) -> VideoClip | None:
    """Genera un clip Veo para el hook. Devuelve None si no hay key o falla."""
    api_key = gemini_key()
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("  google-genai not installed; skipping Veo")
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / "veo_hook.mp4"
    if out_path.exists():
        # Reuse si ya está cacheado
        return VideoClip(
            path=str(out_path),
            duration_seconds=float(duration_seconds),
            width=720 if aspect_ratio == "9:16" else 1280,
            height=1280 if aspect_ratio == "9:16" else 720,
            keyword="veo_hook",
        )

    try:
        client = genai.Client(api_key=api_key)
        print(f"  veo: generating hook clip ({aspect_ratio}, {duration_seconds}s)...")
        operation = client.models.generate_videos(
            model="veo-3.1-generate-preview",
            prompt=visual_prompt,
            config=types.GenerateVideosConfig(aspect_ratio=aspect_ratio),
        )

        start = time.monotonic()
        while not operation.done:
            if time.monotonic() - start > timeout_seconds:
                print("  veo: timeout, falling back to Pexels")
                return None
            time.sleep(10)
            operation = client.operations.get(operation)

        generated_video = operation.response.generated_videos[0]
        client.files.download(file=generated_video.video)
        generated_video.video.save(str(out_path))
        print(f"  veo: saved → {out_path.name}")
        return VideoClip(
            path=str(out_path),
            duration_seconds=float(duration_seconds),
            width=720 if aspect_ratio == "9:16" else 1280,
            height=1280 if aspect_ratio == "9:16" else 720,
            keyword="veo_hook",
        )
    except Exception as e:
        msg = str(e)
        if "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower() or "429" in msg:
            print(f"  veo: rate-limited, falling back to Pexels")
        else:
            print(f"  veo failed: {e}")
        return None


def build_visual_prompt(hook_text: str, visual_keywords: list[str]) -> str:
    """Combina texto del hook + keywords visuales en un prompt para Veo."""
    kws = ", ".join(visual_keywords[:4])
    return (
        f"Cinematic vertical video, 9:16 aspect ratio. {kws}. "
        f"High detail, professional documentary style, dramatic lighting, "
        f"shallow depth of field. No text overlay, no captions."
    )
