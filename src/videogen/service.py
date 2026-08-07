"""Lógica de generación/publicación reutilizable (CLI y UI web).

Modo por defecto: --stats (stock Pexels + overlays de datos + captions), gratis.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from . import align, compose, graphics, script, upload_youtube, visuals, voice, wikimedia
from .config import PENDING_DIR, UPLOADED_DIR

Progress = Callable[[str], None]

# Cuánto dura en pantalla el texto-hook del arranque (segundos)
HOOK_SECONDS = 2.4


def _noop(msg: str) -> None:
    pass


def load_or_make_specs(loc, work_dir: Path) -> list[graphics.GraphicSpec]:
    path = work_dir / f"graphic_specs_{loc.lang}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return [graphics.GraphicSpec.model_validate(s) for s in data]
    specs = graphics.generate_graphic_specs(loc)
    path.write_text(
        json.dumps([s.model_dump() for s in specs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return specs


def make_stat_overlays(timed, loc, work_dir: Path):
    specs = load_or_make_specs(loc, work_dir)
    ov_dir = work_dir / "stat_overlays" / loc.lang
    ov_dir.mkdir(parents=True, exist_ok=True)
    overlays = []
    for i, seg in enumerate(timed):
        spec = specs[i] if i < len(specs) else graphics.GraphicSpec(headline="?", sublabel="")
        png = graphics.render_stat_overlay_png(spec, ov_dir / f"ov_{i}.png", theme_idx=i)
        overlays.append((png, seg.start, seg.end))
    return overlays


def generate(
    topic: str,
    langs: tuple[str, ...] = ("es", "en"),
    progress: Progress = _noop,
    ai_hero: bool = True,
) -> str:
    """Genera el/los video(s) en modo --stats. Devuelve el slug."""
    progress("Generando guion bilingüe con Gemini…")
    scripts = script.generate_scripts(topic)
    slug = scripts.slug
    work_dir = PENDING_DIR / slug
    work_dir.mkdir(parents=True, exist_ok=True)
    script.save_scripts(scripts, work_dir)
    progress(f"Guion listo (slug: {slug})")

    # Fotos CC del famoso (si el topic es sobre una persona pública)
    person_clips = []
    if getattr(scripts, "subject_person", "").strip():
        person = scripts.subject_person.strip()
        progress(f"Buscando fotos CC de {person} (Wikimedia)…")
        imgs = wikimedia.fetch_cc_images(person, work_dir / "people", n=3)
        if imgs:
            attr = wikimedia.attribution_line(imgs)
            for lc in (scripts.es, scripts.en):
                if attr and attr not in lc.description:
                    lc.description = (lc.description + "\n\n" + attr).strip()
            script.save_scripts(scripts, work_dir)  # persistir atribución en descripción
            from pathlib import Path as _P
            for j, im in enumerate(imgs):
                try:
                    clip = graphics.scene_to_clip(_P(im["path"]), 4.0, work_dir / "people" / f"person_{j}.mp4")
                    person_clips.append(clip)
                except Exception as e:
                    progress(f"  ⚠ foto {j} falló ({str(e)[:60]}), salto")
            if person_clips:
                progress(f"  ✓ {len(person_clips)} fotos de {person} (con atribución)")
            else:
                progress(f"  sin fotos válidas de {person}, sigo sin caras reales")
        else:
            progress(f"  sin fotos CC de {person}, uso simbólico")

    # Imagen IA "wow" del teaser (Pollinations, gratis). Solo si NO hay famoso:
    # para personas usamos su foto real CC, mejor que un rostro generado.
    hero_clip = None
    if ai_hero and not getattr(scripts, "subject_person", "").strip():
        progress("Generando imagen IA del teaser (Pollinations, gratis)…")
        try:
            from . import aimages
            hero_clip = aimages.generate_hero_clip(scripts, work_dir)
        except Exception as e:
            progress(f"  imagen IA falló: {str(e)[:60]}")
        progress("  ✓ imagen IA lista" if hero_clip else "  sin imagen IA, sigo con stock")

    for lang in langs:
        loc = getattr(scripts, lang)
        progress(f"[{lang}] Sintetizando voz…")
        track = voice.synthesize(loc, work_dir)

        progress(f"[{lang}] Descargando B-roll de Pexels…")
        timed = align.segment_timings(loc, track)
        anchor = visuals.topic_subject_from_slug(slug)
        visuals.fetch_clips_for_segments(
            timed, work_dir / "broll" / "vertical", orientation="portrait", topic_anchor=anchor
        )

        # Caras del famoso: teaser primero, luego repartidas por el body
        if person_clips and timed:
            timed[0].clips = [person_clips[0]] + timed[0].clips
            body_idx = [i for i, s in enumerate(timed) if s.label.startswith("body")]
            for k, bi in enumerate(body_idx):
                if k + 1 < len(person_clips):
                    timed[bi].clips = [person_clips[k + 1]] + timed[bi].clips

        # Imagen IA como primer frame del teaser (cuando no hay famoso)
        if hero_clip and timed:
            timed[0].clips = [hero_clip] + timed[0].clips

        progress(f"[{lang}] Generando overlays de datos…")
        overlays = make_stat_overlays(timed, loc, work_dir)

        # Texto-hook en pantalla en el segundo 0 (palanca nº1 de retención TikTok)
        hook_text = (getattr(loc, "thumbnail_text", "") or loc.hook.text or "").strip()
        if hook_text:
            hk_dir = work_dir / "hook"
            hk = graphics.render_hook_overlay_png(hook_text, hk_dir / f"hook_{lang}.png")
            overlays = list(overlays)
            # Evita choque visual: el overlay del 1er segmento no compite con el
            # hook → lo retrasamos hasta que el hook desaparece (o lo quitamos).
            if overlays:
                png0, s0, e0 = overlays[0]
                if e0 > HOOK_SECONDS + 0.3:
                    overlays[0] = (png0, HOOK_SECONDS, e0)
                else:
                    overlays = overlays[1:]
            overlays = overlays + [(hk, 0.0, HOOK_SECONDS)]
            progress(f"[{lang}] Texto-hook: «{hook_text[:48]}»")

        progress(f"[{lang}] Componiendo video YouTube (música: {scripts.music_mood})…")
        ass = compose.build_caption_ass(track, work_dir / f"captions_{lang}_v.ass", vertical=True)
        out = work_dir / f"video_{lang}_vertical.mp4"
        compose.compose_from_segments(
            track, timed, ass, out, vertical=True, stat_overlays=overlays,
            music=True, music_mood=scripts.music_mood,
        )

        progress(f"[{lang}] Generando variante TikTok (sin música)…")
        tiktok = work_dir / f"video_{lang}_vertical_tiktok.mp4"
        compose.make_tiktok_variant(out, track.audio_path, tiktok)
        progress(f"[{lang}] ✓ Video listo (YT + TikTok)")

    return slug


def _build_long_description(loc, timed) -> str:
    """Enriquece la descripción long-form con timestamps de capítulos al final."""
    base = (loc.description or "").rstrip()
    lines = ["", "📍 Capítulos:"]
    for s in timed:
        if s.label == "intro":
            label = "Intro"
        elif s.label == "outro":
            label = "Cierre"
        elif s.label.startswith("chapter"):
            label = s.label.split(":", 1)[1] if ":" in s.label else "Capítulo"
        else:
            continue
        ts = int(s.start)
        mm, ss = divmod(ts, 60)
        lines.append(f"{mm:02d}:{ss:02d} {label}")
    if loc.hashtags:
        lines += ["", " ".join((h if h.startswith("#") else f"#{h}") for h in loc.hashtags)]
    return base + "\n" + "\n".join(lines)


def generate_long(
    topic: str,
    target_minutes: int = 7,
    langs: tuple[str, ...] = ("es", "en"),
    progress: Progress = _noop,
) -> str:
    """Genera un long-form (16:9, ~7 min) bilingüe. Devuelve el slug."""
    progress("Generando guion LONG-FORM con Gemini…")
    scripts = script.generate_long_scripts(topic, target_minutes=target_minutes)
    slug = scripts.slug
    work_dir = PENDING_DIR / slug
    work_dir.mkdir(parents=True, exist_ok=True)
    script.save_long_scripts(scripts, work_dir)
    progress(f"Guion long-form listo (slug: {slug}, {len(scripts.es.chapters)} capítulos)")

    # Fotos CC del famoso (Wikimedia) — reusamos exactamente la lógica de Shorts.
    person_clips = []
    if scripts.subject_person.strip():
        person = scripts.subject_person.strip()
        progress(f"Buscando fotos CC de {person} (Wikimedia)…")
        imgs = wikimedia.fetch_cc_images(person, work_dir / "people", n=4)
        if imgs:
            attr = wikimedia.attribution_line(imgs)
            for lc in (scripts.es, scripts.en):
                if attr and attr not in lc.description:
                    lc.description = (lc.description + "\n\n" + attr).strip()
            script.save_long_scripts(scripts, work_dir)
            from pathlib import Path as _P
            for j, im in enumerate(imgs):
                clip = graphics.scene_to_clip(_P(im["path"]), 5.0, work_dir / "people" / f"person_{j}.mp4")
                person_clips.append(clip)
            progress(f"  ✓ {len(person_clips)} fotos de {person}")
        else:
            progress(f"  sin fotos CC de {person}")

    for lang in langs:
        loc = getattr(scripts, lang)
        progress(f"[{lang}] Sintetizando voz long-form (~{target_minutes} min)…")
        track = voice.synthesize(loc, work_dir)
        progress(f"  voz: {track.duration_seconds:.1f}s ({track.duration_seconds/60:.1f} min)")

        progress(f"[{lang}] Descargando B-roll LANDSCAPE de Pexels…")
        timed = align.segment_timings(loc, track)
        anchor = visuals.topic_subject_from_slug(slug)
        visuals.fetch_clips_for_segments(
            timed, work_dir / "broll" / "landscape",
            orientation="landscape", topic_anchor=anchor,
        )

        # Caras del famoso: intro primero, luego repartidas entre capítulos
        if person_clips and timed:
            timed[0].clips = [person_clips[0]] + timed[0].clips
            chap_idx = [i for i, s in enumerate(timed) if s.label.startswith("chapter")]
            for k, ci in enumerate(chap_idx):
                if k + 1 < len(person_clips):
                    timed[ci].clips = [person_clips[k + 1]] + timed[ci].clips

        progress(f"[{lang}] Componiendo 16:9 (música: {scripts.music_mood}, sin subs quemados — YT los autogenera)…")
        out = work_dir / f"video_long_{lang}.mp4"
        compose.compose_from_segments(
            track, timed, None, out, vertical=False,  # captions_ass=None → YT auto-captions
            music=True, music_mood=scripts.music_mood,
        )

        # Enriquece la descripción con timestamps de capítulos
        loc.description = _build_long_description(loc, timed)
        script.save_long_scripts(scripts, work_dir)
        progress(f"[{lang}] ✓ Long-form listo · {out.name}")

    return slug


def video_path(slug: str, lang: str) -> Path | None:
    for base in (PENDING_DIR, UPLOADED_DIR):
        p = base / slug / f"video_{lang}_vertical.mp4"
        if p.exists():
            return p
    return None


def get_meta(slug: str) -> dict:
    for base in (PENDING_DIR, UPLOADED_DIR):
        d = base / slug
        if (d / "scripts.json").exists():
            s = script.load_scripts(d)
            return {
                "slug": slug,
                "topic": s.topic,
                "es": {"title": s.es.title, "hashtags": s.es.hashtags},
                "en": {"title": s.en.title, "hashtags": s.en.hashtags},
            }
    return {"slug": slug}


def _notify_telegram(text: str) -> None:
    """Envía una notificación a Telegram (best-effort, no falla si no hay config)."""
    import os

    import requests

    from .config import telegram_chat_id

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = telegram_chat_id()
    if not token or not chat:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text},
            timeout=15,
        )
    except Exception:
        pass


CHANNEL_HANDLE = "@waitwhy_ybb"
CHANNEL_URL = f"https://youtube.com/{CHANNEL_HANDLE}"
PLAYLISTS_URL = f"{CHANNEL_URL}/playlists"


def _format_court_source(court) -> str:
    """Formatea el bloque de fuente judicial verificable para la descripción.
    Señal anti-AI-slop: nadie más en el nicho lo hace en español (research 08-07).
    """
    if court is None:
        return ""
    try:
        # Acepta CourtSource pydantic o dict-like
        tribunal = getattr(court, "tribunal", None) or (court.get("tribunal", "") if isinstance(court, dict) else "")
        sentencia = getattr(court, "sentencia", None) or (court.get("sentencia", "") if isinstance(court, dict) else "")
        fecha = getattr(court, "fecha", None) or (court.get("fecha", "") if isinstance(court, dict) else "")
        resumen = getattr(court, "resumen_fallo", None) or (court.get("resumen_fallo", "") if isinstance(court, dict) else "")
    except Exception:
        return ""
    if not any([tribunal, sentencia, fecha, resumen]):
        return ""
    parts = []
    if tribunal:
        parts.append(tribunal.strip())
    if sentencia:
        parts.append(sentencia.strip())
    if fecha:
        parts.append(fecha.strip())
    header = " · ".join(parts) if parts else "Fuente judicial verificable"
    body = f"\n📜 Fuente: {header}"
    if resumen:
        body += f"\n   {resumen.strip()}"
    return body


def _enrich_description_seo(base: str, title: str, hashtags: list[str], is_short: bool = True, court=None) -> str:
    """Envuelve la descripción del guion con SEO-hook (primeras 2 líneas visibles
    en search) + fuente judicial verificable + CTA fuerte al canal + link a
    playlists segmentadas.

    Estructura:
    1. Título + hook (primeras 2 líneas visibles en search)
    2. Fuente judicial (si conocida) — señal anti-AI-slop
    3. Descripción original del script
    4. CTA (subscribe + playlists)
    5. Hashtags
    """
    base = (base or "").strip()
    dur_hint = "60 segundos" if is_short else "~9 minutos"
    seo_head = f"🚨 {title}\n\nCaso real con sentencia firme, explicado en {dur_hint}."
    court_block = _format_court_source(court)
    cta = (
        "\n\n━━━━━━━━━━━━━━━\n"
        f"🎬 Casos nuevos cada semana\n"
        f"📼 Suscríbete: {CHANNEL_URL}\n"
        f"📚 Playlists por categoría (Bancarios · Políticos · Empresariales): {PLAYLISTS_URL}\n"
        "━━━━━━━━━━━━━━━"
    )
    tags_line = "\n\n" + " ".join(hashtags[:15])
    if is_short and "#shorts" not in tags_line.lower():
        tags_line += " #Shorts"
    parts = [seo_head]
    if court_block:
        parts.append(court_block)
    parts.append(base)
    return ("\n\n".join(p for p in parts if p) + cta + tags_line).strip()[:5000]



def publish(
    slug: str,
    langs: tuple[str, ...] = ("es", "en"),
    privacy: str = "public",
    progress: Progress = _noop,
    notify: bool = True,
    publish_at: str | None = None,
) -> dict:
    """Sube a YouTube en los idiomas dados. Devuelve {lang: url}.
    notify=True manda una notificación a Telegram con los links.
    publish_at: RFC3339 (ej. "2026-05-28T20:00:00Z") → sube privado y YouTube
    lo publica solo a esa hora (publicación programada)."""
    import shutil

    d = None
    for base in (PENDING_DIR, UPLOADED_DIR):
        if (base / slug).exists():
            d = base / slug
            break
    if d is None:
        raise FileNotFoundError(slug)

    scripts = script.load_scripts(d)
    links: dict[str, str] = {}
    ids: dict[str, str] = {}
    for lang in langs:
        loc = getattr(scripts, lang)
        vid = d / f"video_{lang}_vertical.mp4"
        if not vid.exists():
            progress(f"[{lang}] sin video, omitido")
            continue
        progress(f"[{lang}] Subiendo a YouTube…")
        video_id = upload_youtube.upload_video(
            vid,
            title=loc.title,
            description=_enrich_description_seo(loc.description, loc.title, loc.hashtags, is_short=True),
            tags=[h.lstrip("#") for h in loc.hashtags],
            privacy=privacy,
            is_short=True,
            publish_at=publish_at,
        )
        url = f"https://youtube.com/shorts/{video_id}"
        links[lang] = url
        ids[lang] = video_id
        progress(f"[{lang}] ✓ {url}")

    # Persiste links + ids junto al video (para historial y stats)
    yt_path = d / "youtube.json"
    existing = {}
    if yt_path.exists():
        existing = json.loads(yt_path.read_text(encoding="utf-8"))
    existing.update(links)
    existing["_ids"] = {**existing.get("_ids", {}), **ids}
    yt_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    # Mover a uploaded/
    dst = UPLOADED_DIR / slug
    if d != dst:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(d), str(dst))

    if notify and links:
        title = getattr(scripts, "es").title
        head = "🚀 Subido a YouTube" if not publish_at else f"🗓 Programado en YouTube (se publica {publish_at})"
        msg = f"{head}: {title}\n" + "\n".join(
            f"{k.upper()}: {v}" for k, v in links.items()
        )
        msg += "\n\n🎵 Para TikTok: usa la variante _tiktok.mp4 + audio trending."
        _notify_telegram(msg)

    return links


def generate_tt_native(
    topic: str,
    fmt: str | None = None,
    progress: Progress = _noop,
) -> str:
    """Genera un TT-FIRST short (28-34s, 9:16, sin música, comment-bait).
    No bilingüe — TikTok funciona mejor con foco mono-lingüe (ES por defecto).
    """
    from . import atomize  # para render_comment_bait_png

    progress("Generando guion TT-native con Gemini…")
    tt = script.generate_tt_native_script(topic, fmt=fmt)
    slug = tt.slug
    work_dir = PENDING_DIR / slug
    work_dir.mkdir(parents=True, exist_ok=True)
    script.save_tt_native_script(tt, work_dir)
    progress(f"Guion TT listo (slug: {slug} · formato: {tt.format} · {len(tt.segments)} segmentos)")

    progress(f"[es] Sintetizando voz…")
    track = voice.synthesize(tt, work_dir)
    progress(f"  voz: {track.duration_seconds:.1f}s")

    progress(f"[es] Descargando B-roll PORTRAIT de Pexels…")
    timed = align.segment_timings(tt, track)
    anchor = visuals.topic_subject_from_slug(slug)
    visuals.fetch_clips_for_segments(
        timed, work_dir / "broll" / "vertical",
        orientation="portrait", topic_anchor=anchor,
    )

    # Text-hook al inicio (thumbnail_text como gancho visual)
    progress(f"[es] Generando overlays (hook + comment-bait)…")
    hook_text = (tt.thumbnail_text or tt.title or "").strip()
    bait_text = (tt.comment_bait or "¿Lo sabías?").strip()
    hk_png = work_dir / "hook.png"
    bait_png = work_dir / "bait.png"
    graphics.render_hook_overlay_png(hook_text, hk_png)
    atomize.render_comment_bait_png(bait_text, bait_png)

    # Overlays como (png, start, end). Hook 0..2.4s, bait últimos 3s.
    total = track.duration_seconds
    overlays = [
        (hk_png, 0.0, min(2.4, total)),
        (bait_png, max(0.0, total - 3.0), total),
    ]

    progress(f"[es] Componiendo 9:16 con música baja (mood: {tt.music_mood})…")
    out = work_dir / f"video_tt_{tt.format}_es.mp4"
    compose.compose_from_segments(
        track, timed, None, out, vertical=True,
        stat_overlays=overlays,
        music=True, music_mood=tt.music_mood,  # música CC al 7% → voz audible, vídeo autosuficiente
    )
    progress(f"[es] ✓ {out.name}  ({tt.format}) · bait: «{bait_text}»")
    return slug


def publish_long(
    slug: str,
    langs: tuple[str, ...] = ("es", "en"),
    privacy: str = "public",
    progress: Progress = _noop,
    notify: bool = True,
    publish_at: str | None = None,
) -> dict:
    """Sube el LONG-FORM 16:9 a YouTube (NO Short). Devuelve {lang: url}.
    Si publish_at se pasa, se programa (privado + publishAt)."""
    import shutil

    d = None
    for base in (PENDING_DIR, UPLOADED_DIR):
        if (base / slug).exists():
            d = base / slug
            break
    if d is None:
        raise FileNotFoundError(slug)

    scripts = script.load_long_scripts(d)
    links: dict[str, str] = {}
    ids: dict[str, str] = {}
    for lang in langs:
        loc = getattr(scripts, lang)
        vid = d / f"video_long_{lang}.mp4"
        if not vid.exists():
            progress(f"[{lang}] sin long-form, omitido")
            continue
        progress(f"[{lang}] Subiendo long-form a YouTube…")
        court = getattr(loc, "court_source", None)
        video_id = upload_youtube.upload_video(
            vid,
            title=loc.title,
            description=_enrich_description_seo(
                loc.description, loc.title, loc.hashtags,
                is_short=False, court=court,
            ),
            tags=[h.lstrip("#") for h in loc.hashtags],
            privacy=privacy,
            is_short=False,  # ← clave: NO es Short
            publish_at=publish_at,
        )
        url = f"https://youtu.be/{video_id}"
        links[lang] = url
        ids[lang] = video_id
        progress(f"[{lang}] ✓ {url}")

    yt_path = d / "youtube_long.json"
    existing = json.loads(yt_path.read_text(encoding="utf-8")) if yt_path.exists() else {}
    existing.update(links)
    existing["_ids"] = {**existing.get("_ids", {}), **ids}
    yt_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    dst = UPLOADED_DIR / slug
    if d != dst:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(d), str(dst))

    if notify and links:
        title = getattr(scripts, "es").title
        head = "🎬 Long-form subido" if not publish_at else f"🗓 Long-form programado ({publish_at})"
        msg = f"{head}: {title}\n" + "\n".join(f"{k.upper()}: {v}" for k, v in links.items())
        _notify_telegram(msg)
    return links


def recompose_no_subs(slug: str, lang: str = "es") -> Path | None:
    """Recompone el video SIN subtítulos quemados (para TikTok/Reels, que
    autogeneran captions). Mantiene datos overlay + voz + música + caras."""
    from pathlib import Path as _P

    d = None
    for base in (PENDING_DIR, UPLOADED_DIR):
        if (base / slug).exists():
            d = base / slug
            break
    if d is None:
        return None
    scripts = script.load_scripts(d)
    loc = getattr(scripts, lang)
    vj = d / f"voice_{lang}.json"
    if not vj.exists():
        return None
    from .models import VideoClip, VoiceTrack

    track = VoiceTrack.model_validate_json(vj.read_text(encoding="utf-8"))
    track.audio_path = str(d / f"voice_{lang}.mp3")  # corrige ruta tras posible move
    timed = align.segment_timings(loc, track)
    anchor = visuals.topic_subject_from_slug(slug)
    visuals.fetch_clips_for_segments(
        timed, d / "broll" / "vertical", orientation="portrait", topic_anchor=anchor
    )
    # Reusar caras de famoso ya generadas (people/person_*.mp4)
    pdir = d / "people"
    pclips = []
    if pdir.exists():
        for mp4 in sorted(pdir.glob("person_*.mp4")):
            pclips.append(VideoClip(path=str(mp4), duration_seconds=4.0, width=1080, height=1920, keyword="person"))
    if pclips and timed:
        timed[0].clips = [pclips[0]] + timed[0].clips
        body_idx = [i for i, s in enumerate(timed) if s.label.startswith("body")]
        for k, bi in enumerate(body_idx):
            if k + 1 < len(pclips):
                timed[bi].clips = [pclips[k + 1]] + timed[bi].clips
    overlays = make_stat_overlays(timed, loc, d)
    out = d / f"video_{lang}_vertical_nosubs.mp4"
    compose.compose_from_segments(
        track, timed, None, out, vertical=True, stat_overlays=overlays,
        music=True, music_mood=scripts.music_mood,
    )
    return out


def list_history() -> list[dict]:
    """Lista todos los videos generados (pending + uploaded), más recientes primero."""
    items: list[dict] = []
    seen: set[str] = set()
    for base, status in ((UPLOADED_DIR, "uploaded"), (PENDING_DIR, "pending")):
        if not base.exists():
            continue
        for d in base.iterdir():
            if not d.is_dir() or d.name in seen:
                continue
            sj = d / "scripts.json"
            if not sj.exists():
                continue
            seen.add(d.name)
            try:
                s = script.load_scripts(d)
                topic = s.topic
                title_es = s.es.title
                title_en = s.en.title
            except Exception:
                topic, title_es, title_en = d.name, "", ""
            yt = {}
            if (d / "youtube.json").exists():
                try:
                    raw = json.loads((d / "youtube.json").read_text(encoding="utf-8"))
                    yt = {k: v for k, v in raw.items() if not k.startswith("_")}
                except Exception:
                    yt = {}
            langs = [l for l in ("es", "en") if (d / f"video_{l}_vertical.mp4").exists()]
            items.append({
                "slug": d.name,
                "topic": topic,
                "title_es": title_es,
                "title_en": title_en,
                "status": status,
                "langs": langs,
                "youtube": yt,
                "mtime": d.stat().st_mtime,
            })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items
