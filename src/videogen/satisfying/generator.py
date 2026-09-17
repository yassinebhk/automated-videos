"""Generador de vídeos 'satisfying' generativos VARIADOS.

100% procedural (numpy + matplotlib), sin metraje real ni IA de pago → contenido
original (no slop) y GLOBAL (sin idioma). Tipos que rotan (anti-repetición):
- fractal   : zoom infinito Mandelbrot/Julia
- phyllo    : espiral áurea (girasol) que rota — hipnótico
- harmo     : harmonograph (curvas de péndulo tipo Spirograph) que se dibujan
- plasma    : interferencia de ondas que fluye
- sort      : visualización de ordenación (barras) — oddly satisfying

Encode mp4 vía FFMpegWriter (path probado en CI). Música: ranking._add_music_to_video.
"""
from __future__ import annotations

import numpy as np
from datetime import datetime, timezone
from pathlib import Path

from ..config import ROOT

SATISFYING_ROOT = ROOT / "output" / "satisfying_uploaded"
BG = "#08111c"

VARIANTS = [
    # ── fractales ──
    {"key": "seahorse", "gen": "fractal", "kind": "mandelbrot",
     "cx": -0.743643887037151, "cy": 0.13182590420533, "cmap": "twilight_shifted"},
    {"key": "spiral", "gen": "fractal", "kind": "mandelbrot",
     "cx": -0.7778078101, "cy": 0.1316451080, "cmap": "magma"},
    {"key": "minibrot", "gen": "fractal", "kind": "mandelbrot",
     "cx": -1.7687788770, "cy": 0.0017389640, "cmap": "inferno"},
    {"key": "julia_a", "gen": "fractal", "kind": "julia",
     "cx": -0.8, "cy": 0.156, "cmap": "twilight"},
    {"key": "julia_b", "gen": "fractal", "kind": "julia",
     "cx": 0.285, "cy": 0.01, "cmap": "cividis"},
    # ── phyllotaxis (espiral áurea) ──
    {"key": "phyllo_twilight", "gen": "phyllo", "cmap": "twilight"},
    {"key": "phyllo_inferno", "gen": "phyllo", "cmap": "inferno"},
    {"key": "phyllo_ocean", "gen": "phyllo", "cmap": "ocean"},
    # ── harmonograph ──
    {"key": "harmo_teal", "gen": "harmo", "freqs": [2.01, 1.99, 3.01, 2.0], "damp": 0.0040, "color": "#39e0d0"},
    {"key": "harmo_gold", "gen": "harmo", "freqs": [3.02, 2.00, 2.01, 4.00], "damp": 0.0035, "color": "#f5c542"},
    {"key": "harmo_pink", "gen": "harmo", "freqs": [2.02, 3.01, 3.03, 2.00], "damp": 0.0032, "color": "#ff6ec7"},
    # ── plasma ──
    {"key": "plasma_magma", "gen": "plasma", "cmap": "magma"},
    {"key": "plasma_ocean", "gen": "plasma", "cmap": "ocean"},
    # ── sorting ──
    {"key": "sort_viridis", "gen": "sort", "cmap": "viridis"},
    {"key": "sort_turbo", "gen": "sort", "cmap": "turbo"},
]


# ───────────────────────────── fractal ─────────────────────────────
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
    if variant.get("kind") == "mandelbrot":
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


def _writer(fps):
    import matplotlib.animation as manim
    return manim.FFMpegWriter(fps=fps, bitrate=3500, codec="libx264",
                              extra_args=["-pix_fmt", "yuv420p"])


def _fig(w, h):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_facecolor(BG); ax.axis("off")
    return plt, fig, ax


def _save(anim, out_video, fps):
    out_video.parent.mkdir(parents=True, exist_ok=True)
    try:
        anim.save(str(out_video), writer=_writer(fps))
        return out_video
    except Exception as e:
        print(f"  satisfying: render fail: {e}")
        return None


