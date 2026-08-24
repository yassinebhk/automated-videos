"""Composición del video final con ffmpeg.

Pipeline:
- Cada TimedSegment del script tiene su ventana temporal y sus propios clips
- Para cada segmento, los clips se reparten dentro de su ventana (clip_dur = seg.duration / len(clips))
- Escala/recorta a 1080x1920 o 1920x1080
- Mezcla música de fondo a -22dB bajo la voz
- Quema captions tipo TikTok (chunks de 2-3 palabras, sincronizados al timestamp)
"""
from __future__ import annotations

import random
import subprocess
from pathlib import Path

from .config import ASSETS_DIR, MUSIC_DIR
from .models import TimedSegment, VideoClip, VoiceTrack

FONTS_DIR = ASSETS_DIR / "fonts"
FONT_NAME = "Montserrat"  # variable font, libass picks weight via Bold flag


VERT_W, VERT_H = 1080, 1920
HORIZ_W, HORIZ_H = 1920, 1080
MIN_CLIP_DUR = 2.0  # bajo este umbral, mejor 1 clip para todo el segmento


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def build_caption_ass(track: VoiceTrack, dest: Path, vertical: bool = True) -> Path:
    """Genera un archivo .ass con captions estilo TikTok (chunks 2 palabras).

    Estilo:
    - Tipografía Montserrat (variable, peso heavy vía Bold=1)
    - Texto blanco con outline negro grueso + sombra suave
    - Posición: ~30% desde abajo (safe-area TikTok, no oculta el feed UI)
    - Chunks de 2 palabras para máxima legibilidad en mobile
    """
    play_w, play_h = (VERT_W, VERT_H) if vertical else (HORIZ_W, HORIZ_H)
    # Bajado de 96 → 84pt en vertical: a 96 los chunks con palabras largas
    # ("PROCESAMIENTO PENITENCIARIO", "MEDICAMENTOS PATRIMONIO") desbordaban
    # el ancho útil (1080px - 160 margen = 920px). 84pt cabe siempre incluso
    # con 2 palabras de 12+ chars.
    font_size = 84 if vertical else 70
    # Alignment=2 (bottom-center). MarginV = px desde abajo
    margin_v = int(play_h * 0.30) if vertical else 100

    # Umbral: si el chunk combinado supera MAX_CHARS_CHUNK caracteres,
    # el texto renderizado desbordará → usar solo 1 palabra en ese chunk.
    # 14 chars * ~55px/char = 770px, cabe con margen holgado en 920px útil.
    MAX_CHARS_CHUNK = 14 if vertical else 22

    chunks: list[tuple[float, float, str]] = []
    i = 0
    words = track.words
    chunk_size = 2 if vertical else 3
    while i < len(words):
        size = chunk_size if i + chunk_size <= len(words) else (len(words) - i)
        chunk_words = words[i : i + size]
        text = " ".join(w.word.upper() for w in chunk_words)
        # Si desborda, retrocedemos a 1 palabra para este chunk
        if len(text) > MAX_CHARS_CHUNK and size > 1:
            size = 1
            chunk_words = words[i : i + 1]
            text = chunk_words[0].word.upper()
        start = chunk_words[0].start
        end = chunk_words[-1].end
        chunks.append((start, end, text))
        i += size

    # ASS colors: &HAABBGGRR (alpha + BGR). 00 alpha = opaque.
    # Primary = white, Outline = black, BackColour (shadow) = semi-transparent black
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT_NAME},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,1,0,0,0,100,100,1,0,1,6,2,2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for start, end, text in chunks:
        # En ASS el campo Text es el último: las comas NO se escapan.
        # Solo neutralizamos llaves (bloques de override) y backslashes sueltos.
        safe = text.replace("{", "(").replace("}", ")")
        lines.append(
            f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Default,,0,0,0,,{safe}\n"
        )
    dest.write_text("".join(lines), encoding="utf-8")
    return dest


def _pick_music(mood: str | None = None) -> Path | None:
    """Elige un track. Si hay subcarpeta music/<mood>/ usa esa; si no, busca
    en todas las subcarpetas + raíz (recursivo)."""
    if mood:
        mood_dir = MUSIC_DIR / mood
        if mood_dir.exists():
            tracks = list(mood_dir.glob("*.mp3"))
            if tracks:
                return random.choice(tracks)
    tracks = list(MUSIC_DIR.rglob("*.mp3"))
    return random.choice(tracks) if tracks else None


def make_preview(src: Path, dest: Path) -> Path:
    """Versión ligera (540x960, comprimida) para previsualizar en Telegram
    sin superar el límite de 50MB ni hacer timeout en el upload."""
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", "scale=540:960",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart", str(dest),
    ]
    _run(cmd)
    return dest


def make_share(src: Path, dest: Path) -> Path:
    """Versión 1080p comprimida (~15MB) para compartir/cross-post: calidad de sobra
    para redes (recomprimen igual) y sube rápido sin timeouts."""
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
        "-vf", "scale=1080:1920", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", str(dest),
    ]
    _run(cmd)
    return dest


