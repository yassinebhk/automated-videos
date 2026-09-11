"""Generador de thumbnails viral-style para Shorts YT.

Estrategia:
- Fondo: primer frame del video (ya tenemos cara/hero) recortado 1280x720
  con vignette oscuro para contraste.
- Texto principal: CIFRA extraída del título en AMARILLO GIGANTE (bottom).
- Texto secundario: palabra shock en ROJO (top) — ROBADOS/IMPUNE/OCULTÓ.
- Efectos: borde negro grueso, sombra caída — legible en móvil pequeño.
- Aunque YT decide qué thumb muestra en móviles Shorts, el thumb custom
  aparece en el navegador, en el player embed, y en la home suggested.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .graphics import _load_font

# Palabras shock por prioridad — si el título las incluye, se elige la primera
SHOCK_WORDS = [
    "NADIE FUE A LA CÁRCEL", "IMPUNE", "OCULTÓ", "ROBADOS",
    "DESAPARECIÓ", "SIN CÁRCEL", "EL CASO OCULTO",
]

CIFRA_RE = re.compile(r"(\d+[.,]?\d*)\s*(M€|MILLONES DE EUROS|MILLONES|€|\$|K€)", re.IGNORECASE)


def extract_cifra(title: str) -> str | None:
    """Extrae la cifra principal del título. Ej '300M€', '6.6M€'."""
    m = CIFRA_RE.search(title)
    if not m:
        return None
    num = m.group(1).replace(",", ".")
    unit = m.group(2).upper()
    unit = "M€" if "MILLON" in unit or unit == "M€" else unit
    return f"{num}{unit}".replace(".0M€", "M€")


def extract_shock(title: str) -> str:
    """Encuentra la palabra shock del título o devuelve default."""
    up = title.upper()
    for w in SHOCK_WORDS:
        if w in up:
            return w
    return "IMPUNE"


def extract_first_frame(video_path: Path, dest: Path, at_seconds: float = 1.0) -> Path | None:
    """Extrae un frame del video como imagen (fondo del thumbnail)."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(at_seconds), "-i", str(video_path),
             "-vframes", "1", "-q:v", "2", str(dest)],
            check=True, capture_output=True, timeout=30,
        )
        return dest if dest.exists() else None
    except Exception as e:
        print(f"  thumb: extract frame fail {e}")
        return None


def _fit_text(draw, text: str, font_path_size, max_w: int, max_h: int) -> ImageFont.FreeTypeFont:
    """Busca el mayor tamaño de fuente que quepa."""
    size = font_path_size
    while size > 40:
        f = _load_font(size, weight=900)
        bbox = draw.textbbox((0, 0), text, font=f, stroke_width=6)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= max_w and h <= max_h:
            return f
        size -= 6
    return _load_font(40, weight=900)


def _draw_outlined_text(draw, xy, text, font, fill, outline="black", stroke_w=8):
    draw.text(xy, text, font=font, fill=fill,
              stroke_width=stroke_w, stroke_fill=outline)


def _try_ai_face(dest_dir: Path, title: str) -> Path | None:
    """Genera cara AI expresiva vía Pollinations para el thumbnail (canales
    tax/finanzas): persona sorprendida/preocupada con documentos, oficina.
    Rota entre estilos para variedad. Fallback silencioso si falla."""
    try:
        from . import aimages
    except Exception:
        return None
    import random
    styles = [
        "spanish person shocked face looking at tax documents, office desk, dramatic lighting",
        "worried spanish businesswoman with calculator and papers, office, cinematic",
        "surprised spanish autonomo looking at phone, home office, warm light",
        "spanish accountant frustrated with paperwork, calculator, dramatic pose",
        "young spanish entrepreneur shocked expression pointing at laptop screen",
    ]
    prompt = random.choice(styles)
    return aimages.generate_image(prompt, dest_dir, seed=random.randint(1, 999999),
                                    width=720, height=720)


