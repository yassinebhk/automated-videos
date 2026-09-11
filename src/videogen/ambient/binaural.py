"""Generador de audio binaural para MenteEnCalma.

Sintetiza tonos puros con ffmpeg (sin librerías Python extra pesadas).
- Carrier freq: portadora audible (100-300 Hz)
- Beat freq: diferencia entre L/R que el cerebro percibe (2-40 Hz)
  - Delta 0.5-4 Hz → sueño profundo
  - Theta 4-8 Hz → meditación, dormir
  - Alpha 8-12 Hz → relajación, focus ligero
  - Beta 12-30 Hz → alerta, concentración activa
  - Gamma >30 Hz → memoria, alto rendimiento

Se usa auditivamente con AURICULARES obligatorio (nota en descripción).
NO claims médicos (política de veracidad).
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def generate_binaural(
    dest: Path,
    duration_seconds: int,
    carrier_hz: int = 200,
    beat_hz: int = 8,
    volume: float = 0.3,
) -> Path | None:
    """Genera un WAV binaural con ffmpeg.

    Left channel = carrier_hz
    Right channel = carrier_hz + beat_hz
    Beat percibido = beat_hz (solo con auriculares).

    Volumen bajo (0.3) para no fatigar tras 30-60 min.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    left = carrier_hz
    right = carrier_hz + beat_hz
    # Filter graph: 2 sinusoidales + amerge en stereo
    filt = (
        f"[0:a]volume={volume}[l];"
        f"[1:a]volume={volume}[r];"
        f"[l][r]amerge=inputs=2[a]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency={left}:duration={duration_seconds}",
        "-f", "lavfi", "-i", f"sine=frequency={right}:duration={duration_seconds}",
        "-filter_complex", filt,
        "-map", "[a]",
        "-c:a", "aac", "-b:a", "192k",
        str(dest),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"  binaural ffmpeg fail: {r.stderr[-400:]}")
        return None
    return dest if dest.exists() else None
