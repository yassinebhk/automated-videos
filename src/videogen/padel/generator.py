"""Genera un short de consejo de pádel: voz Edge (guion curado) + animación de
pista + mux ffmpeg. Coste cero (sin LLM). Reusa edge-tts y ffmpeg (probado CI)."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..config import ROOT
from . import court

PADEL_ROOT = ROOT / "output" / "padel_uploaded"
EDGE_VOICE = "es-ES-AlvaroNeural"


def _synth_voice(text: str, out_mp3: Path) -> Path | None:
    try:
        import asyncio
        import edge_tts

        async def go():
            c = edge_tts.Communicate(text, EDGE_VOICE)
            await c.save(str(out_mp3))
        asyncio.run(go())
        return out_mp3 if out_mp3.exists() else None
    except Exception as e:
        print(f"  padel: voz edge fail: {e}")
        return None


def _audio_duration(path: Path) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                            "-of", "json", str(path)], capture_output=True, text=True, timeout=30)
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 25.0


def _mux(video: Path, audio: Path, out: Path) -> Path:
    cmd = ["ffmpeg", "-y", "-i", str(video), "-i", str(audio),
           "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
           "-b:a", "128k", "-shortest", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return out if r.returncode == 0 else video
    except Exception:
        return video


def generate_padel_video(topic: dict, out_dir: Path) -> dict | None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"padel_{topic['key']}_{ts}"
    work = out_dir / slug
    work.mkdir(parents=True, exist_ok=True)

    voice = _synth_voice(topic["narracion"], work / "voice.mp3")
    if not voice:
        return None
    dur = max(18.0, min(58.0, _audio_duration(voice) + 1.0))

    anim = court.render_play_animation(topic["play"], topic["titulo"], work / "anim.mp4", dur)
    if not anim:
        return None
    final = _mux(anim, voice, work / "final.mp4")

    return {
        "slug": slug, "topic_key": topic["key"], "video_path": str(final),
        "title": f"{topic['titulo']} 🎾 Consejo de pádel #shorts"[:100],
        "description": (
            f"{topic['titulo']} — consejo de pádel.\n\n"
            f"Recreación de la jugada en pista. Consejos generales de técnica.\n\n"
            f"#padel #padeltips #padel2026 #deporte #consejos #shorts"
        ),
        "tags": ["padel", "padeltips", "deporte", "consejos", "padel2026"],
    }
