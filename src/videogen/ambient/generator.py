"""Generador del video ambient/relax completo.

Pipeline:
1. Elige topic no-usado recientemente (ledger)
2. Descarga música CC0 de Pixabay (30-60 min, loopeando si hace falta)
3. Descarga imagen de Pexels
4. ffmpeg: image_loop + audio + fade_in/out → mp4 final
5. Gemini: título SEO long-tail + descripción con timestamps + tags
6. Devuelve dict con paths + metadata para uploader
"""
from __future__ import annotations

import json
import random
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from ..config import ROOT
from . import topic_pool

AMBIENT_ROOT = ROOT / "output" / "ambient_uploaded"
AMBIENT_LEDGER = ROOT / "output" / "ambient_ledger.json"
COOLDOWN_DAYS = 14  # no repetir tema en 2 semanas


def _load_ledger() -> dict[str, list[str]]:
    """{ topic_key: [iso_timestamp, ...] }"""
    if not AMBIENT_LEDGER.exists():
        return {}
    try:
        return json.loads(AMBIENT_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_ledger(data: dict) -> None:
    AMBIENT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    AMBIENT_LEDGER.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                              encoding="utf-8")


def _mark_used(topic_key: str) -> None:
    ledger = _load_ledger()
    ledger.setdefault(topic_key, []).append(
        datetime.now(timezone.utc).isoformat())
    ledger[topic_key] = ledger[topic_key][-20:]  # cap history
    _save_ledger(ledger)


def _pick_topic() -> dict:
    """Elige topic no usado en últimos COOLDOWN_DAYS días."""
    ledger = _load_ledger()
    cutoff = datetime.now(timezone.utc) - timedelta(days=COOLDOWN_DAYS)
    available = []
    for t in topic_pool.all_topics():
        recent = ledger.get(t["key"], [])
        last_use = None
        for iso in recent[-1:]:
            try:
                last_use = datetime.fromisoformat(iso)
                break
            except Exception:
                continue
        if not last_use or last_use < cutoff:
            available.append(t)
    if not available:
        # Todos en cooldown → coge el más antiguo
        available = topic_pool.all_topics()
    return random.choice(available)


def _fetch_music(topic: dict, target_duration_seconds: int, out_dir: Path) -> Path | None:
    """Descarga música CC0 de Pixabay que dure >= target_duration.

    Pixabay Music API es gratuita y devuelve mp3 CC0 sin licencia. Si un solo
    track no cubre la duración, concatena varios con crossfade.
    """
    import os, requests
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        print("  ambient: falta PIXABAY_API_KEY — abortando descarga música")
        return None

    q = topic["pixabay_music_query"]
    try:
        r = requests.get(
            "https://pixabay.com/api/audio/",
            params={"key": key, "q": q, "per_page": 50, "safesearch": "true"},
            timeout=30,
        )
        data = r.json()
    except Exception as e:
        print(f"  ambient: Pixabay Music fetch fail — {e}")
        return None

    hits = data.get("hits", [])
    if not hits:
        print(f"  ambient: Pixabay Music sin resultados para '{q}'")
        return None

    # Baraja para variedad + prefiere tracks largos
    random.shuffle(hits)
    hits.sort(key=lambda h: -int(h.get("duration") or 0))

    tracks = []
    total = 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, h in enumerate(hits):
        dur = int(h.get("duration") or 0)
        url = h.get("audio", "") or h.get("url", "")
        if not url or dur < 60:
            continue
        try:
            audio = requests.get(url, timeout=60).content
        except Exception:
            continue
        p = out_dir / f"track_{i:02d}.mp3"
        p.write_bytes(audio)
        tracks.append(p)
        total += dur
        if total >= target_duration_seconds:
            break

    if not tracks or total < target_duration_seconds * 0.7:
        print(f"  ambient: no reunió duración suficiente ({total}s < {target_duration_seconds}s)")
        return None

    # Concatena con ffmpeg crossfade 3s entre tracks
    concat_file = out_dir / "concat.txt"
    concat_file.write_text("\n".join(f"file '{t.name}'" for t in tracks))
    output = out_dir / "audio.mp3"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(output),
    ]
    r = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"  ambient: ffmpeg concat fail — {r.stderr[:200]}")
        return None
    return output


