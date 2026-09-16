"""Renderer v2 de pista de pádel — perspectiva 2.5D (PIL), 4 jugadores, bola con
estela/sombra, hook y subtítulos grandes. Frame-a-frame → ffmpeg (path CI).

Coordenadas de pista en metros: x∈[0,10] (ancho), y∈[0,20] (largo; y=0 borde
cercano, y=20 fondo lejano). Red en y=10. SIEMPRE 4 jugadores (2 por pareja).
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
CX = W / 2
NEAR_Y, FAR_Y = 1060, 300
NEAR_HW, FAR_HW = 340, 150
BALL_C = (232, 255, 42)
RED = (230, 60, 60)
ORA = (255, 170, 20)


def proj(xc: float, yc: float) -> tuple[float, float]:
    depth = yc / 20.0
    sy = NEAR_Y + (FAR_Y - NEAR_Y) * depth
    hw = NEAR_HW + (FAR_HW - NEAR_HW) * depth
    sx = CX + (xc - 5) / 5.0 * hw
    return (sx, sy)


def scale_at(yc: float) -> float:
    return 1 - 0.55 * (yc / 20.0)


def _font(sz: int):
    for p in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/Library/Fonts/Arial.ttf"]:
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            continue
    return ImageFont.load_default()


def _bg(d: ImageDraw.ImageDraw):
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(12 + 18 * t), int(22 + 30 * t), int(34 + 44 * t)))


def _court(d: ImageDraw.ImageDraw):
    d.polygon([proj(0, 0), proj(10, 0), proj(10, 20), proj(0, 20)], fill=(28, 108, 140))

    def ln(x0, y0, x1, y1, wd=3, col=(240, 240, 240, 235)):
        d.line([proj(x0, y0), proj(x1, y1)], fill=col, width=wd)
    ln(0, 10, 10, 10, 4)
    ln(0, 3, 10, 3, 2); ln(0, 17, 10, 17, 2)
    ln(5, 3, 5, 17, 2)
    # pared de cristal fondo (panel semitransparente) + laterales
    top = proj(0, 20)[1]
    d.polygon([proj(0, 20), proj(10, 20), (proj(10, 20)[0], top - 70), (proj(0, 20)[0], top - 70)],
              fill=(160, 216, 232, 70))
    d.line([proj(0, 0), proj(0, 20)], fill=(180, 225, 240, 150), width=4)
    d.line([proj(10, 0), proj(10, 20)], fill=(180, 225, 240, 150), width=4)
    for xx in (0, 10):
        px, py = proj(xx, 10)
        d.line([(px, py), (px, py - 46 * scale_at(10))], fill=(235, 235, 235, 230), width=4)


def _player(d, xc, yc, color):
    s = scale_at(yc)
    px, py = proj(xc, yc)
    d.ellipse([px - 26 * s, py - 8 * s, px + 26 * s, py + 8 * s], fill=(0, 0, 0, 90))
    d.ellipse([px - 16 * s, py - 60 * s, px + 16 * s, py - 20 * s], fill=color)
    d.ellipse([px - 12 * s, py - 84 * s, px + 12 * s, py - 60 * s], fill=(255, 224, 189))
    d.line([(px + 13 * s, py - 44 * s), (px + 32 * s, py - 54 * s)], fill=(30, 30, 30), width=max(2, int(5 * s)))
    d.ellipse([px + 28 * s, py - 63 * s, px + 43 * s, py - 48 * s], outline=(30, 30, 30), width=max(2, int(3 * s)))


def _ball(d, xc, yc, trail=None):
    s = scale_at(yc)
    bx, by = proj(xc, yc)
    if trail and len(trail) > 1:
        d.line([proj(x, y) for (x, y) in trail], fill=(232, 255, 42, 150), width=4)
    d.ellipse([bx - 10 * s, by + 6 * s, bx + 10 * s, by + 12 * s], fill=(0, 0, 0, 80))
    d.ellipse([bx - 9 * s, by - 9 * s, bx + 9 * s, by + 9 * s], fill=BALL_C, outline=(20, 20, 20), width=2)


def _wrap(d, text, font, maxw):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textbbox((0, 0), t, font=font)[2] <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def render_frame(hook: str, caption: str, ball_xy, players, trail=None) -> Image.Image:
    img = Image.new("RGB", (W, H), (12, 20, 30))
    d = ImageDraw.Draw(img, "RGBA")
    _bg(d); _court(d)
    for (px, py, col) in players:
        _player(d, px, py, col)
    if ball_xy:
        _ball(d, ball_xy[0], ball_xy[1], trail)
    # hook (arriba)
    if hook:
        fh = _font(50)
        d.rectangle([0, 60, W, 180], fill=(0, 0, 0, 120))
        for i, ln in enumerate(_wrap(d, hook, fh, W - 60)[:2]):
            tw = d.textbbox((0, 0), ln, font=fh)[2]
            d.text(((W - tw) // 2, 78 + i * 56), ln, font=fh, fill=(255, 255, 255))
    # subtítulo (banda inferior)
    if caption:
        fc = _font(46)
        lines = _wrap(d, caption, fc, W - 70)[:2]
        bh = 66 * len(lines) + 30
        d.rectangle([0, H - 150 - bh, W, H - 120], fill=(0, 0, 0, 175))
        for i, ln in enumerate(lines):
            cw = d.textbbox((0, 0), ln, font=fc)[2]
            d.text(((W - cw) // 2, H - 140 - bh + i * 62), ln, font=fc, fill=(255, 230, 60))
    # marca (bola dibujada, no emoji)
    d.ellipse([38, H - 96, 66, H - 68], fill=BALL_C, outline=(20, 20, 20), width=2)
    d.text((78, H - 96), "Padel Pro", font=_font(30), fill=(255, 255, 255))
    return img


def save_sample(out_png: Path) -> Path:
    players = [(3.2, 2.4, RED), (6.8, 3.2, RED), (3.6, 15.5, ORA), (6.4, 16.2, ORA)]
    trail = [(6.6, 3.2), (5.8, 6.0), (5.2, 8.5)]
    img = render_frame("Getting passed at the net?", "The lob wins the net back", (5.2, 8.5), players, trail)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_png))
    return out_png


def _interp(wp, t):
    if not wp:
        return (5.0, 10.0)
    if len(wp) == 1:
        return wp[0]
    seg = t * (len(wp) - 1)
    i = min(int(seg), len(wp) - 2)
    f = seg - i
    (x0, y0), (x1, y1) = wp[i], wp[i + 1]
    return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)


def render_play_video(play: dict, hook: str, caption_timeline, out_mp4: Path,
                      duration: float, fps: int = 15, hook_secs: float = 2.5) -> Path | None:
    """Frames PIL (bola animada + subtítulos por tiempo) → ffmpeg image2 → mp4 mudo."""
    import subprocess, tempfile, shutil
    ball_wp = play.get("ball", [])
    players = [(x, y, (RED if y < 10 else ORA)) for (x, y) in play.get("players", [])]
    n = max(1, int(duration * fps))
    tmp = Path(tempfile.mkdtemp(prefix="padel_"))
    try:
        for fi in range(n):
            t = fi / fps
            prog = min(1.0, t / max(0.1, duration))
            bxy = _interp(ball_wp, prog) if ball_wp else None
            trail = [_interp(ball_wp, max(0.0, prog - k * 0.03)) for k in range(8)] if ball_wp else None
            cap = ""
            for (start, txt) in caption_timeline:
                if t >= start:
                    cap = txt
                else:
                    break
            hk = hook if t < hook_secs else ""
            render_frame(hk, cap, bxy, players, trail).save(str(tmp / f"f_{fi:05d}.png"))
        cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", str(tmp / "f_%05d.png"),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), str(out_mp4)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return out_mp4 if (r.returncode == 0 and out_mp4.exists()) else None
    except Exception as e:
        print(f"  padel: render_play_video fail: {e}")
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
