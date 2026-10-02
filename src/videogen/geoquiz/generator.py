"""Generador de vídeo GeoQuiz (EN) — "guess the country by its flag".

Sin voz (música + texto en pantalla → esquiva la limitación del TTS). Frames con
PIL (1080x1920) → concat con ffmpeg → música (helper de ranking). Banderas desde
flagcdn.com (dominio público). 5 rondas: bandera + cuenta atrás 3-2-1 → reveal
país + capital. Cierre con CTA "comment your score". Ver [[tanda-canales-02-10]].
"""
from __future__ import annotations

import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config import ROOT

W, H = 1080, 1920
BG = (14, 23, 38)          # navy oscuro
ACCENT = (57, 224, 208)    # turquesa
GOLD = (245, 197, 66)
WHITE = (240, 244, 248)
MUTED = (150, 165, 185)
FONT_PATH = ROOT / "assets" / "fonts" / "Montserrat.ttf"
FLAG_CACHE = ROOT / "output" / "geoquiz_assets" / "flags"


def _font(size: int):
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except Exception:
        return ImageFont.load_default()


def _text_center(draw, cx, y, text, font, fill, max_w=None):
    """Dibuja texto centrado horizontalmente en cx. Devuelve alto usado."""
    lines = [text]
    if max_w:
        words = text.split()
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if draw.textlength(test, font=font) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
    yy = y
    asc, desc = font.getmetrics()
    lh = asc + desc + 8
    for ln in lines:
        wline = draw.textlength(ln, font=font)
        draw.text((cx - wline / 2, yy), ln, font=font, fill=fill)
        yy += lh
    return yy - y