def make_tiktok_variant(video_with_music: Path, voice_audio: str, dest: Path) -> Path:
    """Crea la variante TikTok: mismo video pero con SOLO la voz (sin música),
    para que añadas audio trending en la app. Copia el stream de video (rápido,
    sin re-encode)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_with_music),
        "-i", str(voice_audio),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(dest),
    ]
    _run(cmd)
    return dest


def _run(cmd: list[str]) -> None:
    print("  $ ffmpeg ...", len(cmd), "args")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-2000:])
        print(proc.stderr[-4000:])
        raise RuntimeError(f"ffmpeg failed (rc={proc.returncode})")


def _plan_clip_durations(
    segments: list[TimedSegment],
) -> list[tuple[VideoClip, float]]:
    """Para cada segmento, distribuye su duración entre sus clips.

    Garantiza clips de >= MIN_CLIP_DUR (reduciendo número de clips si hace falta).
    Devuelve lista plana de (clip, duration_to_play) en orden temporal.
    """
    plan: list[tuple[VideoClip, float]] = []
    for seg in segments:
        seg_dur = max(seg.duration, MIN_CLIP_DUR)
        clips = list(seg.clips)
        if not clips:
            continue
        # El teaser usa cortes más rápidos (ráfaga); el resto, ritmo normal
        min_clip = 1.2 if seg.label == "teaser" else MIN_CLIP_DUR
        max_clips = max(1, int(seg_dur // min_clip))
        clips = clips[:max_clips]
        per = seg_dur / len(clips)
        for c in clips:
            plan.append((c, per))
    return plan


def compose_from_segments(
    voice: VoiceTrack,
    segments: list[TimedSegment],
    captions_ass: Path | None,
    dest: Path,
    vertical: bool = True,
    stat_overlays: list[tuple[Path, float, float]] | None = None,
    music: bool = True,
    music_mood: str | None = None,
) -> Path:
    """Ensambla el video usando segmentos alineados al script.

    Si captions_ass es None, no quema subtítulos (modo motion graphics).
    stat_overlays: lista de (png_transparente, start, end) que se superponen.
    music=False: solo voz, sin música de fondo (variante para TikTok donde
    añadirás audio trending en la app)."""
    out_w, out_h = (VERT_W, VERT_H) if vertical else (HORIZ_W, HORIZ_H)
    plan = _plan_clip_durations(segments)
    if not plan:
        raise ValueError("No hay clips para componer.")

    total_duration = voice.duration_seconds + 0.5

    inputs: list[str] = []
    filter_parts: list[str] = []
    concat_inputs = ""

    for i, (clip, dur) in enumerate(plan):
        inputs += ["-stream_loop", "-1", "-t", f"{dur:.3f}", "-i", clip.path]
        filter_parts.append(
            f"[{i}:v]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},setsar=1,fps=30,format=yuv420p[v{i}]"
        )
        concat_inputs += f"[v{i}]"

    n = len(plan)

    def _ffmpeg_escape(p: str) -> str:
        return (
            p.replace("\\", r"\\")
            .replace(":", r"\:")
            .replace("'", r"\'")
            .replace(",", r"\,")
            .replace("[", r"\[")
            .replace("]", r"\]")
        )

    # Concat de los clips → [bg]
    filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[bg]")

    # Audio: voz (+ música opcional)
    voice_idx = n
    music_path = _pick_music(music_mood) if music else None
    if music_path:
        music_idx = n + 1
        inputs += ["-i", voice.audio_path, "-stream_loop", "-1", "-i", str(music_path)]
        filter_parts.append(
            f"[{voice_idx}:a]volume=1.0[va];"
            f"[{music_idx}:a]volume=0.07[ma];"
            f"[va][ma]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        audio_out = "[aout]"
        next_idx = n + 2
    else:
        inputs += ["-i", voice.audio_path]
        # Sin brackets: es un stream specifier de input, no un label de filter_complex
        audio_out = f"{voice_idx}:a"
        next_idx = n + 1

    # Overlays de stats timed por segmento (modo stock + datos)
    cur = "[bg]"
    if stat_overlays:
        for k, (png, start, end) in enumerate(stat_overlays):
            inputs += ["-loop", "1", "-t", f"{total_duration:.2f}", "-i", str(png)]
            ov_in = next_idx + k
            out_lbl = f"[ov{k}]"
            filter_parts.append(
                f"{cur}[{ov_in}:v]overlay=0:0:enable='between(t\\,{start:.2f}\\,{end:.2f})'{out_lbl}"
            )
            cur = out_lbl

    # Captions encima de todo
    if captions_ass is not None:
        ass_path = _ffmpeg_escape(str(captions_ass))
        fonts_arg = ""
        if FONTS_DIR.exists() and any(FONTS_DIR.glob("*.ttf")):
            fonts_arg = f":fontsdir={_ffmpeg_escape(str(FONTS_DIR))}"
        filter_parts.append(f"{cur}ass={ass_path}{fonts_arg}[vout]")
    else:
        filter_parts.append(f"{cur}null[vout]")

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filter_parts),
        "-map",
        "[vout]",
        "-map",
        audio_out,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-t",
        f"{total_duration:.2f}",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    _run(cmd)
    return dest


# --- Backwards-compat wrapper (clips planos, igual duración a cada uno) ---
def compose(
    voice: VoiceTrack,
    clips: list[VideoClip],
    captions_ass: Path,
    dest: Path,
    vertical: bool = True,
) -> Path:
    """Wrapper legacy: trata todos los clips como un único segmento de duración total."""
    if not clips:
        raise ValueError("No hay clips de B-roll para componer.")
    seg = TimedSegment(
        index=0,
        label="all",
        text="",
        start=0.0,
        end=voice.duration_seconds,
        visual_keywords=[],
        clips=clips,
    )
    return compose_from_segments(voice, [seg], captions_ass, dest, vertical)
