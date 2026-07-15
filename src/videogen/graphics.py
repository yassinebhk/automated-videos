"""Motion graphics: escenas infográficas (PIL) en vez de B-roll de stock.

Para videos de DATOS (records, estadísticas, comparativas) el footage stock
queda cutre. Este módulo genera escenas limpias y bold: gradiente de fondo,
número/headline gigante en color de acento, sublabel, formas decorativas.

Pipeline:
  1. generate_graphic_specs(scripts, lang) → Gemini convierte cada segmento
     en {headline, sublabel} (ej. "48", "EQUIPOS")
  2. render_scene(...) → PNG 1080x1920 por segmento
  3. scene_to_clip(...) → mp4 con zoom suave, listo para compose_from_segments
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel

from .config import ASSETS_DIR, gemini_key
from .models import GeneratedScripts, LocalizedScript, VideoClip

FONT_PATH = ASSETS_DIR / "fonts" / "Montserrat.ttf"

W, H = 1080, 1920

# Paletas (gradiente vertical bg, color de acento para el headline)
PALETTES = [
    {"bg": ((13, 27, 62), (8, 12, 28)), "accent": (250, 204, 21)},   # navy → yellow
    {"bg": ((10, 30, 40), (6, 14, 22)), "accent": (45, 212, 191)},   # teal → cyan
    {"bg": ((40, 12, 50), (16, 8, 28)), "accent": (244, 114, 182)},  # purple → pink
    {"bg": ((45, 20, 12), (20, 10, 8)), "accent": (251, 146, 60)},   # warm → orange
    {"bg": ((12, 35, 28), (6, 16, 14)), "accent": (163, 230, 53)},   # green → lime
    {"bg": ((30, 14, 14), (14, 8, 10)), "accent": (248, 113, 113)},  # dark → red
]


class GraphicSpec(BaseModel):
    headline: str  # texto/número grande (ej. "48", "3 PAÍSES", "RÉCORD")
    sublabel: str  # apoyo pequeño (ej. "EQUIPOS POR PRIMERA VEZ")


def _load_font(size: int, weight: int = 900) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT_PATH), size)
    try:
        font.set_variation_by_axes([weight])
    except Exception:
        pass
    return font


def _fit_font(
    draw: ImageDraw.ImageDraw, text: str, max_w: int, start_size: int,
    weight: int = 900, min_size: int = 36,
) -> ImageFont.FreeTypeFont:
    """Devuelve la fuente más grande (≤ start_size) con la que `text` cabe en max_w."""
    size = start_size
    while size > min_size:
        font = _load_font(size, weight)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_w:
            return font
        size -= 6
    return _load_font(min_size, weight)


def _vertical_gradient(c1: tuple, c2: tuple) -> Image.Image:
    """Gradiente vertical suave c1 (arriba) → c2 (abajo)."""
    base = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        base.putpixel((0, y), (r, g, b))
    return base.resize((W, H))


def _draw_text_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    cy: int,
    fill: tuple,
    max_width: int = W - 120,
    line_spacing: float = 1.05,
) -> int:
    """Dibuja texto centrado horizontalmente, con wrap por palabras. Devuelve y final."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)

    # Altura de línea
    asc, desc = font.getmetrics()
    lh = int((asc + desc) * line_spacing)
    total_h = lh * len(lines)
    y = cy - total_h // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x = (W - lw) // 2 - bbox[0]
        # Sombra sutil
        draw.text((x + 4, y + 4), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=fill)
        y += lh
    return y


