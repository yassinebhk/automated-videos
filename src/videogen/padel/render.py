"""Render de una táctica de pádel: escena Manim + voz Edge + música + mux SIN cortes.

Se ejecuta dentro del job de GitHub Actions que instala manim+cairo/pango+ffmpeg
(solo para command=padel-once). Reproduce el pipeline validado del render-test:
  1. manim -qm --disable_caching <Scene>  → mp4 mudo 1080x1920
  2. Edge TTS (en-US-GuyNeural, rate -6%)  → voice.mp3 (narración didáctica)
  3. Pixabay music (best-effort)           → music.mp3
  4. mux: tpad congela la tarjeta de cierre + apad en la voz → final sin cortes
"""
from __future__ import annotations

import asyncio
import os
import random
import subprocess
from pathlib import Path

SCENE_FILE = Path(__file__).parent / "manim_scene.py"
EDGE_VOICE = "en-US-GuyNeural"
EDGE_RATE = "-6%"


def _render_manim(scene_class: str, topic_env: str | None = None) -> Path | None:
    base = SCENE_FILE.parent
    media = base / "media"
    subprocess.run(["rm", "-rf", str(media)], check=False)
    env = dict(os.environ)
    if topic_env:
        env["PADEL_TOPIC"] = topic_env  # plantillas data-driven leen esto
    cmd = ["manim", "-qm", "--disable_caching", str(SCENE_FILE.name), scene_class]
    r = subprocess.run(cmd, cwd=str(base), capture_output=True, text=True, timeout=900, env=env)
    if r.returncode != 0:
        print(f"  padel: manim FAIL ({scene_class})\n{r.stderr[-1500:]}")
        return None
    hits = [h for h in (base / "media").rglob(f"{scene_class}.mp4") if "videos" in h.parts]
    if not hits:
        hits = list((base / "media").rglob(f"{scene_class}.mp4"))
    return hits[0] if hits else None


async def _edge_voice(text: str, out: Path) -> None:
    import edge_tts
    await edge_tts.Communicate(text, EDGE_VOICE, rate=EDGE_RATE).save(str(out))


def _fetch_music(work: Path) -> Path | None:
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        return None
    try:
        import requests
        q = random.choice(["upbeat energetic sport", "motivational upbeat",
                           "electronic upbeat", "corporate positive energetic"])
        r = requests.get("https://pixabay.com/api/audio/",
                         params={"key": key, "q": q, "per_page": 20, "safesearch": "true"},
                         headers={"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                                 "AppleWebKit/537.36 (KHTML, like Gecko) "
                                                 "Chrome/122.0.0.0 Safari/537.36")},
                         timeout=30).json()
        for h in r.get("hits", []):
            u = h.get("audio") or h.get("url") or ""
            if u:
                p = work / "music.mp3"
                p.write_bytes(requests.get(u, timeout=60).content)
                return p
    except Exception as e:
        print(f"  padel: music fail ({e})")
    return None


def _probe_dur(p: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(p)],
            capture_output=True, text=True, timeout=60).stdout.strip()
        return float(out)
    except Exception:
        return 0.0


def _mux(video: Path, voice: Path, music: Path | None, work: Path) -> Path:
    vdur, adur = _probe_dur(video), _probe_dur(voice)
    final_len = round(max(vdur, adur) + 1.2, 2)
    pad = round(max(0.0, final_len - vdur), 2)
    out = work / "final.mp4"
    if music:
        fc = (f"[1:v]tpad=stop_mode=clone:stop_duration={pad}[v];"
              f"[2:a]apad[vo];[0:a]volume=0.09[bg];"
              f"[vo][bg]amix=inputs=2:duration=first:dropout_transition=0[a]")
        cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(music),
               "-i", str(video), "-i", str(voice), "-filter_complex", fc,
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-preset", "veryfast", "-c:a", "aac", "-b:a", "160k", "-t", str(final_len), str(out)]
    else:
        fc = f"[0:v]tpad=stop_mode=clone:stop_duration={pad}[v];[1:a]apad[a]"
        cmd = ["ffmpeg", "-y", "-i", str(video), "-i", str(voice), "-filter_complex", fc,
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-preset", "veryfast", "-c:a", "aac", "-b:a", "160k", "-t", str(final_len), str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"  padel: mux FAIL\n{r.stderr[-1200:]}")
        return video
    return out


def render_topic(topic: dict, work: Path) -> Path | None:
    """Renderiza cualquier topic (tactic/fact/compare/checklist) completo
    (vídeo+voz+música). Devuelve mp4 final o None."""
    import json as _json
    from . import manim_scene
    fmt = topic.get("format", "tactic")
    topic_env = None
    if fmt == "tactic":
        scene = manim_scene.TACTICS[topic["tactic"]]["scene"]
        narration = manim_scene.narration_for(scene)
    else:
        scene = manim_scene.FORMAT_SCENES[fmt]
        narration = topic.get("narration") or manim_scene.narration_for(scene)
        topic_env = _json.dumps(topic, ensure_ascii=False)
    work.mkdir(parents=True, exist_ok=True)
    print(f"  padel: render Manim {scene} (format={fmt})")
    silent = _render_manim(scene, topic_env=topic_env)
    if not silent:
        return None
    voice = work / "voice.mp3"
    try:
        asyncio.run(_edge_voice(narration, voice))
    except Exception as e:
        print(f"  padel: voice FAIL ({e})")
        return None
    music = _fetch_music(work)
    print(f"  padel: mux (music={'sí' if music else 'no'})")
    return _mux(silent, voice, music, work)
