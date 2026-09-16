"""Genera un Short de padel EN: voz Edge en-US (guion curado) con timings de
palabra → subtítulos sincronizados + animación de jugada (perspectiva) + mux.
Coste cero (sin LLM). ffmpeg image2 + mux (path CI)."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..config import ROOT
from . import court

PADEL_ROOT = ROOT / "output" / "padel_uploaded"
EDGE_VOICE = "en-US-GuyNeural"


def _synth(text: str, out_mp3: Path):
    """Devuelve lista [(start_sec, word)] y guarda mp3. edge-tts WordBoundary."""
    import asyncio
    import edge_tts
    words = []

    async def go():
        c = edge_tts.Communicate(text, EDGE_VOICE)
        with open(out_mp3, "wb") as f:
            async for ch in c.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    words.append((ch["offset"] / 1e7, ch["text"]))
    try:
        asyncio.run(go())
    except Exception as e:
        print(f"  padel: edge tts fail: {e}")
        return None, []
    return (out_mp3 if out_mp3.exists() else None), words


def _captions(words, per_line: int = 6):
    """Agrupa palabras en líneas de subtítulo con su tiempo de inicio."""
    timeline = []
    for i in range(0, len(words), per_line):
        chunk = words[i:i + per_line]
        if not chunk:
            continue
        start = chunk[0][0]
        text = " ".join(w for _, w in chunk)
        timeline.append((start, text))
    return timeline


def _duration(words, mp3: Path) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                            "-of", "json", str(mp3)], capture_output=True, text=True, timeout=30)
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return (words[-1][0] + 2.0) if words else 25.0


def _mux(video: Path, audio: Path, out: Path) -> Path:
    cmd = ["ffmpeg", "-y", "-i", str(video), "-i", str(audio),
           "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
           "-b:a", "128k", "-shortest", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return out if r.returncode == 0 else video
    except Exception:
        return video


def generate_padel_video(topic: dict, out_dir: Path):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"padel_{topic['key']}_{ts}"
    work = out_dir / slug
    work.mkdir(parents=True, exist_ok=True)

    voice, words = _synth(topic["narracion"], work / "voice.mp3")
    if not voice:
        return None
    dur = max(16.0, min(45.0, _duration(words, voice) + 0.8))
    captions = _captions(words)

    silent = court.render_play_video(topic["play"], topic["hook"], captions,
                                     work / "silent.mp4", dur)
    if not silent:
        return None
    final = _mux(silent, voice, work / "final.mp4")

    name = topic["titulo"]
    return {
        "slug": slug, "topic_key": topic["key"], "video_path": str(final),
        "title": f"{name} — Padel tip 🎾 #padel #shorts"[:100],
        "description": (
            f"{name}. {topic['hook']}\n\n"
            f"Padel tactics, explained on the court. General coaching tips.\n\n"
            f"#padel #padeltips #padeltactics #sport #shorts"
        ),
        "tags": ["padel", "padeltips", "padeltactics", "sport", "tennis"],
    }
