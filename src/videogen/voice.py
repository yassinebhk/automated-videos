"""Síntesis de voz con timestamps por palabra.

Motor por defecto: Edge TTS (Microsoft, gratis e ILIMITADO, sin API key).
Alternativa: ElevenLabs (mejor calidad, de pago) vía VOICE_ENGINE=elevenlabs.
"""
from __future__ import annotations

import asyncio
import base64
import os
import re
from pathlib import Path

import requests

from .config import elevenlabs_key, elevenlabs_voice
from .models import LocalizedScript, VoiceTrack, WordTimestamp


def voice_engine() -> str:
    return os.environ.get("VOICE_ENGINE", "edge").strip().lower()


def _clean_for_tts(text: str) -> str:
    """Normaliza el texto para que Edge TTS suene fluido sin pausas innecesarias.

    Edge pausa en CADA coma/punto y coma → quitamos las comas de FRASE (coma
    seguida de espacio) para que la locución fluya. NO tocamos los decimales
    tipo "6,34" (coma entre dígitos, sin espacio) ni los miles "1.000".
    Mantenemos puntos (pausa natural de fin de frase)."""
    text = text.replace("…", " ").replace("...", " ")
    text = re.sub(r"\s*\n\s*", " ", text)              # saltos de línea → espacio
    text = re.sub(r"[;,]\s+", " ", text)               # coma/; de frase → sin pausa
    text = re.sub(r"\s*:\s+", ". ", text)              # ":" → punto (pausa natural, no rara)
    text = re.sub(r"\s+([.!?])", r"\1", text)          # espacio antes de puntuación
    text = re.sub(r"\s+", " ", text)                    # espacios múltiples
    return text.strip()


# Voces Edge por defecto (neuronales, buena calidad ES/EN)
EDGE_VOICES = {
    "es": os.environ.get("EDGE_VOICE_ES", "es-ES-AlvaroNeural"),
    "en": os.environ.get("EDGE_VOICE_EN", "en-US-GuyNeural"),
}


def synthesize(script: LocalizedScript, dest_dir: Path) -> VoiceTrack:
    """Sintetiza la voz del script según el motor configurado."""
    if voice_engine() == "elevenlabs":
        return _synthesize_elevenlabs(script, dest_dir)
    return _synthesize_edge(script, dest_dir)


# ---------------------------------------------------------------- Edge TTS
def _synthesize_edge(script: LocalizedScript, dest_dir: Path) -> VoiceTrack:
    import edge_tts

    dest_dir.mkdir(parents=True, exist_ok=True)
    voice = EDGE_VOICES.get(script.lang, EDGE_VOICES["en"])
    text = _clean_for_tts(script.full_text())
    audio_path = dest_dir / f"voice_{script.lang}.mp3"

    rate = os.environ.get("EDGE_RATE", "+10%")  # ágil pero natural

    async def _run() -> list[WordTimestamp]:
        communicate = edge_tts.Communicate(
            text, voice, rate=rate, boundary="WordBoundary"
        )
        words: list[WordTimestamp] = []
        with open(audio_path, "wb") as f:
            async for ch in communicate.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    start = ch["offset"] / 1e7
                    dur = ch["duration"] / 1e7
                    words.append(
                        WordTimestamp(word=ch["text"], start=start, end=start + dur)
                    )
        return words

    words = asyncio.run(_run())
    duration = words[-1].end if words else 0.0

    track = VoiceTrack(
        lang=script.lang,
        audio_path=str(audio_path),
        duration_seconds=duration,
        words=words,
    )
    (dest_dir / f"voice_{script.lang}.json").write_text(
        track.model_dump_json(indent=2), encoding="utf-8"
    )
    return track


# ---------------------------------------------------------------- ElevenLabs
TIMESTAMPS_URL = (
    "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
)


def _chars_to_words(
    chars: list[str], starts: list[float], ends: list[float]
) -> list[WordTimestamp]:
    words: list[WordTimestamp] = []
    cur_word = ""
    cur_start: float | None = None
    cur_end: float | None = None

    def flush():
        nonlocal cur_word, cur_start, cur_end
        if cur_word.strip() and cur_start is not None and cur_end is not None:
            words.append(
                WordTimestamp(word=cur_word.strip(), start=cur_start, end=cur_end)
            )
        cur_word = ""
        cur_start = None
        cur_end = None

    for c, s, e in zip(chars, starts, ends):
        if c.isspace():
            flush()
        else:
            if cur_start is None:
                cur_start = s
            cur_end = e
            cur_word += c
    flush()
    return words


def _synthesize_elevenlabs(script: LocalizedScript, dest_dir: Path) -> VoiceTrack:
    dest_dir.mkdir(parents=True, exist_ok=True)
    voice_id = elevenlabs_voice(script.lang)
    text = script.full_text()

    resp = requests.post(
        TIMESTAMPS_URL.format(voice_id=voice_id),
        headers={"xi-api-key": elevenlabs_key(), "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.3,
                "use_speaker_boost": True,
            },
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    audio_bytes = base64.b64decode(data["audio_base64"])
    audio_path = dest_dir / f"voice_{script.lang}.mp3"
    audio_path.write_bytes(audio_bytes)

    alignment = data.get("alignment") or data.get("normalized_alignment") or {}
    words = _chars_to_words(
        alignment.get("characters", []),
        alignment.get("character_start_times_seconds", []),
        alignment.get("character_end_times_seconds", []),
    )
    duration = words[-1].end if words else 0.0

    track = VoiceTrack(
        lang=script.lang,
        audio_path=str(audio_path),
        duration_seconds=duration,
        words=words,
    )
    (dest_dir / f"voice_{script.lang}.json").write_text(
        track.model_dump_json(indent=2), encoding="utf-8"
    )
    return track