def _base() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # viñeta sutil arriba/abajo
    for i in range(220):
        a = int(40 * (1 - i / 220))
        d.line([(0, i), (W, i)], fill=(BG[0] + a // 6, BG[1] + a // 6, BG[2] + a // 5))
    return img


def _paste_flag(img: Image.Image, flag: Path, cy: int) -> None:
    try:
        fl = Image.open(flag).convert("RGB")
    except Exception:
        return
    fw = 780
    fh = int(fl.height * (fw / fl.width))
    fh = min(fh, 560)
    fw = int(fl.width * (fh / fl.height))
    fl = fl.resize((fw, fh), Image.LANCZOS)
    x = (W - fw) // 2
    y = cy - fh // 2
    # marco blanco
    d = ImageDraw.Draw(img)
    d.rectangle([x - 8, y - 8, x + fw + 8, y + fh + 8], fill=WHITE)
    img.paste(fl, (x, y))


def _frame_intro(path: Path) -> None:
    img = _base()
    d = ImageDraw.Draw(img)
    _text_center(d, W // 2, 470, "GUESS THE", _font(120), WHITE)
    _text_center(d, W // 2, 610, "COUNTRY", _font(170), ACCENT)
    _text_center(d, W // 2, 850, "by its flag", _font(78), MUTED)
    _text_center(d, W // 2, 1150, "Only 1% score 5/5", _font(84), GOLD, max_w=900)
    _text_center(d, W // 2, 1480, "Comment your score below", _font(60), MUTED, max_w=900)
    img.save(path)


def _frame_round(path: Path, flag: Path, rnd: int, total: int, number: int) -> None:
    img = _base()
    d = ImageDraw.Draw(img)
    _text_center(d, W // 2, 230, f"ROUND {rnd}/{total}", _font(76), ACCENT)
    _paste_flag(img, flag, 900)
    # círculo cuenta atrás
    cx, cy, r = W // 2, 1420, 120
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=GOLD, width=10)
    num = str(number)
    f = _font(150)
    wnum = d.textlength(num, font=f)
    asc, desc = f.getmetrics()
    d.text((cx - wnum / 2, cy - (asc + desc) / 2), num, font=f, fill=WHITE)
    _text_center(d, W // 2, 1620, "Name it!", _font(60), MUTED)
    img.save(path)


def _frame_reveal(path: Path, flag: Path, rnd: int, total: int, name: str, capital: str) -> None:
    img = _base()
    d = ImageDraw.Draw(img)
    _text_center(d, W // 2, 230, f"ROUND {rnd}/{total}", _font(76), MUTED)
    _paste_flag(img, flag, 820)
    _text_center(d, W // 2, 1230, name, _font(104), ACCENT, max_w=980)
    _text_center(d, W // 2, 1470, f"Capital: {capital}", _font(66), WHITE, max_w=980)
    img.save(path)


def _frame_outro(path: Path) -> None:
    img = _base()
    d = ImageDraw.Draw(img)
    _text_center(d, W // 2, 560, "How many", _font(120), WHITE)
    _text_center(d, W // 2, 700, "did you get?", _font(120), ACCENT)
    _text_center(d, W // 2, 1050, "Comment your score", _font(80), GOLD, max_w=940)
    _text_center(d, W // 2, 1420, "Follow for more geo quizzes", _font(62), MUTED, max_w=940)
    img.save(path)


def _download_flag(iso2: str, dest: Path) -> Path | None:
    from .data import flag_url
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(flag_url(iso2), headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=20).read()
        if len(data) < 1000:
            return None
        dest.write_bytes(data)
        return dest
    except Exception as e:
        print(f"  geoquiz: flag {iso2} fail ({type(e).__name__})")
        return None


def generate_geoquiz(out_dir: Path, candidates: list[tuple], n_rounds: int = 5) -> dict | None:
    """candidates: lista de (iso2, name, capital, tier). Usa los primeros n_rounds
    cuyas banderas descarguen OK. Devuelve meta o None."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"geoquiz_{ts}"
    work = out_dir / slug
    work.mkdir(parents=True, exist_ok=True)

    chosen: list[tuple] = []
    for iso2, name, capital, tier in candidates:
        fp = _download_flag(iso2, FLAG_CACHE / f"{iso2}.png")
        if fp:
            chosen.append((iso2, name, capital, fp))
        if len(chosen) >= n_rounds:
            break
    if len(chosen) < n_rounds:
        print(f"  geoquiz: solo {len(chosen)} banderas OK (<{n_rounds}) — abort")
        return None

    # construir frames + lista concat (duraciones en segundos)
    frames: list[tuple[Path, float]] = []
    intro = work / "f_intro.png"; _frame_intro(intro); frames.append((intro, 2.6))
    for i, (iso2, name, capital, fp) in enumerate(chosen, 1):
        for num, dur in ((3, 1.0), (2, 1.0), (1, 1.0)):
            fr = work / f"f_r{i}_{num}.png"
            _frame_round(fr, fp, i, n_rounds, num)
            frames.append((fr, dur))
        rv = work / f"f_r{i}_rev.png"
        _frame_reveal(rv, fp, i, n_rounds, name, capital)
        frames.append((rv, 1.7))
    outro = work / "f_outro.png"; _frame_outro(outro); frames.append((outro, 2.8))

    # Secuencia numerada (image2) = método robusto entre versiones de ffmpeg:
    # cada frame se repite dur*fps veces y se codifica a 30 fps constante.
    import shutil
    fps = 30
    seq = work / "seq"
    seq.mkdir(exist_ok=True)
    idx = 0
    for p, dur in frames:
        for _ in range(max(1, round(dur * fps))):
            shutil.copyfile(p, seq / f"{idx:05d}.png")
            idx += 1

    raw = work / "raw.mp4"
    cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", str(seq / "%05d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
           "-movflags", "+faststart", str(raw)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not raw.exists():
        print(f"  geoquiz: ffmpeg encode fail: {r.stderr[-400:]}")
        return None

    total_s = sum(d for _, d in frames)
    try:
        from ..ranking.generator import _add_music_to_video
        final = _add_music_to_video(raw, work, int(total_s)) or raw
    except Exception as e:
        print(f"  geoquiz: music skip ({e})")
        final = raw

    names = ", ".join(c[1] for c in chosen)
    title = "Guess the country by its flag 🏴 | Only 1% score 5/5"
    desc = (
        "Can you name all 5 flags? Comment your score below! 🌍\n\n"
        f"Flags in this round: {names}.\n"
        "New geography quiz every day — follow to test yourself.\n\n"
        "Flags: public domain (flagcdn.com). Capitals verified.\n\n"
        "#geography #quiz #flags #guessthecountry #trivia #geoquiz #shorts #learnontiktok"
    )
    return {
        "slug": slug, "video_path": str(final),
        "title": title[:100], "description": desc[:4900],
        "tags": ["geography", "quiz", "flags", "guess the country", "trivia", "geoquiz", "shorts"],
        "countries": [c[0] for c in chosen],
        "round_key": "-".join(c[0] for c in chosen),
    }
