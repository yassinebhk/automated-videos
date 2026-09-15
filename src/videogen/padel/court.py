"""Pista de pádel (vista cenital 9:16) + animación de jugada. 100% matplotlib."""
from __future__ import annotations

import numpy as np
from pathlib import Path

L, W = 20.0, 10.0
SERVICE_FROM_BACK = 3.0
NET_Y = L / 2
COURT_BLUE = "#1e6f8e"; LINE = "#f5f5f5"; WALL = "#9fd8e8"; BG = "#0b1e26"
BALL = "#e8ff2a"; P_LEFT = "#ff5252"; P_RIGHT = "#ffb300"


def _rect(x, y, w, h, color, zorder=1):
    import matplotlib.patches as patches
    return patches.Rectangle((x, y), w, h, facecolor=color, edgecolor="none", zorder=zorder)


def _draw_court(ax):
    ax.set_facecolor(BG)
    ax.add_patch(_rect(0, 0, W, L, COURT_BLUE, zorder=1))
    for (x0, y0, x1, y1) in [(0, 0, W, 0), (0, L, W, L), (0, 0, 0, L), (W, 0, W, L)]:
        ax.plot([x0, x1], [y0, y1], color=WALL, lw=6, zorder=3, solid_capstyle="round")
    ax.plot([0, W], [NET_Y, NET_Y], color=LINE, lw=3, zorder=4, dashes=(2, 2))
    for y in (SERVICE_FROM_BACK, L - SERVICE_FROM_BACK):
        ax.plot([0, W], [y, y], color=LINE, lw=2, zorder=4)
    ax.plot([W / 2, W / 2], [SERVICE_FROM_BACK, L - SERVICE_FROM_BACK], color=LINE, lw=2, zorder=4)
    ax.set_xlim(-1, W + 1); ax.set_ylim(-1.5, L + 2.2)
    ax.set_aspect("equal"); ax.axis("off")


def _interp(wp, t):
    if len(wp) == 1:
        return wp[0]
    seg = t * (len(wp) - 1)
    i = min(int(seg), len(wp) - 2)
    f = seg - i
    (x0, y0), (x1, y1) = wp[i], wp[i + 1]
    return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)


def save_sample_court(out_png: Path, ball_xy=(5.0, 14.0),
                      players=((3.0, 2.5), (7.0, 3.5), (3.5, 17.0), (6.5, 17.5))) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(7.2, 12.8), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); _draw_court(ax)
    for (px, py) in players:
        ax.scatter([px], [py], s=520, c=(P_LEFT if py < NET_Y else P_RIGHT),
                   edgecolors="white", linewidths=2, zorder=5)
    ax.scatter([ball_xy[0]], [ball_xy[1]], s=180, c=BALL, edgecolors="black", linewidths=1.5, zorder=6)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_png), dpi=100, facecolor=BG); plt.close(fig)
    return out_png


def render_play_animation(play: dict, title: str, out_video: Path, duration: float,
                          fps: int = 15, w: int = 720, h: int = 1280) -> Path | None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.animation as manim
    ball_wp = play["ball"]; players = play.get("players", [])
    n_frames = max(1, int(duration * fps))
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])

    def draw(fi: int):
        ax.clear(); _draw_court(ax)
        ax.text(W / 2, L + 1.2, title, ha="center", va="center", color="white",
                fontsize=14, fontweight="bold", zorder=7)
        for (px, py) in players:
            ax.scatter([px], [py], s=460, c=(P_LEFT if py < NET_Y else P_RIGHT),
                       edgecolors="white", linewidths=2, zorder=5)
        t = fi / max(1, n_frames - 1)
        trail = [_interp(ball_wp, max(0.0, t - k * 0.035)) for k in range(8)]
        ax.plot([p[0] for p in trail], [p[1] for p in trail], color=BALL, lw=2, alpha=0.4, zorder=5)
        bx, by = _interp(ball_wp, t)
        ax.scatter([bx], [by], s=190, c=BALL, edgecolors="black", linewidths=1.5, zorder=6)

    anim = manim.FuncAnimation(fig, draw, frames=n_frames, interval=1000 // fps)
    out_video.parent.mkdir(parents=True, exist_ok=True)
    writer = manim.FFMpegWriter(fps=fps, bitrate=2800, codec="libx264", extra_args=["-pix_fmt", "yuv420p"])
    try:
        anim.save(str(out_video), writer=writer); plt.close(fig); return out_video
    except Exception as e:
        print(f"  padel: anim render fail: {e}"); plt.close(fig); return None