def render_hook_overlay_png(text: str, dest: Path, max_lines: int = 3) -> Path:
    """PNG transparente a pantalla completa con el TEXTO-HOOK arriba.

    Estilo TikTok: mayúsculas, fuente grande, banda oscura translúcida detrás y
    borde negro grueso para leerse sobre cualquier footage. Para parar el scroll
    en el segundo 0 (la palanca nº1 de retención en TikTok/Reels)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    text = (text or "").strip().upper()
    if not text:
        img.save(dest)
        return dest

    max_width = W - 150
    longest = max(text.split(), key=len) if text.split() else text
    font = _fit_font(draw, longest, max_width, start_size=108, weight=900, min_size=52)

    # Wrap por palabras
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] > max_width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:  # recorta si es demasiado largo
        lines = lines[:max_lines]

    asc, desc = font.getmetrics()
    lh = int((asc + desc) * 1.08)
    total_h = lh * len(lines)
    top = int(H * 0.12)

    # Banda oscura translúcida detrás del texto
    pad = 38
    draw.rounded_rectangle(
        [55, top - pad, W - 55, top + total_h + pad], radius=40, fill=(0, 0, 0, 120)
    )
    y = top
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (W - (bbox[2] - bbox[0])) // 2 - bbox[0]
        draw.text(
            (x, y), line, font=font, fill=(255, 255, 255, 255),
            stroke_width=8, stroke_fill=(0, 0, 0, 255),
        )
        y += lh
    img.save(dest)
    return dest


def render_scene(
    spec: GraphicSpec, index: int, total: int, dest: Path, theme_idx: int
) -> Path:
    """Renderiza una escena infográfica a PNG."""
    pal = PALETTES[theme_idx % len(PALETTES)]
    img = _vertical_gradient(*pal["bg"]).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    accent = pal["accent"]

    # Forma decorativa: círculo grande translúcido detrás del headline
    cx, cy = W // 2, int(H * 0.40)
    radius = 360
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        outline=accent + (60,),
        width=6,
    )
    radius2 = 460
    draw.ellipse(
        [cx - radius2, cy - radius2, cx + radius2, cy + radius2],
        outline=accent + (30,),
        width=3,
    )

    # Indicador de progreso (dots) arriba
    dot_r = 9
    gap = 44
    total_w = gap * (total - 1)
    start_x = (W - total_w) // 2
    dy = 220
    for i in range(total):
        on = i == index
        fill = accent + (255,) if on else (255, 255, 255, 70)
        rr = dot_r + 3 if on else dot_r
        draw.ellipse([start_x + i * gap - rr, dy - rr, start_x + i * gap + rr, dy + rr], fill=fill)

    # Headline gigante (auto-shrink según longitud)
    head = spec.headline.upper()
    head_size = 300 if len(head) <= 3 else (200 if len(head) <= 8 else 130)
    head_font = _load_font(head_size, 900)
    y_after = _draw_text_centered(draw, head, head_font, cy, accent)

    # Sublabel debajo del círculo
    sub_font = _load_font(58, 800)
    _draw_text_centered(
        draw, spec.sublabel.upper(), sub_font, int(H * 0.66), (255, 255, 255),
        max_width=W - 160,
    )

    # Barra de acento decorativa abajo del sublabel
    bar_w, bar_h = 140, 10
    draw.rounded_rectangle(
        [(W - bar_w) // 2, int(H * 0.73), (W + bar_w) // 2, int(H * 0.73) + bar_h],
        radius=5,
        fill=accent + (255,),
    )

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "PNG")
    return dest


def render_stat_overlay_png(
    spec: GraphicSpec, dest: Path, theme_idx: int
) -> Path:
    """Renderiza un overlay TRANSPARENTE (RGBA) con un stat card en el tercio
    superior, para superponer sobre clips de stock vía ffmpeg. El resto del
    frame queda transparente (no tapa el footage ni los captions de abajo)."""
    pal = PALETTES[theme_idx % len(PALETTES)]
    accent = pal["accent"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Panel redondeado semi-transparente en el tercio superior
    panel_w = 940
    px = (W - panel_w) // 2
    py = 200
    head = spec.headline.upper()
    sub = spec.sublabel.upper()

    max_text_w = panel_w - 100
    head_start = 200 if len(head) <= 3 else (150 if len(head) <= 8 else 110)
    head_font = _fit_font(d, head, max_text_w, head_start, weight=900, min_size=64)
    sub_font = _fit_font(d, sub, max_text_w, 50, weight=800, min_size=28)

    h_asc, h_desc = head_font.getmetrics()
    s_asc, s_desc = sub_font.getmetrics()
    pad = 44
    gap = 12
    panel_h = pad + h_asc + h_desc + gap + s_asc + s_desc + pad

    # Sombra del panel
    d.rounded_rectangle(
        [px + 6, py + 8, px + panel_w + 6, py + panel_h + 8], radius=34,
        fill=(0, 0, 0, 90),
    )
    # Panel
    d.rounded_rectangle(
        [px, py, px + panel_w, py + panel_h], radius=34,
        fill=(8, 12, 22, 200), outline=accent + (255,), width=4,
    )

    # Número grande centrado
    hb = d.textbbox((0, 0), head, font=head_font)
    hx = px + (panel_w - (hb[2] - hb[0])) // 2 - hb[0]
    hy = py + pad
    d.text((hx, hy), head, font=head_font, fill=accent + (255,))

    # Label
    sb = d.textbbox((0, 0), sub, font=sub_font)
    sx = px + (panel_w - (sb[2] - sb[0])) // 2 - sb[0]
    sy = hy + h_asc + h_desc + gap
    d.text((sx, sy), sub, font=sub_font, fill=(255, 255, 255, 255))

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "PNG")
    return dest


def _cover_resize(img: Image.Image, w: int, h: int) -> Image.Image:
    """Escala+recorta (cover) la imagen a w×h."""
    src_ratio = img.width / img.height
    dst_ratio = w / h
    if src_ratio > dst_ratio:
        new_h = h
        new_w = int(h * src_ratio)
    else:
        new_w = w
        new_h = int(w / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def composite_stat_over_image(
    ai_image: Path, spec: GraphicSpec, dest: Path, theme_idx: int, show_stat: bool = True
) -> Path:
    """Compone un stat card sobre una imagen IA de fondo.

    - Cover-resize de la imagen IA a 1080x1920
    - Oscurece arriba y abajo (gradiente) para legibilidad de stat/captions
    - Si show_stat: dibuja card con número grande + label en el tercio superior
    """
    pal = PALETTES[theme_idx % len(PALETTES)]
    accent = pal["accent"]

    base = Image.open(ai_image).convert("RGB")
    base = _cover_resize(base, W, H)
    # Sharpening tras el upscale (Pollinations entrega ~576px, se escala a 1080)
    base = base.filter(ImageFilter.UnsharpMask(radius=2.5, percent=110, threshold=2))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # Oscurecer franja superior (para el stat) y inferior (para captions)
    for y in range(H):
        if y < int(H * 0.42):
            a = int(150 * (1 - y / (H * 0.42)))  # top dark → fade
        elif y > int(H * 0.72):
            a = int(170 * ((y - H * 0.72) / (H * 0.28)))  # bottom dark
        else:
            a = 0
        if a:
            od.line([(0, y), (W, y)], fill=(0, 0, 0, a))

    if show_stat:
        margin = 80
        max_w = W - 2 * margin
        head = spec.headline.upper()
        start = 240 if len(head) <= 3 else (170 if len(head) <= 8 else 120)
        head_font = _fit_font(od, head, max_w, start, weight=900, min_size=70)
        sub = spec.sublabel.upper()
        sub_font = _fit_font(od, sub, max_w, 56, weight=800, min_size=30)
        # Número grande
        cy = int(H * 0.15)
        bbox = od.textbbox((0, 0), head, font=head_font)
        hw = bbox[2] - bbox[0]
        hx = (W - hw) // 2 - bbox[0]
        od.text((hx + 4, cy + 4), head, font=head_font, fill=(0, 0, 0, 200))
        od.text((hx, cy), head, font=head_font, fill=accent + (255,))
        # Label debajo
        asc, desc = head_font.getmetrics()
        ly = cy + asc + 16
        sb = od.textbbox((0, 0), sub, font=sub_font)
        lw = sb[2] - sb[0]
        lx = (W - lw) // 2 - sb[0]
        od.text((lx + 2, ly + 2), sub, font=sub_font, fill=(0, 0, 0, 200))
        od.text((lx, ly), sub, font=sub_font, fill=(255, 255, 255, 255))

    out = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, "JPEG", quality=90)
    return dest


def scene_to_clip(png: Path, duration: float, dest: Path) -> VideoClip:
    """Convierte una escena PNG en un mp4 con zoom-in suave (Ken Burns).

    Renderiza a 2x y reescala para evitar el jitter típico de zoompan.
    """
    dur = max(duration, 1.5)
    frames = int(dur * 30)
    # Zoom de 1.0 a 1.08 a lo largo del clip
    vf = (
        "scale=2160:3840,"
        f"zoompan=z='min(1+0.08*on/{frames},1.08)':d={frames}:"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,"
        "format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(png),
        "-vf", vf, "-t", f"{dur:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr[-2000:])
        raise RuntimeError("scene_to_clip ffmpeg failed")
    return VideoClip(
        path=str(dest), duration_seconds=dur, width=W, height=H, keyword="graphic"
    )


GRAPHIC_SYSTEM = """You convert a short-form video script into MOTION GRAPHICS specs.

