"""Generador de vídeos 'satisfying' generativos (fractal zoom infinito).

100% procedural (numpy + matplotlib), SIN metraje real ni IA de pago → contenido
original (no slop, no stock) y GLOBAL (sin idioma). Reusa el mezclador de música
de ranking.generator._add_music_to_video. Encode mp4 vía FFMpegWriter (path CI).
"""
from __future__ import annotations

import numpy as np
from datetime import datetime, timezone
from pathlib import Path

from ..config import ROOT

SATISFYING_ROOT = ROOT / "output" / "satisfying_uploaded"

VARIANTS = [
    {"key": "seahorse", "kind": "mandelbrot",
     "cx": -0.743643887037151, "cy": 0.13182590420533, "cmap": "twilight_shifted"},
    {"key": "spiral", "kind": "mandelbrot",
     "cx": -0.7778078101, "cy": 0.1316451080, "cmap": "magma"},
    {"key": "minibrot", "kind": "mandelbrot",
     "cx": -1.7687788770, "cy": 0.0017389640, "cmap": "inferno"},
    {"key": "julia_a", "kind": "julia",
     "cx": -0.8, "cy": 0.156, "cmap": "twilight"},
    {"key": "julia_b", "kind": "julia",
     "cx": 0.285, "cy": 0.01, "cmap": "cividis"},
]


def _escape_smooth(Cc, Z, max_iter: int) -> np.ndarray:
    nu = np.zeros(Z.shape, dtype=float)
    alive = np.ones(Z.shape, dtype=bool)
    cc_is_array = np.ndim(Cc) > 0
    for i in range(max_iter):
        add = Cc[alive] if cc_is_array else Cc
        Z[alive] = Z[alive] * Z[alive] + add
        mag = np.abs(Z)
        esc = alive & (mag > 2.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            nu[esc] = i + 1 - np.log(np.log(mag[esc])) / np.log(2)
        alive[esc] = False
    nu[alive] = max_iter
    return nu


def render_frame(variant: dict, scale: float, w: int, h: int, max_iter: int) -> np.ndarray:
    aspect = h / w
    if variant["kind"] == "mandelbrot":
        cx, cy = variant["cx"], variant["cy"]
        xs = np.linspace(cx - scale / 2, cx + scale / 2, w)
        ys = np.linspace(cy - scale * aspect / 2, cy + scale * aspect / 2, h)
        X, Y = np.meshgrid(xs, ys)
        C = (X + 1j * Y).astype(np.complex128)
        nu = _escape_smooth(C, np.zeros_like(C), max_iter)
    else:
        xs = np.linspace(-scale / 2, scale / 2, w)
        ys = np.linspace(-scale * aspect / 2, scale * aspect / 2, h)
        X, Y = np.meshgrid(xs, ys)
        Z = (X + 1j * Y).astype(np.complex128)
        Cc = np.complex128(complex(variant["cx"], variant["cy"]))
        nu = _escape_smooth(Cc, Z, max_iter)
    nu = np.nan_to_num(nu, nan=max_iter, posinf=max_iter, neginf=0.0)
    return (nu / max_iter) ** 0.5


def save_sample_frame(variant_key: str, out_png: Path, w: int = 720, h: int = 1280,
                      zoom: float = 0.02) -> Path:
    """1 frame a PNG (sin ffmpeg) para verificar calidad."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    v = next((x for x in VARIANTS if x["key"] == variant_key), VARIANTS[0])
    base = 3.0 if v["kind"] == "mandelbrot" else 3.2
    norm = render_frame(v, base * zoom, w, h, max_iter=400)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.imshow(norm, cmap=v["cmap"], origin="lower")
    fig.savefig(str(out_png), dpi=100)
    plt.close(fig)
    return out_png


def render_fractal_zoom(variant: dict, out_video: Path, seconds: int = 30,
                        fps: int = 15, w: int = 720, h: int = 1280) -> Path | None:
    """Zoom fractal → mp4 vertical. Mismo path FFMpegWriter que ranking (probado CI)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.animation as manim

    n_frames = max(1, seconds * fps)
    base = 3.0 if variant["kind"] == "mandelbrot" else 3.2
    deep = base * (1e-4 if variant["kind"] == "mandelbrot" else 0.12)

    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")

    def draw(fi: int):
        t = fi / max(1, n_frames - 1)
        scale = base * (deep / base) ** t
        max_iter = int(150 + 350 * t)
        norm = render_frame(variant, scale, w, h, max_iter)
        ax.clear(); ax.axis("off")
        ax.imshow(norm, cmap=variant["cmap"], origin="lower")

    anim = manim.FuncAnimation(fig, draw, frames=n_frames, interval=1000 // fps)
    out_video.parent.mkdir(parents=True, exist_ok=True)
    writer = manim.FFMpegWriter(fps=fps, bitrate=3500, codec="libx264",
                                extra_args=["-pix_fmt", "yuv420p"])
    try:
        anim.save(str(out_video), writer=writer)
        plt.close(fig)
        return out_video
    except Exception as e:
        print(f"  satisfying: render fail: {e}")
        plt.close(fig)
        return None


def generate_satisfying_video(out_dir: Path, variant: dict, seconds: int = 30) -> dict | None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"fractal_{variant['key']}_{ts}"
    work = out_dir / slug
    work.mkdir(parents=True, exist_ok=True)
    raw = render_fractal_zoom(variant, work / "fractal.mp4", seconds=seconds)
    if not raw:
        return None
    try:
        from ..ranking.generator import _add_music_to_video
        final = _add_music_to_video(raw, work, seconds) or raw
    except Exception as e:
        print(f"  satisfying: music skip ({e})")
        final = raw
    name = variant["key"].replace("_", " ").title()
    return {
        "slug": slug,
        "variant": variant["key"],
        "video_path": str(final),
        "title": f"Satisfying Infinite Fractal Zoom 🌀 #{name.replace(' ', '')} #shorts"[:100],
        "description": (
            "Relax with an infinite fractal zoom. 🌀\n\n"
            "Procedurally generated in real time (Mandelbrot & Julia sets) — "
            "no two videos are the same.\n\n"
            "#satisfying #fractal #oddlysatisfying #relaxing #zoom #mathart #shorts"
        ),
        "tags": ["satisfying", "fractal", "oddlysatisfying", "relaxing", "zoom", "mathart"],
    }
