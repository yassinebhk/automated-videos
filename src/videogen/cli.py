"""CLI principal de videogen.

Comandos:
  videogen create "topic"           → genera video(s) en pending_review/
  videogen review <slug>             → abre la carpeta para previsualizar
  videogen approve <slug>            → mueve a approved/
  videogen publish <slug>            → sube a YT + TikTok
  videogen list                      → lista los videos en pending/approved
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import (
    aimages,
    align,
    compose,
    doctor,
    graphics,
    refine as refine_mod,
    script,
    upload_tiktok,
    upload_youtube,
    veo,
    visuals,
    voice,
)
from .config import APPROVED_DIR, ASSETS_DIR, PENDING_DIR, UPLOADED_DIR, gemini_key
from .models import VoiceTrack

console = Console()


def _slug_dir(base: Path, slug: str) -> Path:
    return base / slug


def _find_slug(slug: str) -> Path:
    for base in (PENDING_DIR, APPROVED_DIR, UPLOADED_DIR):
        d = _slug_dir(base, slug)
        if d.exists():
            return d
    raise click.ClickException(f"slug '{slug}' no encontrado")


def _load_or_make_specs(loc, work_dir):
    """Carga graphic specs cacheados o los genera con Gemini (y cachea)."""
    import json as _json
    path = work_dir / f"graphic_specs_{loc.lang}.json"
    if path.exists():
        data = _json.loads(path.read_text(encoding="utf-8"))
        return [graphics.GraphicSpec.model_validate(s) for s in data]
    specs = graphics.generate_graphic_specs(loc)
    path.write_text(
        _json.dumps([s.model_dump() for s in specs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return specs


def _make_stat_overlays(timed, loc, work_dir):
    """Genera un PNG de stat overlay por segmento. Devuelve lista
    [(png, start, end)] para superponer sobre clips de stock."""
    specs = _load_or_make_specs(loc, work_dir)
    ov_dir = work_dir / "stat_overlays" / loc.lang
    ov_dir.mkdir(parents=True, exist_ok=True)
    overlays = []
    for i, seg in enumerate(timed):
        spec = specs[i] if i < len(specs) else graphics.GraphicSpec(headline="?", sublabel="")
        png = graphics.render_stat_overlay_png(spec, ov_dir / f"ov_{i}.png", theme_idx=i)
        overlays.append((png, seg.start, seg.end))
        console.print(f"  {seg.label:10s} [{spec.headline}] {spec.sublabel}")
    return overlays


def _apply_graphics(timed, loc, work_dir) -> None:
    """Genera escenas de motion graphics y las asigna como clips de cada segmento.
    Reemplaza el B-roll de stock. Muta `timed` in-place."""
    scenes_dir = work_dir / "graphics" / loc.lang
    scenes_dir.mkdir(parents=True, exist_ok=True)
    specs = _load_or_make_specs(loc, work_dir)
    total = len(timed)
    for i, seg in enumerate(timed):
        spec = specs[i] if i < len(specs) else graphics.GraphicSpec(headline="?", sublabel="")
        png = graphics.render_scene(spec, i, total, scenes_dir / f"scene_{i}.png", theme_idx=i)
        clip = graphics.scene_to_clip(png, seg.duration, scenes_dir / f"scene_{i}.mp4")
        seg.clips = [clip]
        console.print(f"  {seg.label:10s} → [{spec.headline}] {spec.sublabel}")


def _apply_ai_images(timed, loc, work_dir, n_per_segment: int = 2) -> None:
    """Modo híbrido: fondo = imágenes IA (Pollinations) relevantes al texto,
    con un stat card (número+label) compuesto encima. Mantiene captions.
    Las imágenes IA se cachean por prompt (compartidas entre idiomas) y se
    generan EN PARALELO (Pollinations es lento por imagen, ~30-80s)."""
    import json as _json
    from concurrent.futures import ThreadPoolExecutor

    specs = _load_or_make_specs(loc, work_dir)
    ai_dir = work_dir / "ai_images"  # cache compartido (prompts language-independent)
    comp_dir = work_dir / "ai_composited" / loc.lang

    # 1) Recolecta todas las tareas de generación de imagen
    gen_tasks = []  # (seg_idx, img_idx, prompt, seed)
    for i, seg in enumerate(timed):
        kws = seg.visual_keywords or [seg.text]
        n = max(1, min(n_per_segment, len(kws)))
        for j in range(n):
            prompt = aimages.build_image_prompt(seg.text, [kws[j % len(kws)]])
            gen_tasks.append((i, j, prompt, i * 10 + j))

    # 2) Genera en paralelo (concurrencia baja para no disparar 402 por ráfaga)
    console.print(f"  generando {len(gen_tasks)} imágenes IA (Pollinations, 3 workers)...")
    images: dict[tuple[int, int], Path] = {}

    def _gen(t):
        i, j, prompt, seed = t
        return (i, j), aimages.generate_image(prompt, ai_dir, seed=seed)

    with ThreadPoolExecutor(max_workers=3) as ex:
        for key, img in ex.map(_gen, gen_tasks):
            images[key] = img

    # 3) Compone stat + Ken Burns. Si una imagen IA falló, FALLBACK a Pexels.
    broll_dir = work_dir / "broll" / "vertical"
    for i, seg in enumerate(timed):
        spec = specs[i] if i < len(specs) else graphics.GraphicSpec(headline="?", sublabel="")
        kws = seg.visual_keywords or [seg.text]
        n = max(1, min(n_per_segment, len(kws)))
        clips = []
        n_ai = 0
        for j in range(n):
            img = images.get((i, j))
            if not img:
                # Fallback: clip de Pexels para que el segmento no quede vacío
                try:
                    fb = visuals.search_clip(kws[j % len(kws)], broll_dir, orientation="portrait")
                except Exception:
                    fb = None
                if fb:
                    clips.append(fb)
                continue
            comp = graphics.composite_stat_over_image(
                img, spec, comp_dir / f"seg{i}_img{j}.jpg", theme_idx=i, show_stat=True
            )
            clip = graphics.scene_to_clip(
                comp, seg.duration / n, comp_dir / f"seg{i}_img{j}.mp4"
            )
            clips.append(clip)
            n_ai += 1
        if clips:
            seg.clips = clips
        console.print(
            f"  {seg.label:10s} → {n_ai} IA + {len(clips)-n_ai} stock  [{spec.headline}]"
        )


@click.group()
def cli():
    """videogen — pipeline de videos automatizados con IA."""


@cli.command(name="reauth")
def reauth_cmd():
    """Re-autoriza YouTube OAuth (borra token caducado + abre navegador).

    Necesario cada ~7 días si el proyecto Google Cloud está en Testing mode
    (Google revoca refresh tokens). Una vez ejecutado: elige cuenta → acepta.
    """
    from . import upload_youtube
    if upload_youtube.TOKEN_FILE.exists():
        upload_youtube.TOKEN_FILE.unlink()
        console.print(f"  [yellow]Token anterior borrado:[/] {upload_youtube.TOKEN_FILE}")
    console.print("[bold cyan]Abriendo navegador para autenticar con Google…[/]")
    try:
        creds = upload_youtube._get_credentials()
        console.print(f"[bold green]✅ Nuevo token guardado en[/] {upload_youtube.TOKEN_FILE}")
        # Verifica con una llamada real
        from . import stats
        ch = stats.fetch_channel_stats() or {}
        console.print(f"  Verificado · {ch.get('subscribers',0)} subs · {ch.get('videos',0)} videos")
    except Exception as e:
        console.print(f"[bold red]❌ Re-auth falló:[/] {e}")
        raise SystemExit(1)


@cli.command(name="doctor")
def doctor_cmd():
    """Verifica que el entorno está listo (ffmpeg, API keys, OAuth, música)."""
    ok = doctor.run_doctor()
    raise SystemExit(0 if ok else 1)


@cli.command(name="ui")
@click.option("--port", default=5005, help="Puerto del servidor web.")
@click.option("--lan", is_flag=True, default=False, help="Accesible desde el móvil en la misma WiFi (escucha en 0.0.0.0).")
def ui_cmd(port: int, lan: bool):
    """Lanza la UI web: prompt → genera → revisa → sube a YouTube.

    Con --lan, accede desde el móvil (misma WiFi) en http://<ip-de-tu-mac>:puerto.
    """
    from . import webapp

    console.print(f"[bold green]videogen studio[/] iniciando…")
    webapp.run(port=port, lan=lan)


@cli.command(name="tt")
@click.argument("topic")
@click.option(
    "--format", "fmt", default=None,
    type=click.Choice(["series", "list", "pov", "curiosity"]),
    help="Formato. Si se omite, Gemini elige el mejor según el topic.",
)
def tt_cmd(topic: str, fmt: str | None):
    """Genera un TikTok EXCLUSIVO (28-34s, 9:16, SIN música, comment-bait).

    NO se sube a YouTube. Está pensado SOLO para TikTok (y derivables a IG/Shorts).
    Pacing TT-first, sin CTA a canal, captions limpios, hashtags niche.
    El usuario añade audio trending al subir.
    """
    from . import service
    slug = service.generate_tt_native(topic, fmt=fmt, progress=console.print)
    console.print(f"\n[bold green]✓ TT-native listo:[/] {slug}")
    console.print("Encuéntralo en: output/pending_review/" + slug + "/")
    console.print("Subir manualmente a TikTok + añade audio trending al final.")


@cli.command(name="atomize-native")
@click.argument("slug")
@click.option("--lang", default="es", type=click.Choice(["es", "en"]))
def atomize_native_cmd(slug: str, lang: str):
    """Atomización TT-FIRST: clips 25-32s, SIN música (audio trending tú), SIN
    CTA a YT (lo penaliza el algoritmo de TT). Comment-bait con pregunta al final.
    """
    from . import atomize
    paths = atomize.atomize_native(slug, lang=lang, progress=console.print)
    console.print(f"\n[bold green]✓ {len(paths)} clips TT-native generados:[/]")
    for p in paths:
        console.print(f"  {p}")


@cli.command(name="atomize")
@click.argument("slug")
@click.option("--lang", default="es", type=click.Choice(["es", "en"]))
@click.option("--handle", default="@waitwhy_ybb", help="Handle de YouTube (para el CTA).")
@click.option("--channel", default="WaitWhy", help="Nombre del canal (para el CTA).")
def atomize_cmd(slug: str, lang: str, handle: str, channel: str):
    """Extrae Shorts promocionales de un LONG-FORM (uno por capítulo).

    Cada clip: 9:16, ~30-45s, con texto-hook del capítulo + CTA «VIDEO COMPLETO EN YT»
    apuntando a tu canal. Súbelos a TikTok/IG/Shorts para captar audiencia al long-form.
    """
    from . import atomize
    paths = atomize.atomize_long(slug, lang=lang, handle=handle, channel=channel,
                                 progress=console.print)
    console.print(f"\n[bold green]✓ {len(paths)} clips generados:[/]")
    for p in paths:
        console.print(f"  {p}")


@cli.command(name="publish-long")
@click.argument("slug")
@click.option(
    "--lang", "langs", multiple=True, type=click.Choice(["es", "en"]),
    default=("es",),  # ES por defecto: rinde más
)
@click.option("--privacy", type=click.Choice(["public", "unlisted", "private"]), default="public")
@click.option("--at", "publish_at", default=None, help="RFC3339 UTC para programar (ej. 2026-05-31T19:00:00Z).")
def publish_long_cmd(slug: str, langs: tuple[str, ...], privacy: str, publish_at: str | None):
    """Sube el LONG-FORM (16:9) a YouTube como vídeo largo (NO Short).
    Con --at programa la publicación a esa hora UTC."""
    from . import service
    links = service.publish_long(slug, langs=langs, privacy=privacy,
                                 progress=console.print, publish_at=publish_at)
    for lang, url in links.items():
        console.print(f"[green]✓[/] {lang.upper()} → {url}")


@cli.command(name="long")
@click.argument("topic")
@click.option("--minutes", default=7, type=int, help="Duración objetivo en minutos (5-10).")
@click.option(
    "--lang", "langs", multiple=True, type=click.Choice(["es", "en"]),
    default=("es", "en"),
)
def long_cmd(topic: str, minutes: int, langs: tuple[str, ...]):
    """Genera un LONG-FORM (16:9, ~7 min) — el formato que monetiza de verdad.

    Estructura: intro + 3-5 capítulos + outro. Subtítulos blandos (no
    quemados, YT los autogenera) y timestamps automáticos en la descripción.
    """
    from . import service
    slug = service.generate_long(topic, target_minutes=minutes, langs=langs, progress=console.print)
    console.print(f"\n[bold green]✓ Long-form listo:[/] {slug}")
    console.print(f"Revisa: [bold]videogen review {slug}[/]")
    console.print("Para subir a YouTube como long-form (NO Short):")
    console.print(f"  [bold].venv/bin/videogen publish-long {slug}[/]  (en breve)")
    console.print("O mediante la UI/bot cuando esté integrado.")


@cli.command(name="bot")
def bot_cmd():
    """Lanza el bot de Telegram (prompt→genera→aprueba→sube + resumen diario)."""
    from . import telegram_bot

    telegram_bot.run()


@cli.command()
@click.argument("topic")
@click.option(
    "--horizontal/--no-horizontal",
    default=False,
    help="Genera también la versión 16:9 para YouTube long-form.",
)
@click.option(
    "--lang",
    "langs",
    multiple=True,
    type=click.Choice(["es", "en"]),
    default=("es", "en"),
)
@click.option(
    "--veo-hook/--no-veo-hook",
    default=False,
    help="Genera los primeros ~5s del video con Veo 3.1 (Google AI Studio, free tier).",
)
@click.option(
    "--graphics",
    "use_graphics",
    is_flag=True,
    default=False,
    help="Usa motion graphics (infografías animadas) en vez de B-roll de stock. Ideal para videos de datos.",
)
@click.option(
    "--ai-images",
    "use_ai_images",
    is_flag=True,
    default=False,
    help="Fondo = imágenes IA (Pollinations) + stat overlay + captions. El modo híbrido.",
)
@click.option(
    "--stats",
    "use_stats",
    is_flag=True,
    default=False,
    help="GRATIS: stock Pexels + overlays de datos + captions.",
)
@click.option(
    "--ai-hero/--no-ai-hero",
    default=False,
    help="Genera un frame de imagen IA (Pollinations, gratis) al inicio del teaser. Se omite si el topic es de un famoso (se usa su foto real).",
)
def create(
    topic: str,
    horizontal: bool,
    langs: tuple[str, ...],
    veo_hook: bool,
    use_graphics: bool,
    use_ai_images: bool,
    use_stats: bool,
    ai_hero: bool,
):
    """Genera videos a partir de un topic. Output: output/pending_review/<slug>/"""
    console.rule("[bold cyan]1. Script con Claude")
    scripts = script.generate_scripts(topic)
    slug = scripts.slug
    work_dir = _slug_dir(PENDING_DIR, slug)
    work_dir.mkdir(parents=True, exist_ok=True)
    script.save_scripts(scripts, work_dir)
    console.print(f"  slug: [bold]{slug}[/]  topic: {topic}")

    if veo_hook and not gemini_key():
        console.print("  [yellow]warn:[/] --veo-hook pedido pero GEMINI_API_KEY no está; usando Pexels")
        veo_hook = False

    broll_dir = work_dir / "broll"
    veo_clip = None
    if veo_hook:
        console.rule("[bold magenta]Veo: hook clip (compartido entre idiomas)")
        # Usa el hook del idioma EN si está disponible (Veo entiende mejor inglés)
        hook_loc = scripts.en if "en" in langs else getattr(scripts, langs[0])
        prompt_v = veo.build_visual_prompt(
            hook_loc.hook.text, hook_loc.hook.visual_keywords
        )
        veo_clip = veo.generate_hook_clip(prompt_v, work_dir / "veo")

    hero_clip = None
    if ai_hero and not scripts.subject_person.strip():
        console.rule("[bold magenta]Imagen IA del teaser (Pollinations, gratis)")
        hero_clip = aimages.generate_hero_clip(scripts, work_dir)
        console.print("  [green]✓[/] hero IA" if hero_clip else "  [yellow]Pollinations falló, sin hero[/]")

    for lang in langs:
        loc = getattr(scripts, lang)
        console.rule(f"[bold cyan]2. Voz ElevenLabs ({lang})")
        track = voice.synthesize(loc, work_dir)
        console.print(f"  audio: {track.audio_path}  ({track.duration_seconds:.1f}s)")

        timed = align.segment_timings(loc, track)
        stat_overlays = None
        if use_ai_images:
            console.rule(f"[bold cyan]3. Imágenes IA + stat overlay ({lang})")
            _apply_ai_images(timed, loc, work_dir)
        elif use_graphics:
            console.rule(f"[bold cyan]3. Motion graphics por segmento ({lang})")
            _apply_graphics(timed, loc, work_dir)
        else:
            console.rule(f"[bold cyan]3. Alineamiento + B-roll por segmento ({lang})")
            anchor = visuals.topic_subject_from_slug(scripts.slug)
            visuals.fetch_clips_for_segments(
                timed,
                broll_dir / "vertical",
                orientation="portrait",
                topic_anchor=anchor,
            )
            if veo_clip and timed:
                timed[0].clips = [veo_clip] + timed[0].clips
            if hero_clip and timed:
                timed[0].clips = [hero_clip] + timed[0].clips
            for seg in timed:
                console.print(
                    f"  {seg.label:10s} {seg.duration:5.1f}s  → {len(seg.clips)} clip(s)"
                )
            if use_stats:
                console.rule(f"[bold cyan]Overlays de datos ({lang})")
                stat_overlays = _make_stat_overlays(timed, loc, work_dir)

        console.rule(f"[bold cyan]4. Composición vertical ({lang})")
        ass_v = None if use_graphics else compose.build_caption_ass(
            track, work_dir / f"captions_{lang}_v.ass", vertical=True
        )
        out_v = work_dir / f"video_{lang}_vertical.mp4"
        compose.compose_from_segments(
            track, timed, ass_v, out_v, vertical=True,
            stat_overlays=stat_overlays, music_mood=scripts.music_mood,
        )
        console.print(f"  [green]✓[/] {out_v.name}")

        if horizontal:
            clips_h = visuals.fetch_broll(
                keywords, broll_dir / "horizontal", orientation="landscape"
            )
            console.rule(f"[bold cyan]5. Composición horizontal ({lang})")
            ass_h = compose.build_caption_ass(
                track, work_dir / f"captions_{lang}_h.ass", vertical=False
            )
            out_h = work_dir / f"video_{lang}_horizontal.mp4"
            compose.compose(track, clips_h or clips_v, ass_h, out_h, vertical=False)
            console.print(f"  [green]✓[/] {out_h.name}")

    console.rule("[bold green]Listo")
    console.print(f"Revisa: [bold]videogen review {slug}[/]")
    console.print(f"Aprobar: [bold]videogen approve {slug}[/]")
    console.print(f"Publicar: [bold]videogen publish {slug}[/]")


@cli.command(name="list")
def list_videos():
    """Lista videos en pending / approved / uploaded."""
    table = Table(title="videogen — estado")
    table.add_column("Slug")
    table.add_column("Estado")
    table.add_column("Archivos")
    for base, label in [
        (PENDING_DIR, "pending"),
        (APPROVED_DIR, "approved"),
        (UPLOADED_DIR, "uploaded"),
    ]:
        for d in sorted(base.iterdir() if base.exists() else []):
            if not d.is_dir():
                continue
            mp4s = list(d.glob("*.mp4"))
            table.add_row(d.name, label, ", ".join(m.name for m in mp4s))
    console.print(table)


@cli.command()
@click.argument("slug")
@click.option(
    "--lang",
    "langs",
    multiple=True,
    type=click.Choice(["es", "en"]),
    default=("es", "en"),
)
@click.option(
    "--keep-keywords",
    is_flag=True,
    default=False,
    help="No re-pedir keywords a Gemini, solo recomponer con los actuales.",
)
@click.option(
    "--veo-hook/--no-veo-hook",
    default=False,
    help="Genera el clip del hook con Veo (garantiza first frame on-topic).",
)
@click.option(
    "--graphics",
    "use_graphics",
    is_flag=True,
    default=False,
    help="Recompone con motion graphics planos en vez de B-roll de stock.",
)
@click.option(
    "--ai-images",
    "use_ai_images",
    is_flag=True,
    default=False,
    help="Fondo = imágenes IA (Pollinations) + stat overlay + captions. El modo híbrido.",
)
@click.option(
    "--stats",
    "use_stats",
    is_flag=True,
    default=False,
    help="GRATIS: stock Pexels + overlays de datos (números grandes) + captions.",
)
@click.option(
    "--revoice",
    is_flag=True,
    default=False,
    help="Re-sintetiza la voz (nueva voz/velocidad) sin tocar el guion.",
)
def refine(
    slug: str,
    langs: tuple[str, ...],
    keep_keywords: bool,
    veo_hook: bool,
    use_graphics: bool,
    use_ai_images: bool,
    use_stats: bool,
    revoice: bool,
):
    """Refina keywords visuales + recompone sin regenerar voz.

    Útil cuando el contenido del script te convence pero las imágenes no.
    Reutiliza voice_*.mp3 existentes (no consume quota de ElevenLabs).
    """
    d = _find_slug(slug)
    scripts = script.load_scripts(d)

    if not keep_keywords:
        console.rule("[bold cyan]Refinando keywords visuales con Gemini")
        scripts = refine_mod.refine_visual_keywords(scripts)
        script.save_scripts(scripts, d)
        console.print("  [green]✓[/] keywords actualizadas en scripts.json")

    if veo_hook and not gemini_key():
        console.print("  [yellow]warn:[/] --veo-hook pedido pero sin GEMINI_API_KEY")
        veo_hook = False

    veo_clip = None
    if veo_hook:
        console.rule("[bold magenta]Veo: hook clip on-topic")
        # Usa el hook EN para Veo (mejor compresión en prompt)
        hook_loc = scripts.en
        prompt_v = veo.build_visual_prompt(
            hook_loc.hook.text, hook_loc.hook.visual_keywords
        )
        console.print(f"  prompt: {prompt_v[:120]}...")
        veo_clip = veo.generate_hook_clip(prompt_v, d / "veo")
        if veo_clip:
            console.print(f"  [green]✓[/] Veo hook generado: {veo_clip.path}")
        else:
            console.print("  [yellow]Veo falló o rate-limited, usando Pexels[/]")

    broll_dir = d / "broll"
    for lang in langs:
        loc = getattr(scripts, lang)
        voice_json = d / f"voice_{lang}.json"
        if revoice:
            console.rule(f"[bold cyan]Re-sintetizando voz ({lang})")
            track = voice.synthesize(loc, d)
        elif voice_json.exists():
            track = VoiceTrack.model_validate_json(voice_json.read_text(encoding="utf-8"))
        else:
            console.print(f"  [yellow]skip {lang}[/]: no hay voice_{lang}.json (usa --revoice)")
            continue

        timed = align.segment_timings(loc, track)
        stat_overlays = None
        if use_ai_images:
            console.rule(f"[bold cyan]Imágenes IA + stat overlay por segmento ({lang})")
            _apply_ai_images(timed, loc, d)
        elif use_graphics:
            console.rule(f"[bold cyan]Motion graphics por segmento ({lang})")
            _apply_graphics(timed, loc, d)
        else:
            console.rule(f"[bold cyan]Stock Pexels por segmento ({lang})")
            anchor = visuals.topic_subject_from_slug(scripts.slug)
            visuals.fetch_clips_for_segments(
                timed,
                broll_dir / "vertical",
                orientation="portrait",
                topic_anchor=anchor,
            )
            if veo_clip and timed:
                timed[0].clips = [veo_clip] + timed[0].clips
            for seg in timed:
                console.print(
                    f"  {seg.label:10s} {seg.duration:5.1f}s  → {len(seg.clips)} clip(s)"
                )
            if use_stats:
                console.rule(f"[bold cyan]Overlays de datos ({lang})")
                stat_overlays = _make_stat_overlays(timed, loc, d)

        console.rule(f"[bold cyan]Recomponiendo ({lang})")
        # graphics plano no lleva captions; ai-images y stock sí
        ass = None if use_graphics else compose.build_caption_ass(
            track, d / f"captions_{lang}_v.ass", vertical=True
        )
        out = d / f"video_{lang}_vertical.mp4"
        compose.compose_from_segments(
            track, timed, ass, out, vertical=True,
            stat_overlays=stat_overlays, music_mood=scripts.music_mood,
        )
        console.print(f"  [green]✓[/] {out.name}")


@cli.command(name="crosspost")
@click.argument("slug")
@click.option("--lang", default="es", type=click.Choice(["es", "en"]))
def crosspost_cmd(slug: str, lang: str):
    """Abre los uploaders de TikTok/IG/FB/Pinterest/Snapchat + caption al portapapeles."""
    from . import crosspost
    d = _find_slug(slug)
    scripts = script.load_scripts(d)
    loc = getattr(scripts, lang)
    crosspost.open_desktop(d, lang, loc)
    console.print("[green]✓[/] Uploaders abiertos + caption copiado. Arrastra el archivo en cada red.")


@cli.command()
@click.argument("slug")
def review(slug: str):
    """Abre la carpeta del slug en Finder para previsualizar los MP4."""
    d = _find_slug(slug)
    if sys.platform == "darwin":
        subprocess.run(["open", str(d)])
    console.print(f"Carpeta abierta: {d}")


@cli.command()
@click.argument("slug")
def approve(slug: str):
    """Mueve el slug de pending_review a approved."""
    src = _slug_dir(PENDING_DIR, slug)
    if not src.exists():
        raise click.ClickException(f"{slug} no está en pending_review")
    dst = _slug_dir(APPROVED_DIR, slug)
    shutil.move(str(src), str(dst))
    console.print(f"[green]✓[/] {slug} → approved/")


@cli.command()
@click.argument("slug")
@click.option(
    "--platform",
    multiple=True,
    type=click.Choice(["youtube", "tiktok"]),
    default=("youtube", "tiktok"),
)
@click.option(
    "--lang", "langs", multiple=True, type=click.Choice(["es", "en"]), default=("es", "en")
)
@click.option("--privacy", type=click.Choice(["public", "unlisted", "private"]), default="public")
def publish(slug: str, platform: tuple[str, ...], langs: tuple[str, ...], privacy: str):
    """Sube el video a las plataformas seleccionadas."""
    d = _find_slug(slug)
    scripts = script.load_scripts(d)

    for lang in langs:
        loc = getattr(scripts, lang)
        video_v = d / f"video_{lang}_vertical.mp4"
        if not video_v.exists():
            console.print(f"  [yellow]skip {lang}[/]: {video_v.name} no existe")
            continue

        if "youtube" in platform:
            console.rule(f"[bold red]YouTube ({lang}) — Short")
            vid = upload_youtube.upload_video(
                video_v,
                title=loc.title,
                description=loc.description,
                tags=[h.lstrip("#") for h in loc.hashtags],
                privacy=privacy,
                is_short=True,
            )
            console.print(f"  [green]✓[/] https://youtube.com/shorts/{vid}")

            video_h = d / f"video_{lang}_horizontal.mp4"
            if video_h.exists():
                console.rule(f"[bold red]YouTube ({lang}) — Long-form")
                vid_h = upload_youtube.upload_video(
                    video_h,
                    title=loc.title,
                    description=loc.description,
                    tags=[h.lstrip("#") for h in loc.hashtags],
                    privacy=privacy,
                    is_short=False,
                )
                console.print(f"  [green]✓[/] https://youtu.be/{vid_h}")

        if "tiktok" in platform:
            console.rule(f"[bold magenta]TikTok ({lang})")
            upload_tiktok.open_uploader(video_v, loc.title, loc.hashtags)

    # Mover a uploaded/
    dst = _slug_dir(UPLOADED_DIR, slug)
    if d != dst:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(d), str(dst))
        console.print(f"[green]✓[/] {slug} → uploaded/")


# --------------------------------------------------------------------------- #
# One-shot entrypoints para GitHub Actions (sin loop bot ni PTB JobQueue)
# --------------------------------------------------------------------------- #

@cli.command(name="autogen-once")
def autogen_once_cmd():
    """Genera el Short diario, lo programa y notifica. Idempotente (no repite hoy)."""
    from . import runner
    runner.run_autogen()


@cli.command(name="longgen-once")
def longgen_once_cmd():
    """Genera long-form semanal + 5 clips atomizados. Idempotente (no repite semana)."""
    from . import runner
    runner.run_longgen()


@cli.command(name="hourly-catchup")
def hourly_catchup_cmd():
    """Chequea si toca autogen hoy y dispara si aún no se ha hecho."""
    from . import runner
    runner.run_hourly_catchup()


@cli.command(name="weekly-catchup")
def weekly_catchup_cmd():
    """Chequea si toca longgen esta semana y dispara si aún no se ha hecho."""
    from . import runner
    runner.run_weekly_catchup()


@cli.command(name="daily-summary")
def daily_summary_cmd():
    """Manda el resumen diario a Telegram (stats + charts + ideas)."""
    from . import runner
    runner.run_daily_summary()


@cli.command(name="bluesky-growth")
def bluesky_growth_cmd():
    """Ejecuta el growth loop de Bluesky (follows + likes + reposts)."""
    from . import bluesky_growth
    bluesky_growth.run_growth_loop(dry_run=False)


@cli.command(name="mastodon-growth")
def mastodon_growth_cmd():
    """Ejecuta el growth loop de Mastodon (follows + favs + reblogs)."""
    from . import mastodon_growth
    mastodon_growth.run_growth_loop(dry_run=False)


@cli.command(name="dispatch")
@click.option("--cmd", required=True, help="Comando (autogen|longgen|snapshot|atomize|send|ideas|stats|help|start)")
@click.option("--args", "args_text", default="", help="Argumentos textuales del comando")
def dispatch_cmd(cmd: str, args_text: str):
    """Ejecuta un comando del bot como si el usuario lo hubiese enviado.

    Usado por el webhook Vercel: Telegram POST → Vercel → repository_dispatch →
    Action → `videogen dispatch --cmd autogen`.
    """
    from . import runner
    runner.dispatch_command(cmd, args_text)


if __name__ == "__main__":
    cli()
