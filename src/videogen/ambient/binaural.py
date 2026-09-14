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
    wave: str = "binaural",
) -> Path | None:
    """Genera audio con ffmpeg. Soporta:

    - wave='binaural' (default) o alpha/beta/theta/delta/gamma/solfeggio:
      sinusoidal binaural o mono según carrier_hz.
    - wave='noise_white': ruido blanco (uniforme, alta frecuencia).
    - wave='noise_pink': ruido rosa (mid-freq, natural para estudio).
    - wave='noise_brown': ruido marrón (grave, ideal dormir/TDAH).

    Los noise usan `anoisesrc` de ffmpeg, no dependen de carrier_hz.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    if wave.startswith("noise_"):
        color = wave.replace("noise_", "")  # white/pink/brown
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anoisesrc=color={color}:amplitude={volume}:duration={duration_seconds}",
            "-c:a", "aac", "-b:a", "192k",
            "-af", (f"afade=t=in:st=0:d=3,"
                    f"afade=t=out:st={duration_seconds-3}:d=3"),
            str(dest),
        ]
    else:
        # Binaural / solfeggio: 2 canales sinusoidales
        left = carrier_hz
        right = carrier_hz + beat_hz
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
    # Timeout 15min: para 8h binaurales/noise, ffmpeg lavfi tarda 3-5min
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        print(f"  binaural/noise ffmpeg fail: {r.stderr[-400:]}")
        return None
    return dest if dest.exists() else None