For each segment (hook, each body beat, cta) produce a punchy on-screen graphic:
- `headline`: the SINGLE most striking number or 1-3 word phrase from that segment. Prefer raw numbers ("48", "104", "3"). If no number, use a 1-3 word power phrase ("RÉCORD", "NUEVO FORMATO").
- `sublabel`: 2-5 word support label that explains the headline (e.g., "EQUIPOS POR PRIMERA VEZ", "PARTIDOS EN TOTAL").

Keep it in the SAME language as the script segment. Headlines must be SHORT (fit on screen big).

Return ONLY JSON: {"segments": [{"headline": "...", "sublabel": "..."}, ...]} in order: hook, body[0..n], cta.
"""


def _fallback_specs(segments: list[str]) -> list[GraphicSpec]:
    """Specs de respaldo SIN Gemini: extrae el primer número del texto como
    headline (ideal para dinero) o usa una palabra corta. Nunca crashea — un
    overlay decorativo no debe tumbar la generación del vídeo entero."""
    import re

    specs: list[GraphicSpec] = []
    for text in segments:
        m = re.search(r"\d[\d.,]*\s?(?:%|€|\$|millones|mil|millón|billones)?", text)
        if m:
            headline = m.group(0).strip()
            sublabel = " ".join(text.split()[:4])
        else:
            words = [w for w in text.split() if len(w) > 3]
            headline = (words[0].upper() if words else "")
            sublabel = " ".join(text.split()[1:4])
        specs.append(GraphicSpec(headline=headline, sublabel=sublabel))
    return specs


def generate_graphic_specs(loc: LocalizedScript) -> list[GraphicSpec]:
    """Pide a Gemini un headline+sublabel por segmento.
    Cadena de modelos (quota separada) + retry en 503/429 y en JSON inválido.
    Si todo falla, devuelve specs de respaldo (no crashea)."""
    import re
    import time

    from google import genai
    from google.genai import types

    segments = [s.text for _, s in loc.ordered_segments()]
    payload = {"lang": loc.lang, "segments": segments}
    cfg = types.GenerateContentConfig(
        system_instruction=GRAPHIC_SYSTEM,
        response_mime_type="application/json",
        temperature=0.5,
        max_output_tokens=2048,
    )
    models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"]
    client = genai.Client(api_key=gemini_key())
    last_err = None
    for model in models:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model, contents=json.dumps(payload, ensure_ascii=False), config=cfg
                )
                raw = (resp.text or "").strip()
                if raw.startswith("```"):  # limpia fences markdown
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE)
                data = json.loads(raw or "{}")
                specs = [GraphicSpec.model_validate(s) for s in data.get("segments", [])]
                while len(specs) < len(segments):
                    specs.append(GraphicSpec(headline="", sublabel=""))
                return specs[: len(segments)]
            except json.JSONDecodeError as e:
                last_err = e
                print(f"  {model}: graphic JSON inválido ({attempt+1}/3), reintento...")
                time.sleep(2)
            except Exception as e:
                last_err = e
                if any(s in str(e) for s in ("503", "429", "UNAVAILABLE")):
                    wait = 4 * (attempt + 1)
                    print(f"  {model} busy ({attempt+1}/3), reintento en {wait}s...")
                    time.sleep(wait)
                else:
                    break  # error no recuperable de este modelo → siguiente
        print(f"  {model} agotado, probando siguiente modelo...")
    print(f"  ⚠ graphic specs vía Gemini fallaron ({last_err}); uso respaldo local")
    return _fallback_specs(segments)