def _fetch_image(topic: dict, out_dir: Path) -> Path | None:
    """Descarga imagen HD de Pexels."""
    import os, requests
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        print("  ambient: falta PEXELS_API_KEY")
        return None
    q = topic["pexels_image_query"]
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": q, "per_page": 20, "orientation": "landscape"},
            timeout=30,
        )
        data = r.json()
    except Exception as e:
        print(f"  ambient: Pexels image fetch fail — {e}")
        return None
    photos = data.get("photos", [])
    if not photos:
        return None
    photo = random.choice(photos)
    url = (photo.get("src") or {}).get("original") or photo["src"]["large2x"]
    try:
        content = requests.get(url, timeout=30).content
    except Exception:
        return None
    p = out_dir / "cover.jpg"
    p.write_bytes(content)
    return p


def _build_video(image: Path, audio: Path, out_dir: Path,
                  duration_seconds: int) -> Path | None:
    """ffmpeg: image loop + audio → mp4 1920x1080. Fade in/out 3s."""
    output = out_dir / "video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image),
        "-i", str(audio),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-vf", (
            "scale=1920:1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080,"
            "fade=t=in:st=0:d=3,"
            f"fade=t=out:st={duration_seconds-3}:d=3"
        ),
        "-shortest",
        "-t", str(duration_seconds),
        str(output),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    if r.returncode != 0:
        print(f"  ambient: ffmpeg video fail — {r.stderr[-400:]}")
        return None
    return output


def _generate_seo_metadata(topic: dict, duration_min: int) -> dict:
    """Gemini genera título SEO long-tail + descripción + tags."""
    from google import genai
    from google.genai import types
    import os

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    modifier = random.choice(topic["modifiers"])
    base_kw = random.choice(topic["base_keywords"])

    if not key:
        # Fallback estático
        return {
            "title": f"{base_kw.title()} {duration_min} minutos · {modifier}",
            "description": (
                f"{base_kw.title()} durante {duration_min} minutos ideal para "
                f"{modifier}. Sin anuncios interrumpiendo.\n\n"
                f"#relax #{topic['mood']}"
            ),
            "tags": [base_kw, modifier, topic["mood"], "relax", "música"],
        }

    prompt = f"""Genera metadata SEO para un video de YouTube en español.

Nicho: música ambiental/relax
Tema: {topic['key']} ({topic['mood']})
Palabra clave base: {base_kw}
Modificador: {modifier}
Duración: {duration_min} minutos

Devuelve JSON con:
- title (max 100 chars, incluye la keyword base + modificador + duración, muy SEO)
- description (~400 chars, tono cálido, invita a suscribirse, con 3 timestamps ficticios spaced, cierra con hashtags)
- tags (lista de 10 keywords SEO, sin #)

NO uses emojis en title. Sí en description con moderación.
Devuelve SOLO JSON."""

    try:
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=1.0,
                max_output_tokens=800,
            ),
        )
        data = json.loads((resp.text or "{}").strip())
        if data.get("title") and data.get("description"):
            return {
                "title": data["title"][:100],
                "description": data["description"][:4900],
                "tags": data.get("tags", [])[:15],
            }
    except Exception as e:
        print(f"  ambient: Gemini SEO fail — {e}")

    return {
        "title": f"{base_kw.title()} {duration_min} minutos · {modifier}",
        "description": (
            f"{base_kw.title()} durante {duration_min} minutos ideal para "
            f"{modifier}. Sin anuncios interrumpiendo.\n\n#relax"
        ),
        "tags": [base_kw, modifier, topic["mood"]],
    }


def generate_ambient_video() -> dict[str, Any] | None:
    """Pipeline completo. Devuelve dict con metadata + paths, o None si falla."""
    topic = _pick_topic()
    duration_min = random.randint(
        topic["min_duration_minutes"], topic["max_duration_minutes"])
    duration_sec = duration_min * 60

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"{topic['key']}_{duration_min}min_{ts}"
    work_dir = AMBIENT_ROOT / slug
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"  ambient: topic={topic['key']} duración={duration_min}min slug={slug}")

    # 1. Música
    audio = _fetch_music(topic, duration_sec, work_dir)
    if not audio:
        return None

    # 2. Imagen
    image = _fetch_image(topic, work_dir)
    if not image:
        return None

    # 3. Video (image loop + audio + fade)
    video = _build_video(image, audio, work_dir, duration_sec)
    if not video:
        return None

    # 4. SEO metadata
    meta = _generate_seo_metadata(topic, duration_min)

    # 5. Marca ledger
    _mark_used(topic["key"])

    result = {
        "slug": slug,
        "topic_key": topic["key"],
        "duration_seconds": duration_sec,
        "video_path": str(video),
        "audio_path": str(audio),
        "image_path": str(image),
        "title": meta["title"],
        "description": meta["description"],
        "tags": meta["tags"],
    }
    # Persist para el uploader
    (work_dir / "metadata.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
