"""Atomización: extrae 4-5 Shorts promocionales de un long-form.

Para cada capítulo del long-form, genera un clip vertical 9:16 con:
- Tramo del capítulo (max ~45s)
- Texto-hook arriba con el nombre del capítulo
- CTA-overlay en los últimos ~3s: "VIDEO COMPLETO EN YT · @handle"
- Crop centrado 16:9 → 9:16
- Voz + música del original

Coste: 0 € (todo local con ffmpeg + Pillow). No reusa Gemini ni Pollinations.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from . import graphics, script
from .config import PENDING_DIR, UPLOADED_DIR

CTA_DURATION = 3.0  # segundos que se muestra el CTA al final
HOOK_DURATION = 2.4  # texto-hook al inicio (consistente con Shorts)
MAX_CLIP_SECONDS = 45.0  # tope de duración modo funnel (con CTA a YT)
MAX_CLIP_SECONDS_NATIVE = 32.0  # tope modo native (TT-first, sin CTA YT)


def _find_slug(slug: str) -> Path | None:
    for base in (PENDING_DIR, UPLOADED_DIR):
        if (base / slug).exists():
            return base / slug
    return None


def render_cta_overlay_png(handle: str, channel: str, dest: Path) -> Path:
    """PNG transparente 1080x1920 con el CTA grande en la mitad inferior.

    Estilo: dedo apuntando arriba (al título del video) + 'VIDEO COMPLETO EN YT'
    + handle del canal. Banda terracota translúcida para destacar.
    """
    W, H = 1080, 1920
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Banda inferior translúcida (terracota oscuro)
    band_top, band_bot = int(H * 0.58), int(H * 0.86)
    draw.rounded_rectangle(
        [60, band_top, W - 60, band_bot], radius=44,
        fill=(168, 78, 44, 220),  # terracota oscuro
    )

    # Dedo apuntando arriba 👆 (un Pillow simple, no emoji — diseñamos un triángulo)
    cy = band_top + 70
    cx = W // 2
    # Triángulo grande blanco que apunta arriba
    tri = [(cx - 50, cy + 50), (cx + 50, cy + 50), (cx, cy - 30)]
    draw.polygon(tri, fill=(255, 255, 255, 255))
    # Línea vertical bajo el triángulo (mango del dedo)
    draw.rounded_rectangle([cx - 18, cy + 50, cx + 18, cy + 110], radius=12, fill=(255, 255, 255, 255))

    # Línea principal "VIDEO COMPLETO EN YT"
    main_font = graphics._fit_font(draw, "VIDEO COMPLETO EN YT", W - 200, start_size=86, weight=900, min_size=56)
    text1 = "VIDEO COMPLETO EN YT"
    bbox = draw.textbbox((0, 0), text1, font=main_font)
    tw = bbox[2] - bbox[0]
    tx = (W - tw) // 2 - bbox[0]
    ty = band_top + 160
    draw.text((tx, ty), text1, font=main_font, fill=(255, 255, 255, 255),
              stroke_width=6, stroke_fill=(0, 0, 0, 255))

    # Sub-línea con el canal/handle (sin emoji: Montserrat no los renderiza)
    sub_text = f"{channel} · {handle}"
    sub_font = graphics._fit_font(draw, sub_text, W - 200, start_size=58, weight=700, min_size=36)
    bbox2 = draw.textbbox((0, 0), sub_text, font=sub_font)
    tw2 = bbox2[2] - bbox2[0]
    tx2 = (W - tw2) // 2 - bbox2[0]
    ty2 = ty + main_font.size + 26
    draw.text((tx2, ty2), sub_text, font=sub_font, fill=(255, 230, 200, 255),
              stroke_width=5, stroke_fill=(60, 25, 10, 255))

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)
    return dest


def render_comment_bait_png(question: str, dest: Path) -> Path:
    """PNG transparente 1080x1920 con una pregunta comment-bait al final del clip.
    Estilo TT-native: banda oscura translúcida + texto grande con emoji 👇 grande."""
    W, H = 1080, 1920
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Banda en la mitad-baja (más arriba que el CTA del modo funnel)
    band_top, band_bot = int(H * 0.50), int(H * 0.80)
    draw.rounded_rectangle(
        [50, band_top, W - 50, band_bot], radius=44,
        fill=(0, 0, 0, 200),
    )
    # Pregunta con wrap
    question = (question or "").strip().upper()
    if not question:
        question = "¿LO SABÍAS?"
    max_w = W - 180
    longest = max(question.split(), key=len) if question.split() else question
    font = graphics._fit_font(draw, longest, max_w, start_size=92, weight=900, min_size=48)
    words, lines, cur = question.split(), [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    # Si necesita más de 4 líneas, encoge fuente hasta caber
    while len(lines) > 4 and font.size > 48:
        font = graphics._load_font(font.size - 8, 900)
        words, lines, cur = question.split(), [], ""
        for w in words:
            test = f"{cur} {w}".strip()
            if draw.textbbox((0, 0), test, font=font)[2] > max_w and cur:
                lines.append(cur); cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
    lines = lines[:4]
    asc, desc = font.getmetrics()
    lh = int((asc + desc) * 1.06)
    total_h = lh * len(lines)
    y = band_top + 60
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (W - (bbox[2] - bbox[0])) // 2 - bbox[0]
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255),
                  stroke_width=8, stroke_fill=(0, 0, 0, 255))
        y += lh
    # Triángulo apuntando hacia abajo grande (en lugar de emoji 👇)
    cy = y + 60
    cx = W // 2
    tri = [(cx - 70, cy - 40), (cx + 70, cy - 40), (cx, cy + 60)]
    draw.polygon(tri, fill=(255, 235, 200, 255))
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)
    return dest


def _generate_bait_questions(scripts, lang: str) -> list[str]:
    """Una pregunta comment-bait por capítulo. Usa Gemini si hay clave, sino fallback genérico."""
    from .config import gemini_key
    loc = getattr(scripts, lang)
    chapters = loc.chapters
    api = gemini_key()
    if not api:
        return [f"¿Lo sabías?" for _ in chapters]
    try:
        from google import genai
        from google.genai import types
        import json as _json
        import re as _re
        client = genai.Client(api_key=api)
        prompt = (
            "Por cada capítulo de un video corto sobre dinero, genera UNA pregunta "
            "comment-bait MUY corta (4-7 palabras MAX) en español o inglés según el lang, "
            "diseñada para forzar comentarios. Estilo TikTok 2026. Ejemplos buenos: "
            "'¿Te lo creías?', '¿Cuál te flipa más?', '¿Es trampa o genio?'. "
            "Devuelve JSON: {\"questions\": [\"...\", \"...\"]} con N preguntas en orden.\n\n"
            f"Lang: {lang}\n"
            f"Capítulos:\n" +
            "\n".join(f"{i+1}. {c.name}: {c.text[:160]}" for i, c in enumerate(chapters))
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7, max_output_tokens=512,
            ),
        )
        raw = (resp.text or "").strip()
        if raw.startswith("```"):
            raw = _re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=_re.MULTILINE)
        data = _json.loads(raw or "{}")
        qs = data.get("questions", [])
        if len(qs) >= len(chapters):
            return qs[:len(chapters)]
    except Exception:
        pass
    return [f"¿Lo sabías?" for _ in chapters]


def _build_clip(
    src_mp4: Path, start: float, duration: float,
    hook_png: Path, cta_png: Path, dest: Path,
) -> None:
    """Recorta src_mp4 desde `start` durante `duration`s, lo reencuadra de
    16:9 a 9:16 con center-crop vertical, y superpone hook (al inicio) + CTA
    (al final)."""
    # Filtro: crop centrado vertical (ih*9/16:ih) → scale 1080x1920 → overlays
    # con enable temporal. hook 0..HOOK_DURATION; CTA en los últimos CTA_DURATION s.
    hook_end = min(HOOK_DURATION, duration)
    cta_start = max(0.0, duration - CTA_DURATION)
    vf = (
        f"[0:v]crop=ih*9/16:ih,scale=1080:1920,format=yuv420p[bg];"
        f"[bg][1:v]overlay=0:0:enable='between(t\\,0\\,{hook_end:.2f})'[hk];"
        f"[hk][2:v]overlay=0:0:enable='between(t\\,{cta_start:.2f}\\,{duration:.2f})'[vout]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.2f}", "-t", f"{duration:.2f}", "-i", str(src_mp4),
        "-loop", "1", "-t", f"{duration:.2f}", "-i", str(hook_png),
        "-loop", "1", "-t", f"{duration:.2f}", "-i", str(cta_png),
        "-filter_complex", vf,
        "-map", "[vout]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-t", f"{duration:.2f}",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr[-2000:])
        raise RuntimeError(f"build_clip failed: {dest}")


def atomize_long(
    slug: str, lang: str = "es",
    handle: str = "@waitwhy_ybb", channel: str = "WaitWhy",
    progress=lambda m: None,
) -> list[Path]:
    """Genera Shorts promocionales (uno por capítulo) del long-form `slug`.
    Devuelve lista de rutas a los MP4 generados."""
    d = _find_slug(slug)
    if d is None:
        raise FileNotFoundError(slug)
    scripts = script.load_long_scripts(d)
    loc = getattr(scripts, lang)
    src = d / f"video_long_{lang}.mp4"
    if not src.exists():
        raise FileNotFoundError(src)

    atom_dir = d / "atomized"
    atom_dir.mkdir(exist_ok=True)

    # CTA overlay (compartido entre todos los clips de este long-form)
    cta_png = atom_dir / "cta.png"
    if not cta_png.exists():
        render_cta_overlay_png(handle, channel, cta_png)

    # Para cada capítulo: calcular el offset temporal en el long-form usando
    # las DURACIONES estimadas por capítulo en el guion (intro + chapters).
    # Como tenemos voice_<lang>.json con timestamps por palabra, podemos
    # calcular el offset real concatenando los textos.
    import json as _json
    voice_json = _json.loads((d / f"voice_{lang}.json").read_text(encoding="utf-8"))
    words = voice_json.get("words", [])

    # Función auxiliar: dado el offset en CARACTERES, devuelve el tiempo en s
    def time_at_char(target_chars: int) -> float:
        cum = 0
        for w in words:
            cum += len(w["word"]) + 1  # +1 por espacio
            if cum >= target_chars:
                return float(w["end"])
        return float(words[-1]["end"]) if words else 0.0

    # Construye lista de offsets de inicio y duración para cada capítulo
    intro_text = loc.intro.text
    intro_chars = len(intro_text) + 1
    out_paths: list[Path] = []

    cur_chars = intro_chars  # tras la intro empieza el capítulo 1
    for i, ch in enumerate(loc.chapters):
        chap_chars = len(ch.text) + 1
        start_s = time_at_char(cur_chars)
        end_s = time_at_char(cur_chars + chap_chars)
        cur_chars += chap_chars
        duration = min(MAX_CLIP_SECONDS, end_s - start_s)
        if duration < 8:
            progress(f"  cap[{i}] '{ch.name}': muy corto ({duration:.1f}s), salto")
            continue
        progress(f"  cap[{i}] '{ch.name}': {start_s:.1f}s + {duration:.1f}s")

        # Texto-hook con el nombre del capítulo
        hook_png = atom_dir / f"hook_{lang}_{i}.png"
        graphics.render_hook_overlay_png(ch.name, hook_png)

        out = atom_dir / f"clip_{lang}_{i:02d}_{_slug_clean(ch.name)}.mp4"
        try:
            _build_clip(src, start_s, duration, hook_png, cta_png, out)
            out_paths.append(out)
        except Exception as e:
            progress(f"    ⚠️ falló: {e}")
    return out_paths


def _build_clip_native(
    src_mp4: Path, voice_mp3: Path, start: float, duration: float,
    hook_png: Path, bait_png: Path, dest: Path,
) -> None:
    """Modo TT-native: recorta src, usa SOLO la voz (sin música), reencuadra 9:16
    con center-crop, overlay hook al inicio + comment-bait al final."""
    hook_end = min(HOOK_DURATION, duration)
    bait_start = max(0.0, duration - CTA_DURATION)
    vf = (
        f"[0:v]crop=ih*9/16:ih,scale=1080:1920,format=yuv420p[bg];"
        f"[bg][2:v]overlay=0:0:enable='between(t\\,0\\,{hook_end:.2f})'[hk];"
        f"[hk][3:v]overlay=0:0:enable='between(t\\,{bait_start:.2f}\\,{duration:.2f})'[vout]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.2f}", "-t", f"{duration:.2f}", "-i", str(src_mp4),       # 0: video con música
        "-ss", f"{start:.2f}", "-t", f"{duration:.2f}", "-i", str(voice_mp3),     # 1: SOLO voz
        "-loop", "1", "-t", f"{duration:.2f}", "-i", str(hook_png),               # 2: hook
        "-loop", "1", "-t", f"{duration:.2f}", "-i", str(bait_png),               # 3: bait
        "-filter_complex", vf,
        "-map", "[vout]", "-map", "1:a",  # video del 0, audio SOLO del 1 (voz limpia)
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p",
        "-t", f"{duration:.2f}", str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr[-2000:])
        raise RuntimeError(f"build_clip_native failed: {dest}")


def atomize_native(
    slug: str, lang: str = "es",
    progress=lambda m: None,
) -> list[Path]:
    """Modo TT-FIRST: clips de 25-32s, sin música (para audio trending), sin
    CTA al canal de YT (lo penaliza el algoritmo de TT). En su lugar:
    comment-bait al final con pregunta diseñada para forzar comentarios.
    """
    d = _find_slug(slug)
    if d is None:
        raise FileNotFoundError(slug)
    scripts = script.load_long_scripts(d)
    loc = getattr(scripts, lang)
    src = d / f"video_long_{lang}.mp4"
    voice = d / f"voice_{lang}.mp3"
    if not src.exists() or not voice.exists():
        raise FileNotFoundError(f"falta {src} o {voice}")

    atom_dir = d / "atomized_native"
    atom_dir.mkdir(exist_ok=True)

    progress("Generando preguntas comment-bait con Gemini…")
    bait_questions = _generate_bait_questions(scripts, lang)

    # Offsets temporales (mismo cálculo que atomize_long)
    import json as _json
    voice_json = _json.loads((d / f"voice_{lang}.json").read_text(encoding="utf-8"))
    words = voice_json.get("words", [])

    def time_at_char(target_chars: int) -> float:
        cum = 0
        for w in words:
            cum += len(w["word"]) + 1
            if cum >= target_chars:
                return float(w["end"])
        return float(words[-1]["end"]) if words else 0.0

    cur_chars = len(loc.intro.text) + 1
    out_paths: list[Path] = []
    for i, ch in enumerate(loc.chapters):
        chap_chars = len(ch.text) + 1
        start_s = time_at_char(cur_chars)
        end_s = time_at_char(cur_chars + chap_chars)
        cur_chars += chap_chars
        duration = min(MAX_CLIP_SECONDS_NATIVE, end_s - start_s)
        if duration < 8:
            progress(f"  cap[{i}] '{ch.name}': muy corto ({duration:.1f}s), salto")
            continue
        progress(f"  cap[{i}] '{ch.name}': {start_s:.1f}s + {duration:.1f}s · bait: «{bait_questions[i]}»")

        hook_png = atom_dir / f"hook_{lang}_{i}.png"
        graphics.render_hook_overlay_png(ch.name, hook_png)
        bait_png = atom_dir / f"bait_{lang}_{i}.png"
        render_comment_bait_png(bait_questions[i], bait_png)

        out = atom_dir / f"clip_{lang}_{i:02d}_{_slug_clean(ch.name)}.mp4"
        try:
            _build_clip_native(src, voice, start_s, duration, hook_png, bait_png, out)
            out_paths.append(out)
        except Exception as e:
            progress(f"    ⚠️ falló: {e}")
    return out_paths


def build_clip_caption_native(loc, ch_name: str, bait_question: str) -> str:
    """Caption TT-native: pregunta comment-bait + hashtags niche (3-5, no spam #fyp)."""
    # Filtra hashtags genéricos spam — solo los específicos del guion
    spam = {"#fyp", "#parati", "#reels", "#shorts", "#viral", "#foryou", "#foryoupage"}
    niche = [h for h in loc.hashtags if h.lower() not in spam][:5]
    return f"{bait_question} 👇\n\n{' '.join(niche)}"


def _slug_clean(name: str, max_len: int = 30) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:max_len].rstrip("-") or "clip"


def build_clip_caption(loc, ch_name: str, handle: str, channel: str) -> str:
    """Caption para subir cada clip a TT/IG. Pide ir al canal por el largo."""
    hashtags = list(loc.hashtags) + ["#fyp", "#parati", "#reels", "#shorts"]
    hashtags = list(dict.fromkeys(hashtags))
    return (
        f"{ch_name} 👆\n\n"
        f"Vídeo COMPLETO en mi canal de YouTube: {channel} ({handle})\n\n"
        f"{' '.join(hashtags)}"
    )
