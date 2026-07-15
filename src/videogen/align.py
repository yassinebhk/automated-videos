"""Alineamiento temporal: divide el voice track en ventanas por segmento del script."""
from __future__ import annotations

from .models import LocalizedScript, TimedSegment, VoiceTrack


def segment_timings(script: LocalizedScript, voice: VoiceTrack) -> list[TimedSegment]:
    """Reparte la duración del audio entre los segmentos del script,
    proporcionalmente al número de caracteres de cada uno.

    Esto es robusto frente a variaciones de la voz ya que asume que
    ElevenLabs habla a ~constante chars/segundo dentro del mismo idioma.
    """
    segments_raw = script.ordered_segments()
    total_chars = sum(len(s.text) for _, s in segments_raw) or 1
    duration = voice.duration_seconds

    timed: list[TimedSegment] = []
    cur = 0.0
    for idx, (label, seg) in enumerate(segments_raw):
        share = len(seg.text) / total_chars
        seg_duration = duration * share
        timed.append(
            TimedSegment(
                index=idx,
                label=label,
                text=seg.text,
                start=cur,
                end=cur + seg_duration,
                visual_keywords=list(seg.visual_keywords),
            )
        )
        cur += seg_duration
    # Ajuste final para que el último segmento termine exacto en duration
    if timed:
        timed[-1].end = duration
    return timed