def render_fractal_zoom(variant, out_video, seconds=30, fps=15, w=720, h=1280):
    import matplotlib.animation as manim
    plt, fig, ax = _fig(w, h)
    n = max(1, seconds * fps)
    base = 3.0 if variant.get("kind") == "mandelbrot" else 3.2
    deep = base * (1e-4 if variant.get("kind") == "mandelbrot" else 0.12)

    def draw(fi):
        t = fi / max(1, n - 1)
        norm = render_frame(variant, base * (deep / base) ** t, w, h, int(150 + 350 * t))
        ax.clear(); ax.axis("off")
        ax.imshow(norm, cmap=variant["cmap"], origin="lower")

    anim = manim.FuncAnimation(fig, draw, frames=n, interval=1000 // fps)
    r = _save(anim, out_video, fps); plt.close(fig); return r


# ───────────────────────────── phyllotaxis ─────────────────────────────
def render_phyllotaxis(variant, out_video, seconds=30, fps=15, w=720, h=1280):
    import matplotlib.animation as manim
    plt, fig, ax = _fig(w, h)
    ax.set_aspect("equal")
    npts = 2600
    idx = np.arange(npts)
    golden = np.pi * (3 - np.sqrt(5))
    r = np.sqrt(idx)
    lim = r.max() * 1.05
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim * h / w, lim * h / w)
    scat = ax.scatter(np.zeros(npts), np.zeros(npts), c=np.zeros(npts),
                      cmap=variant.get("cmap", "twilight"), s=16)
    n = max(1, seconds * fps)

    def draw(fi):
        theta = idx * golden + 2 * np.pi * fi / n
        scat.set_offsets(np.column_stack([r * np.cos(theta), r * np.sin(theta)]))
        scat.set_array(theta % (2 * np.pi))
        return scat,

    anim = manim.FuncAnimation(fig, draw, frames=n, interval=1000 // fps, blit=False)
    res = _save(anim, out_video, fps); plt.close(fig); return res


# ───────────────────────────── harmonograph ─────────────────────────────
def render_harmonograph(variant, out_video, seconds=30, fps=15, w=720, h=1280):
    import matplotlib.animation as manim
    plt, fig, ax = _fig(w, h)
    ax.set_aspect("equal")
    t = np.linspace(0, 50, 14000)
    f = variant.get("freqs", [2.01, 1.99, 3.01, 2.0])
    d = variant.get("damp", 0.004)
    hx = np.sin(f[0] * t + 0.3) * np.exp(-d * t) + 0.7 * np.sin(f[1] * t + 1.2) * np.exp(-d * t)
    hy = np.sin(f[2] * t + 0.9) * np.exp(-d * t) + 0.7 * np.sin(f[3] * t + 2.4) * np.exp(-d * t)
    L = max(np.abs(hx).max(), np.abs(hy).max()) * 1.1
    ax.set_xlim(-L, L); ax.set_ylim(-L * h / w, L * h / w)
    line, = ax.plot([], [], color=variant.get("color", "#39e0d0"), lw=0.9, alpha=0.9)
    n = max(1, seconds * fps)

    def draw(fi):
        k = int(len(t) * (fi + 1) / n)
        line.set_data(hx[:k], hy[:k])
        return line,

    anim = manim.FuncAnimation(fig, draw, frames=n, interval=1000 // fps, blit=False)
    res = _save(anim, out_video, fps); plt.close(fig); return res


# ───────────────────────────── plasma ─────────────────────────────
def render_plasma(variant, out_video, seconds=30, fps=15, w=720, h=1280):
    import matplotlib.animation as manim
    plt, fig, ax = _fig(w, h)
    w2, h2 = int(w * 0.34), int(h * 0.34)
    xs = np.linspace(0, 8, w2); ys = np.linspace(0, 14, h2)
    X, Y = np.meshgrid(xs, ys)
    R = np.sqrt(X ** 2 + Y ** 2)
    im = ax.imshow(np.zeros((h2, w2)), cmap=variant.get("cmap", "magma"),
                   origin="lower", aspect="auto", vmin=-4, vmax=4)
    n = max(1, seconds * fps)

    def draw(fi):
        ph = 2 * np.pi * 2 * fi / n
        p = (np.sin(X + ph) + np.sin(Y * 0.9 - ph)
             + np.sin((X + Y) * 0.7 + ph) + np.sin(R * 1.2 - ph * 2))
        im.set_data(p)
        return im,

    anim = manim.FuncAnimation(fig, draw, frames=n, interval=1000 // fps, blit=False)
    res = _save(anim, out_video, fps); plt.close(fig); return res


# ───────────────────────────── sorting ─────────────────────────────
def _sort_states(nbars=64, seed=None):
    rng = np.random.default_rng(seed)
    a = np.arange(1, nbars + 1)
    rng.shuffle(a)
    states = [a.copy()]
    b = a.copy()
    for i in range(nbars - 1):  # selection sort
        m = i
        for j in range(i + 1, nbars):
            if b[j] < b[m]:
                m = j
        if m != i:
            b[i], b[m] = b[m], b[i]
        states.append(b.copy())
    return states


def render_sorting(variant, out_video, seconds=30, fps=15, w=720, h=1280):
    import matplotlib.animation as manim
    plt, fig, ax = _fig(w, h)
    cmap = plt.get_cmap(variant.get("cmap", "viridis"))
    N = 64
    states = _sort_states(N)
    ax.set_xlim(-1, N); ax.set_ylim(0, N + 2)
    bars = ax.bar(range(N), states[0], width=0.92,
                  color=[cmap(v / N) for v in states[0]])
    n = max(1, seconds * fps)

    def draw(fi):
        st = states[min(int(len(states) * fi / n), len(states) - 1)]
        for bar, v in zip(bars, st):
            bar.set_height(v); bar.set_color(cmap(v / N))
        return bars

    anim = manim.FuncAnimation(fig, draw, frames=n, interval=1000 // fps, blit=False)
    res = _save(anim, out_video, fps); plt.close(fig); return res


RENDERERS = {
    "fractal": render_fractal_zoom, "phyllo": render_phyllotaxis,
    "harmo": render_harmonograph, "plasma": render_plasma, "sort": render_sorting,
}

GEN_META = {
    "fractal": ("Satisfying Infinite Fractal Zoom", ["fractal", "zoom", "mandelbrot"]),
    "phyllo": ("Hypnotic Golden Spiral", ["spiral", "hypnotic", "phyllotaxis"]),
    "harmo": ("Mesmerizing Harmonograph Art", ["harmonograph", "spirograph", "hypnotic"]),
    "plasma": ("Flowing Plasma Waves", ["plasma", "abstract", "hypnotic"]),
    "sort": ("Oddly Satisfying Sorting", ["sorting", "algorithm", "coding"]),
}


def save_sample_frame(variant_key: str, out_png: Path, w: int = 720, h: int = 1280) -> Path:
    """1 frame a PNG (sin ffmpeg) para verificar calidad de cualquier tipo."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    v = next((x for x in VARIANTS if x["key"] == variant_key), VARIANTS[0])
    gen = v.get("gen", "fractal")
    plt2, fig, ax = _fig(w, h)
    if gen == "fractal":
        norm = render_frame(v, (3.0 if v.get("kind") == "mandelbrot" else 3.2) * 0.02, w, h, 400)
        ax.imshow(norm, cmap=v["cmap"], origin="lower")
    elif gen == "phyllo":
        idx = np.arange(2600); g = np.pi * (3 - np.sqrt(5)); r = np.sqrt(idx); th = idx * g + 1.0
        lim = r.max() * 1.05; ax.set_aspect("equal"); ax.set_xlim(-lim, lim); ax.set_ylim(-lim * h / w, lim * h / w)
        ax.scatter(r * np.cos(th), r * np.sin(th), c=th % (2 * np.pi), cmap=v.get("cmap", "twilight"), s=16)
    elif gen == "harmo":
        t = np.linspace(0, 50, 14000); f = v.get("freqs", [2.01, 1.99, 3.01, 2.0]); d = v.get("damp", 0.004)
        hx = np.sin(f[0]*t+0.3)*np.exp(-d*t)+0.7*np.sin(f[1]*t+1.2)*np.exp(-d*t)
        hy = np.sin(f[2]*t+0.9)*np.exp(-d*t)+0.7*np.sin(f[3]*t+2.4)*np.exp(-d*t)
        L = max(np.abs(hx).max(), np.abs(hy).max())*1.1; ax.set_aspect("equal")
        ax.set_xlim(-L, L); ax.set_ylim(-L*h/w, L*h/w); ax.plot(hx, hy, color=v.get("color", "#39e0d0"), lw=0.9)
    elif gen == "plasma":
        w2, h2 = int(w*0.34), int(h*0.34); X, Y = np.meshgrid(np.linspace(0, 8, w2), np.linspace(0, 14, h2))
        R = np.sqrt(X**2+Y**2); ph = 1.3
        p = np.sin(X+ph)+np.sin(Y*0.9-ph)+np.sin((X+Y)*0.7+ph)+np.sin(R*1.2-ph*2)
        ax.imshow(p, cmap=v.get("cmap", "magma"), origin="lower", aspect="auto")
    elif gen == "sort":
        st = _sort_states(64)[32]; cmap = plt.get_cmap(v.get("cmap", "viridis"))
        ax.set_xlim(-1, 64); ax.set_ylim(0, 66); ax.bar(range(64), st, width=0.92, color=[cmap(x/64) for x in st])
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_png), dpi=100, facecolor=BG); plt2.close(fig)
    return out_png


def generate_satisfying_video(out_dir: Path, variant: dict, seconds: int = 30) -> dict | None:
    gen = variant.get("gen", "fractal")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"{gen}_{variant['key']}_{ts}"
    work = out_dir / slug
    work.mkdir(parents=True, exist_ok=True)
    raw = RENDERERS.get(gen, render_fractal_zoom)(variant, work / "vid.mp4", seconds=seconds)
    if not raw:
        return None
    try:
        from ..ranking.generator import _add_music_to_video
        final = _add_music_to_video(raw, work, seconds) or raw
    except Exception as e:
        print(f"  satisfying: music skip ({e})")
        final = raw
    title, extra = GEN_META.get(gen, GEN_META["fractal"])
    tags = ["satisfying", "oddlysatisfying", "relaxing", "hypnotic"] + extra
    return {
        "slug": slug, "variant": variant["key"], "video_path": str(final),
        "title": f"{title} #satisfying #shorts"[:100],
        "description": (
            f"{title}. Procedurally generated in real time — no two videos are the same.\n\n"
            f"#satisfying #oddlysatisfying #relaxing #hypnotic #{gen} #mathart #shorts"
        ),
        "tags": tags,
    }
