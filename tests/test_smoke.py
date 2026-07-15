"""Smoke tests — sin red, validan la lógica pura."""
from __future__ import annotations

from pathlib import Path

from videogen import compose
from videogen.models import VoiceTrack, WordTimestamp
from videogen.script import _slugify


def test_slugify():
    assert _slugify("¿Por qué los pulpos tienen 3 corazones?") == "por-qu-los-pulpos-tienen-3-corazones"
    assert _slugify("") == "video"


def test_caption_ass_generation(tmp_path: Path):
    track = VoiceTrack(
        lang="es",
        audio_path="/tmp/fake.mp3",
        duration_seconds=10.0,
        words=[
            WordTimestamp(word="Los", start=0.0, end=0.3),
            WordTimestamp(word="pulpos", start=0.3, end=0.8),
            WordTimestamp(word="tienen", start=0.8, end=1.2),
            WordTimestamp(word="tres", start=1.2, end=1.6),
            WordTimestamp(word="corazones", start=1.6, end=2.4),
            WordTimestamp(word="azules", start=2.4, end=3.0),
        ],
    )
    out = compose.build_caption_ass(track, tmp_path / "captions.ass", vertical=True)
    text = out.read_text(encoding="utf-8")
    assert "[Script Info]" in text
    assert "PlayResX: 1080" in text
    assert "PlayResY: 1920" in text
    # vertical → chunks de 2 palabras → 6 palabras = 3 chunks
    dialogue_lines = [l for l in text.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogue_lines) == 3
    assert "LOS PULPOS" in dialogue_lines[0]
    assert "TIENEN TRES" in dialogue_lines[1]
    assert "CORAZONES AZULES" in dialogue_lines[2]


def test_time_format():
    assert compose._fmt_time(0) == "0:00:00.00"
    assert compose._fmt_time(65.5) == "0:01:05.50"
    assert compose._fmt_time(3661.25) == "1:01:01.25"
