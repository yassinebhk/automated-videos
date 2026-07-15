"""Descarga de B-roll desde Pexels API."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import requests

from .config import pexels_key
from .models import VideoClip


PEXELS_SEARCH = "https://api.pexels.com/videos/search"


def _cache_key(keyword: str) -> str:
    return hashlib.sha1(keyword.lower().encode("utf-8")).hexdigest()[:12]


_NEGATIVE_TOKENS = {
    # Off-topic for nature/science docs
    "toy", "toys", "wooden", "cardboard", "drawing", "drawn",
    "cooked", "cooking", "grilled", "dish", "food", "recipe", "meal",
    "kitchen", "chef", "restaurant", "plate", "fried", "sushi",
    "cartoon", "puppet", "stuffed", "plush",
    "halloween", "costume", "fake", "mascot",
    # Modern lifestyle / outdoor people que rompen temas históricos o serios
    "hiker", "hiking", "hike", "climber", "climbing", "trekking", "trek",
    "backpacker", "backpack", "tourist", "tourism", "traveler", "traveller",
    "vlog", "vlogger", "selfie", "jogging", "jogger", "running", "runner",
    "trail", "camping", "camper", "yoga", "fitness", "workout", "gym",
    "influencer", "lifestyle", "fashion", "model", "smiling", "wedding",
    "businessman", "businesswoman", "office",
}


def _score_video(vid: dict, kw_tokens: set[str], orientation: str) -> float:
    """Puntúa un resultado de Pexels por relevancia + calidad técnica.

    Factores:
    - Match de tokens del keyword en URL/uploader (+3 cada uno)
    - **PENALIZA tokens negativos** que indican contenido off-topic (-5 cada uno)
    - Resolución máxima disponible (1080p +2, 1440p +0.5, 2160p +0.5)
    - Duración suficiente (+1 si ≥5s, +0.5 si ≥8s)
    - Orientación correcta (+0.5)
    """
    url = (vid.get("url") or "").lower()
    user_name = (vid.get("user", {}).get("name") or "").lower()
    haystack = f"{url} {user_name}"
    # Tokens del URL slug (separados por guiones)
    url_tokens = set(url.replace("/", "-").split("-"))

    score = 0.0
    for tok in kw_tokens:
        if len(tok) < 3:
            continue
        if tok in haystack:
            score += 3.0

    # Penalización fuerte por tokens negativos (cooked, toy, cartoon, etc.)
    for neg in _NEGATIVE_TOKENS:
        if neg in url_tokens:
            score -= 5.0

    duration = vid.get("duration", 0)
    if duration >= 5:
        score += 1.0
    if duration >= 8:
        score += 0.5

    files = vid.get("video_files", [])
    # Resolución máxima disponible (la dimensión larga)
    max_long = 0
    has_correct_orientation = False
    for f in files:
        w, h = f.get("width", 0), f.get("height", 0)
        if not w or not h:
            continue
        long_side = max(w, h)
        max_long = max(max_long, long_side)
        is_portrait = h > w
        if (orientation == "portrait" and is_portrait) or (
            orientation == "landscape" and not is_portrait
        ):
            has_correct_orientation = True

    if max_long >= 1920:  # full HD
        score += 2.0
    if max_long >= 2560:
        score += 0.5
    if max_long >= 3840:
        score += 0.5
    if has_correct_orientation:
        score += 0.5

    return score


def search_clip(
    keyword: str,
    dest_dir: Path,
    min_duration: float = 3.0,
    orientation: str = "portrait",
) -> VideoClip | None:
    """Busca un clip en Pexels matching keyword.

    Pide 15 candidatos, los puntúa por relevancia (URL slug match, duración,
    orientación) y descarga el mejor. Resultado cacheado en dest_dir.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    cache_key = _cache_key(keyword)
    cached_meta = dest_dir / f"{cache_key}.json"
    if cached_meta.exists():
        clip = VideoClip.model_validate_json(cached_meta.read_text(encoding="utf-8"))
        mp4 = dest_dir / f"{cache_key}.mp4"
        if mp4.exists():
            clip.path = str(mp4)  # corrige ruta si la carpeta se movió (pending→uploaded)
            return clip

    resp = requests.get(
        PEXELS_SEARCH,
        headers={"Authorization": pexels_key()},
        params={
            "query": keyword,
            "per_page": 15,
            "orientation": orientation,
            "size": "large",  # ≥1080p para no pixelar al escalar
        },
        timeout=30,
    )
    resp.raise_for_status()
    videos = resp.json().get("videos", [])
    if not videos:
        return None

    kw_tokens = set(keyword.lower().split())
    # Filtra por duración mínima y puntúa el resto
    scored = [
        (_score_video(v, kw_tokens, orientation), v)
        for v in videos
        if v.get("duration", 0) >= min_duration
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    for _, vid in scored:
        files = vid.get("video_files", [])
        # Long-side closest to 1920 (full HD). Para portrait queremos 1080x1920;
        # para landscape, 1920x1080. En ambos casos el lado largo = 1920.
        mp4s = [
            f
            for f in files
            if f.get("file_type") == "video/mp4"
            and max(f.get("width", 0), f.get("height", 0)) >= 1280
        ]
        if not mp4s:
            continue
        mp4s.sort(
            key=lambda f: abs(max(f.get("width", 0), f.get("height", 0)) - 1920)
        )
        chosen = mp4s[0]
        url = chosen["link"]
        out_path = dest_dir / f"{cache_key}.mp4"
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(out_path, "wb") as fp:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    fp.write(chunk)

        clip = VideoClip(
            path=str(out_path),
            duration_seconds=float(vid.get("duration", 0)),
            width=int(chosen.get("width", 0)),
            height=int(chosen.get("height", 0)),
            keyword=keyword,
        )
        cached_meta.write_text(clip.model_dump_json(indent=2), encoding="utf-8")
        return clip
    return None


def fetch_broll(
    keywords: list[str], dest_dir: Path, orientation: str = "portrait"
) -> list[VideoClip]:
    """Descarga clips para cada keyword. Mantiene orden."""
    clips: list[VideoClip] = []
    for kw in keywords:
        try:
            clip = search_clip(kw, dest_dir, orientation=orientation)
        except Exception as e:
            print(f"  pexels failed for '{kw}': {e}")
            clip = None
        if clip:
            clips.append(clip)
    return clips


_STOPWORDS = {
    "why", "how", "what", "when", "where", "who", "the", "a", "an",
    "of", "for", "to", "in", "on", "at", "is", "are", "do", "does",
    "about", "with", "from", "that", "this", "your", "you", "its",
    "their", "and", "or", "but", "so", "than", "then", "into", "as",
    "be", "will", "can", "did", "has", "have",
}

# Genéricos que SÍ forman compound natural y merecen prepend (world cup, ...).
_COMPOUND_HEADS = {"world"}


# Palabras demasiado genéricas para usarse solas como anchor visual:
# Pexels devuelve contenido abstracto/irrelevante. Si el primer token es uno
# de estos, combinamos con el siguiente para concretar (ej. "world" → "world cup").
_GENERIC_FIRST = {
    "world", "thing", "things", "people", "life", "history", "fact",
    "facts", "data", "story", "stories", "best", "top", "most", "new",
    "real", "secret", "secrets", "amazing", "biggest", "greatest",
}


def topic_subject_from_slug(slug: str) -> str:
    """Extrae el sujeto visual del slug para anclar el primer frame.

    Devuelve el primer token significativo; si es demasiado genérico
    (ej. "world", "facts"), lo combina con el siguiente para concretar.

    Ej: "octopus-three-hearts-mystery" → "octopus"
    Ej: "world-cup-2026-curious-facts" → "world cup"
    Ej: "why-do-cats-purr" → "cats"
    """
    tokens = [
        p.strip().lower()
        for p in slug.split("-")
        if p.strip() and p.strip().lower() not in _STOPWORDS and not p.isdigit()
    ]
    if not tokens:
        return slug.replace("-", " ")

    # Primer token no-genérico = sujeto real
    non_generic = [t for t in tokens if t not in _GENERIC_FIRST]
    if not non_generic:
        return tokens[0]
    core = non_generic[0]
    core_idx = tokens.index(core)
    # Solo prepend si el token previo forma compound natural (ej. "world cup").
    if core_idx > 0 and tokens[core_idx - 1] in _COMPOUND_HEADS:
        return f"{tokens[core_idx - 1]} {core}"
    return core


def fetch_clips_for_segments(
    segments,
    dest_dir: Path,
    orientation: str = "portrait",
    topic_anchor: str | None = None,
) -> None:
    """Para cada TimedSegment, descarga clips matching sus visual_keywords.
    Muta los segmentos in-place añadiendo .clips. Garantiza ≥1 clip por segmento.

    Si se pasa `topic_anchor`, se PREPONE como primer keyword del hook
    (índice 0), garantizando que la primera imagen del video sea on-topic.
    """
    for seg in segments:
        # Confiamos en las keywords curadas por Gemini (la primera del teaser
        # es la imagen icónica del topic). El scoring + penalización filtran ruido.
        for kw in seg.visual_keywords:
            try:
                clip = search_clip(kw, dest_dir, orientation=orientation)
            except Exception as e:
                print(f"  pexels failed for '{kw}': {e}")
                continue
            if clip:
                seg.clips.append(clip)
        if not seg.clips:
            # Fallback: el sujeto del topic, o las primeras palabras del segmento
            fallback = topic_anchor or " ".join(seg.text.split()[:3])
            print(f"  ⚠ seg {seg.label}: sin clips, fallback a '{fallback}'")
            try:
                clip = search_clip(fallback, dest_dir, orientation=orientation)
                if clip:
                    seg.clips.append(clip)
            except Exception:
                pass