def build_viral_thumbnail(
    video_path: Path,
    title: str,
    dest: Path,
    use_ai_face: bool = False,
) -> Path | None:
    """Compone thumbnail 1280x720 viral-style.

    use_ai_face=True → intenta generar cara AI izquierda + cifra derecha
    (patrón MrBeast / canales finanzas). Fallback = frame del video.
    """
    W, H = 1280, 720

    ai_face_img: Image.Image | None = None
    if use_ai_face:
        face_path = _try_ai_face(dest.parent, title)
        if face_path and face_path.exists():
            try:
                ai_face_img = Image.open(face_path).convert("RGB")
            except Exception:
                ai_face_img = None

    # 1. Fondo: primer frame del video (o gris oscuro fallback)
    bg_frame = dest.parent / "_thumb_frame.jpg"
    frame = extract_first_frame(video_path, bg_frame, at_seconds=2.0)
    if not frame:
        bg = Image.new("RGB", (W, H), (20, 20, 30))
    else:
        bg = Image.open(frame).convert("RGB")
        src_w, src_h = bg.size
        ratio = max(W / src_w, H / src_h)
        new_w, new_h = int(src_w * ratio), int(src_h * ratio)
        bg = bg.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - W) // 2
        top = (new_h - H) // 2
        bg = bg.crop((left, top, left + W, top + H))

    # Si hay cara AI, la pegamos ocupando el 45% izquierdo (canvas 720×720 → 576×576)
    if ai_face_img:
        face_size = 560
        f_ratio = max(face_size / ai_face_img.width, face_size / ai_face_img.height)
        f_w = int(ai_face_img.width * f_ratio)
        f_h = int(ai_face_img.height * f_ratio)
        ai_face_img = ai_face_img.resize((f_w, f_h), Image.LANCZOS)
        # Crop cuadrado 560×560
        fl = (f_w - face_size) // 2
        ft = (f_h - face_size) // 2
        ai_face_img = ai_face_img.crop((fl, ft, fl + face_size, ft + face_size))
        # Vignette de la mitad derecha del fondo (donde va cifra) para dar contraste
        bg_rgba = bg.convert("RGBA")
        vg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        vd = ImageDraw.Draw(vg)
        vd.rectangle([W // 2, 0, W, H], fill=(0, 0, 0, 140))
        bg_rgba = Image.alpha_composite(bg_rgba, vg)
        # Pega cara con margen 80px izq y centrada vertical
        bg = bg_rgba.convert("RGB")
        bg.paste(ai_face_img, (80, (H - face_size) // 2))

    # 2. Vignette oscuro para contraste con texto
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # Banda oscura arriba (donde va shock) y abajo (donde va cifra)
    od.rectangle([0, 0, W, 180], fill=(0, 0, 0, 180))
    od.rectangle([0, H - 260, W, H], fill=(0, 0, 0, 200))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(bg)

    # 3. Texto shock arriba (rojo)
    shock = extract_shock(title)
    shock_font = _fit_text(draw, shock, 110, W - 80, 140)
    bbox = draw.textbbox((0, 0), shock, font=shock_font, stroke_width=8)
    sw = bbox[2] - bbox[0]
    sh = bbox[3] - bbox[1]
    _draw_outlined_text(draw, ((W - sw) // 2, 30 - bbox[1]), shock, shock_font,
                        fill=(255, 60, 60), stroke_w=8)

    # 4. Cifra abajo (amarillo GIGANTE)
    cifra = extract_cifra(title) or ""
    if cifra:
        cifra_font = _fit_text(draw, cifra, 260, W - 80, 240)
        cbox = draw.textbbox((0, 0), cifra, font=cifra_font, stroke_width=12)
        cw = cbox[2] - cbox[0]
        ch = cbox[3] - cbox[1]
        cy = H - 240 - cbox[1]
        _draw_outlined_text(draw, ((W - cw) // 2, cy), cifra, cifra_font,
                            fill=(255, 230, 40), stroke_w=12)

    dest.parent.mkdir(parents=True, exist_ok=True)
    bg.save(dest, "JPEG", quality=92)
    # Limpieza
    if bg_frame.exists():
        try:
            bg_frame.unlink()
        except Exception:
            pass
    print(f"  thumb: viral generado {dest.name} · shock='{shock}' cifra='{cifra}'")
    return dest
