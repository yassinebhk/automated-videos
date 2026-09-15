"""Shorts ambient (30-45s vertical 9:16) — cebo para el canal MenteEnCalma.

Estrategia: shorts que muestran fragmento del audio ambient del canal
(muestra tipo "trailer") + CTA claro para ir al long-form completo.

Formato:
  - 40s duración total
  - 9:16 vertical (1080×1920)
  - Audio: 40s de Freesound/Pixabay (mismo topic pool que long-form)
  - Video: crossfade entre 3-4 imágenes verticales Pexels con Ken Burns
  - Overlay texto:
      • Top: título topic tipo "🎧 Ondas Alfa · Estudiar"
      • Bottom animado: "3 HORAS en el canal ↑ MenteEnCalma"
  - CTA en descripción: link al long-form más reciente del mismo tema
"""
from __future__ import annotations

import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import ROOT
from . import generator, topic_pool, topic_refresher

SHORTS_ROOT = ROOT / "output" / "ambient_shorts_uploaded"
SHORT_DURATION_SEC = 40


def _pick_topic_for_short():
    """Elige topic al azar del pool merged (mismo criterio que long-form)."""
    all_pool = topic_refresher.get_all_topics_merged()
    return random.choice(all_pool)


def _fetch_short_images(topic: dict, out_dir: Path, n: int = 4) -> list[Path]:
    """Descarga N imágenes verticales Pexels para short."""
    import os, requests
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        return []
    q = topic["pexels_image_query"]
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": q, "per_page": max(15, n * 2),
                     "orientation": "portrait", "size": "large"},
            timeout=30,
        )
        photos = r.json().get("photos", [])
    except Exception as e:
        print(f"  short-amb: Pexels fail — {e}")
        return []
    if not photos:
        return []
    random.shuffle(photos)
    downloaded = []
    for i, photo in enumerate(photos[:n]):
        url = (photo.get("src") or {}).get("portrait") or photo["src"]["large"]
        try:
            content = requests.get(url, timeout=30).content
            p = out_dir / f"vert_{i:02d}.jpg"
            p.write_bytes(content)
            downloaded.append(p)
        except Exception:
            continue
    return downloaded


def _fetch_short_audio(topic: dict, out_dir: Path) -> Path | None:
    """Reusa la cascada de audio del generator (Pixabay → Freesound → noise).
    Duración target 40s. Para binaural, generado por ffmpeg directamente."""
    if topic.get("mood_type") == "binaural":
        from . import binaural
        audio_path = out_dir / "binaural.m4a"
        return binaural.generate_binaural(
            audio_path, duration_seconds=SHORT_DURATION_SEC,
            carrier_hz=topic.get("carrier_hz", 200),
            beat_hz=topic.get("beat_hz", 8),
            volume=0.3,
            wave=topic.get("wave", "binaural"),
        )
    # Non-binaural: usa el _fetch_music (Pixabay→Freesound→noise)
    return generator._fetch_music(topic, SHORT_DURATION_SEC, out_dir)


def _build_short_video(images: list[Path], audio: Path, topic: dict,
                        out_dir: Path) -> Path | None:
    """Genera short 9:16 con crossfade imágenes + overlay texto."""
    if not images:
        return None
    output = out_dir / "video_es_vertical.mp4"

    # Título corto para overlay top (extraído del primer base_keyword)
    kws = topic.get("base_keywords", [])
    title_top = (kws[0] if kws else topic.get("mood", "Relax"))[:40]
    # CTA bottom
    cta = "MENTEENCALMA · Suscríbete"

    # Escapa caracteres especiales para ffmpeg drawtext
    def _esc(s):
        return s.replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")

    title_esc = _esc(title_top)
    cta_esc = _esc(cta)

    # Crossfade 4 imágenes × 10s = 40s. Cada imagen mini-clip.
    per_img = SHORT_DURATION_SEC // len(images)
    mini_dir = out_dir / "mini"
    mini_dir.mkdir(exist_ok=True)
    mini_clips = []
    for i, img in enumerate(images):
        mc = mini_dir / f"m{i:02d}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", "30", "-i", str(img),
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
            "-r", "30", "-pix_fmt", "yuv420p",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-t", str(per_img), "-an", str(mc),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and mc.exists():
            mini_clips.append(mc)
    if not mini_clips:
        return None

    # Concat mini-clips + audio + overlay text (drawtext)
    concat = out_dir / "concat_short.txt"
    concat.write_text("\n".join(f"file '{mc.relative_to(out_dir)}'" for mc in mini_clips))

    # Overlay text: título top con fondo semi + CTA bottom pulsante
    vf = (
        f"drawtext=text='{title_esc}':fontcolor=white:fontsize=60:"
        f"borderw=4:bordercolor=black:x=(w-text_w)/2:y=100,"
        f"drawtext=text='{cta_esc}':fontcolor=yellow:fontsize=50:"
        f"borderw=4:bordercolor=black:x=(w-text_w)/2:y=h-200:"
        f"box=1:boxcolor=black@0.5:boxborderw=15,"
        f"fade=t=in:st=0:d=1,fade=t=out:st={SHORT_DURATION_SEC-1}:d=1"
    )
    cmd_final = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-i", str(audio),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-r", "30", "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-vf", vf,
        "-shortest", "-t", str(SHORT_DURATION_SEC),
        str(output),
    ]
    r = subprocess.run(cmd_final, cwd=out_dir, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"  short-amb: ffmpeg fail — {r.stderr[-400:]}")
        return None
    # Limpieza
    import shutil
    shutil.rmtree(mini_dir, ignore_errors=True)
    concat.unlink(missing_ok=True)
    return output


def generate_ambient_short() -> dict[str, Any] | None:
    """Genera 1 short ambient para MenteEnCalma. Devuelve meta dict o None."""
    topic = _pick_topic_for_short()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"short_{topic['key']}_{ts}"
    work_dir = SHORTS_ROOT / slug
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"  short-amb: topic={topic['key']}")

    # 1. Audio 40s
    audio = _fetch_short_audio(topic, work_dir)
    if not audio:
        print("  short-amb: audio fail")
        return None

    # 2. Imágenes verticales
    images = _fetch_short_images(topic, work_dir, n=4)
    if not images:
        print("  short-amb: imágenes fail — abortando")
        return None

    # 3. Video con overlay
    video = _build_short_video(images, audio, topic, work_dir)
    if not video:
        return None

    kws = topic.get("base_keywords", [])
    title = kws[0][:80] if kws else f"MenteEnCalma · {topic.get('mood','relax')}"
    if "#Shorts" not in title:
        display_title = title
    else:
        display_title = title
    description = (
        f"{title}\n\n"
        f"🎧 VERSIÓN COMPLETA (varias horas) en el canal ↑\n"
        f"Suscríbete a MenteEnCalma para más música de estudio, dormir, "
        f"meditación y relax.\n\n"
        f"#Shorts #Relax #Estudiar #Dormir #Meditar #Concentracion"
    )

    return {
        "slug": slug,
        "topic_key": topic["key"],
        "video_path": str(video),
        "audio_path": str(audio),
        "title": display_title,
        "description": description,
        "tags": ["relax", "estudiar", "dormir", "meditar",
                  topic.get("mood", "relax"), "shorts", "musica"],
    }
