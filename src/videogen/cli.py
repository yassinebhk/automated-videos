"""CLI principal de videogen.

Comandos:
  videogen create "topic"           → genera video(s) en pending_review/
  videogen review <slug>             → abre la carpeta para previsualizar
  videogen approve <slug>            → mueve a approved/
  videogen publish <slug>            → sube a YT + TikTok
  videogen list                      → lista los videos en pending/approved
"""
from __future__ import annotations

import json
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
from .config import APPROVED_DIR, ASSETS_DIR, PENDING_DIR, ROOT, UPLOADED_DIR, gemini_key
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
@click.option("--channel", "channel_prefix", type=str, default="",
              help="Prefix del canal (ej. YT_IA, YT_TAX). Vacío = WaitWhy default")
def reauth_cmd(channel_prefix: str):
    """Re-autoriza YouTube OAuth. Abre navegador para autenticar cuenta Google.

    Necesario cada ~7 días si el proyecto Google Cloud está en Testing mode
    (Google revoca refresh tokens con invalid_grant).

    Uso:
      videogen reauth                       → WaitWhy default
      videogen reauth --channel YT_IA       → IA Autónomos
      videogen reauth --channel YT_TAX      → TaxHack ES

    IMPORTANTE: en el navegador elige la cuenta Google del CANAL correcto
    (no la cuenta principal). Tras completar: pega el nuevo refresh_token
    al secret GH correspondiente (YT_IA_REFRESH_TOKEN, YT_TAX_REFRESH_TOKEN, etc).
    """
    import os
    from . import upload_youtube
    prev = os.environ.get("YT_CHANNEL_PREFIX", "")
    if channel_prefix:
        os.environ["YT_CHANNEL_PREFIX"] = channel_prefix
        console.print(f"[cyan]Canal: {channel_prefix} (necesitarás elegir la cuenta Google del canal)[/]")
    else:
        os.environ.pop("YT_CHANNEL_PREFIX", None)
        console.print("[cyan]Canal: WaitWhy default[/]")

    try:
        if channel_prefix:
            # Multi-canal: OAuth directo con InstalledAppFlow.
            # CRÍTICO: usar los CLIENT_ID/SECRET DEL CANAL (env vars),
            # NO el client_secret.json principal (bug 21/09: refresh_token
            # generado con client principal NO funciona con YT_X_CLIENT_ID
            # distinto → invalid_grant Bad Request al usar).
            cid_env = f"{channel_prefix}_CLIENT_ID"
            csec_env = f"{channel_prefix}_CLIENT_SECRET"
            cid = os.environ.get(cid_env, "").strip()
            csec = os.environ.get(csec_env, "").strip()

            console.print(f"[yellow]Modo multi-canal: OAuth directo para {channel_prefix}[/]")
            if not (cid and csec):
                console.print(f"[bold red]❌ Faltan env vars {cid_env} + {csec_env}[/]")
                console.print(f"[yellow]Cópialos de GH Secrets y expórtalos ANTES de correr reauth:[/]")
                console.print(f"[cyan]  export {cid_env}='...'[/]")
                console.print(f"[cyan]  export {csec_env}='...'[/]")
                console.print(f"[cyan]  .venv/bin/videogen reauth --channel {channel_prefix}[/]")
                console.print(f"[dim]O añádelos a tu .env local en la raíz del repo.[/]")
                raise SystemExit(1)

            # Construir client_config inline (no depende de client_secret.json)
            client_config = {
                "installed": {
                    "client_id": cid,
                    "client_secret": csec,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
            import google_auth_oauthlib.flow
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
                client_config, upload_youtube.SCOPES,
            )
            console.print(f"[dim]client_id: {cid}[/]")
            console.print("[bold cyan]Abriendo navegador — elige la cuenta Google del canal correcto[/]")
            creds = flow.run_local_server(port=0)
            console.print(f"[bold green]✅ OAuth completado[/]")
            console.print(f"[bold yellow]⚠ COPIA este refresh_token al secret GH {channel_prefix}_REFRESH_TOKEN:[/]")
            console.print(f"[dim]MUY IMPORTANTE: pega en UNA SOLA LÍNEA sin espacios/saltos.[/]")
            console.print(f"[dim]Longitud esperada: {len(creds.refresh_token)} caracteres.[/]")
            console.print("")
            console.print("──── COPIAR DESDE AQUÍ (línea única): ────")
            # sys.stdout directo (no rich) para evitar wrapping visual
            import sys as _sys
            _sys.stdout.write(creds.refresh_token + "\n")
            _sys.stdout.flush()
            console.print("──── HASTA AQUÍ ────")
            console.print("")
            console.print(f"[dim]NO actualizar CLIENT_ID/SECRET (ya son los correctos del canal)[/]")
            # También lo escribo a un file para eliminar dudas
            _tmp = ROOT / "output" / f".reauth_token_{channel_prefix}.txt"
            _tmp.parent.mkdir(parents=True, exist_ok=True)
            _tmp.write_text(creds.refresh_token, encoding="utf-8")
            console.print(f"[dim]También guardado en: {_tmp} (haz `cat` para copiar limpio)[/]")
            return

        # Modo WaitWhy default (comportamiento original)
        if upload_youtube.TOKEN_FILE.exists():
            upload_youtube.TOKEN_FILE.unlink()
            console.print(f"  [yellow]Token WaitWhy anterior borrado:[/] {upload_youtube.TOKEN_FILE}")
        console.print("[bold cyan]Abriendo navegador para autenticar con Google…[/]")
        creds = upload_youtube._get_credentials()
        console.print(f"[bold green]✅ OAuth completado[/]")
        console.print(f"[green]Guardado en {upload_youtube.TOKEN_FILE}[/]")
        from . import stats
        ch = stats.fetch_channel_stats() or {}
        console.print(f"  Verificado · {ch.get('subscribers',0)} subs · {ch.get('videos',0)} videos")
    except Exception as e:
        console.print(f"[bold red]❌ Re-auth falló:[/] {e}")
        raise SystemExit(1)
    finally:
        if prev:
            os.environ["YT_CHANNEL_PREFIX"] = prev
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)


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


@cli.command(name="first-comment-catchup")
def first_comment_catchup_cmd():
    """Postea first-comment en videos públicos que aún no lo tengan.
    Corre cada 2h para arreglar el bug 08-17 (scheduled videos → 403)."""
    from . import first_comment
    result = first_comment.catchup_pending_first_comments(max_videos=20)
    print(f"  first-comment catchup: {result}")


@cli.command(name="engagement")
@click.option("--dry-run", is_flag=True, help="No postea, solo enseña qué haría")
@click.option("--max", "max_total", type=int, default=15,
              help="Max replies por pase (default 15, tope duro 30 para no spam)")
def engagement_cmd(dry_run: bool, max_total: int):
    """Auto-reply a comentarios de videos publicados 6-72h atrás.
    Palanca YPP: cada reply del creador → notify al viewer → CTR de vuelta.
    Anti-spam: max 3 replies/video, ledger persistente, templates rotativos."""
    from . import engagement
    max_total = min(max_total, 30)
    result = engagement.run_engagement_pass(max_total=max_total, dry_run=dry_run)
    print(f"  engagement pass: {result}")


@cli.command(name="ig-engagement")
@click.option("--dry-run", is_flag=True, help="No postea, solo enseña qué haría")
@click.option("--max", "max_total", type=int, default=15,
              help="Max replies por pase (default 15, tope duro 30)")
def ig_engagement_cmd(dry_run: bool, max_total: int):
    """Auto-reply a comentarios de reels IG (@waitwhy_) últimas 48h.
    Solo cuenta principal. Anti-spam: 3/reel, ledger persistente."""
    from . import ig_engagement
    max_total = min(max_total, 30)
    result = ig_engagement.run_ig_engagement_pass(max_total=max_total, dry_run=dry_run)
    print(f"  ig engagement pass: {result}")


@cli.command(name="threads-engagement")
@click.option("--dry-run", is_flag=True, help="No postea, solo enseña qué haría")
def threads_engagement_cmd(dry_run: bool):
    """Auto-reply Threads SOLO a menciones directas (@waitwhy_).
    Máx 5/día. Modo defensivo — Threads es hipersensible al spam."""
    from . import threads_engagement
    result = threads_engagement.run_threads_engagement_pass(dry_run=dry_run)
    print(f"  threads engagement pass: {result}")


@cli.command(name="bsky-reply-boost")
@click.option("--live", is_flag=True,
              help="Postear de verdad. Sin este flag = dry-run (safe).")
def bsky_reply_boost_cmd(live: bool):
    """Reply-boost Bluesky a threads trending ES (true crime/corrupción).
    MAX 3/día, cuentas <5k followers, posts >=8 likes, aportando dato + fuente."""
    from . import bluesky_reply_boost
    result = bluesky_reply_boost.run_bsky_reply_boost(dry_run=not live)
    print(f"  bsky reply-boost pass: {result}")


@cli.command(name="playlists-catchup")
def playlists_catchup_cmd():
    """Sincroniza retroactivamente todos los videos uploaded/ a sus playlists
    de case_key. Crea playlists YT para casos con >=3 videos. Idempotente."""
    from . import playlists_manager
    result = playlists_manager.catchup_all_cases()
    print(f"  playlists catchup: {result}")


@cli.command(name="rankings-refresh")
@click.option("--to-year", type=int, default=0,
              help="Año fin (default = año actual - 1, WB publica con delay)")
def rankings_refresh_cmd(to_year: int):
    """Refresca datasets World Bank de rankings a año actual.

    Itera sobre todos los `dataset_key` que empiecen por `wb_` en topic_pool
    y refetch con to_year actualizado. Guarda en output/ranking_datasets/.
    Los bundled_data/*.json quedan como fallback si el fetch falla."""
    import re as _re
    from datetime import datetime as _dt, timezone as _tz
    from .ranking import topic_pool
    from .ranking import datasets_fetcher

    year_end = to_year or (_dt.now(_tz.utc).year - 1)
    topics = topic_pool.all_topics()
    wb_topics = [t for t in topics
                 if isinstance(t.get("dataset_key"), str) and t["dataset_key"].startswith("wb_")]
    console.print(f"[cyan]Refrescando {len(wb_topics)} datasets WB → hasta año {year_end}[/]")
    ok = fail = 0
    for t in wb_topics:
        dkey_old = t["dataset_key"]
        # wb_NY_GDP_MKTP_CD_2000_2024 → indicator=NY.GDP.MKTP.CD, from=2000, to=2024
        m = _re.match(r"wb_(.+)_(\d{4})_(\d{4})", dkey_old)
        if not m:
            console.print(f"  [yellow]skip malformed[/] {dkey_old}")
            continue
        indicator = m.group(1).replace("_", ".")
        from_year = int(m.group(2))
        try:
            result = datasets_fetcher.fetch_worldbank_top(
                indicator, from_year=from_year, to_year=year_end, top_n=10)
            if result:
                console.print(f"  [green]✓[/] {indicator} · {from_year}-{max(result['years'])} · {len(result['items'])} items")
                ok += 1
            else:
                console.print(f"  [red]✗[/] {indicator} fetch returned None")
                fail += 1
        except Exception as e:
            console.print(f"  [red]✗[/] {indicator}: {type(e).__name__}: {e}")
            fail += 1
    console.print(f"\n[bold]{ok} ok · {fail} fail[/]")


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


@cli.command(name="x-growth")
def x_growth_cmd():
    """Ejecuta el growth loop de X (follows + likes de cuentas ES relevantes)."""
    from . import x_growth
    x_growth.run_growth_loop(dry_run=False)


@cli.command(name="ambient-once")
def ambient_once_cmd():
    """Genera + sube 1 video ambient/relax al canal YT_AMBIENT_*."""
    from .ambient import pipeline
    result = pipeline.run_once()
    if not result:
        raise SystemExit(1)
    print(json.dumps(result, indent=2, default=str))


@cli.command(name="ranking-datasets-refresh")
def ranking_datasets_refresh_cmd():
    """Refresh datasets REALES para TopRanking (World Bank + más).

    Cron weekly. Descarga últimos datos oficiales y cachea en
    output/ranking_datasets/. Los videos ranking cogen de cache.
    """
    from .ranking import datasets_fetcher
    result = datasets_fetcher.refresh_all()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


@cli.command(name="waitwhy-analyze")
def waitwhy_analyze_cmd():
    """Analiza performance WaitWhy: top10 videos + ranking por categoría.

    Fetch YT API, categoriza por keywords (corrupción, crimen, estafa, robo,
    casos famosos ES, etc), ordena por views/día. Notif Telegram con
    recomendación pivote."""
    from . import waitwhy_analyze
    result = waitwhy_analyze.analyze()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


@cli.command(name="yt-cookies-check")
def yt_cookies_check_cmd():
    """Diagnóstico específico YT_COOKIES: verifica secret + archivo + test yt-dlp.

    Notifica a Telegram con causa concreta:
      - Secret vacío
      - Archivo /tmp/yt_cookies.txt no creado
      - Formato inválido (no empieza por # Netscape)
      - Cookies expiradas (yt-dlp devuelve "Sign in to confirm you're not a bot")
      - Cookies OK (test download 1 short público funciona)
    """
    import os, subprocess, tempfile, json as _json, urllib.request
    lines = ["🍪 <b>YT_COOKIES check</b>"]

    # 1. Env var
    env_val = os.environ.get("YT_COOKIES", "")
    if env_val:
        lines.append(f"✅ env YT_COOKIES presente ({len(env_val)} chars)")
    else:
        lines.append("⚠️ env YT_COOKIES vacía en este step (revisar propagación).")

    # 2. Archivo (puede existir aunque env esté vacía si el step 1 lo escribió)
    p = "/tmp/yt_cookies.txt"
    if not os.path.exists(p):
        lines.append(f"❌ {p} NO existe.")
        lines.append("   Fix: verifica secret YT_COOKIES_V2 (nombre exacto, no vacío) + step 'Reconstruir .env' del workflow.")
    else:
        # Reset lógica — el archivo existe, el test yt-dlp es lo que importa
        env_val = env_val or "file-only"
        if True:
            sz = os.path.getsize(p)
            lines.append(f"✅ {p} existe ({sz} bytes)")

            # 3. Formato
            with open(p) as f:
                head = f.read(200)
            if not head.startswith("# Netscape"):
                lines.append(f"❌ Formato INVÁLIDO: empieza por <code>{head[:40]}...</code>")
                lines.append("   Fix: exporta cookies con extensión 'Get cookies.txt LOCALLY' (Netscape).")
            else:
                lines.append("✅ formato Netscape OK")

                # 4. Test yt-dlp — probar 3 player_clients (algunos necesitan
                # PO Token con cookies, otros no). Usamos MrBeast short (activo).
                test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                strategies = [
                    ("android", ["--extractor-args", "youtube:player_client=android"]),
                    ("tv_embedded", ["--extractor-args", "youtube:player_client=tv_embedded"]),
                    ("web (default)", []),  # sin forzar client
                ]
                success = False
                for name, extra in strategies:
                    with tempfile.TemporaryDirectory() as td:
                        out_path = f"{td}/test.mp4"
                        # -f: limita a 1080p max. Sin límite YT servía 4K (485MB)
                        # y se agotaba timeout 90s (15/09).
                        cmd = ["yt-dlp",
                               "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
                               "--merge-output-format", "mp4",
                               "-o", out_path,
                               "--no-warnings", "--no-playlist",
                               "--cookies", p,
                               *extra,
                               test_url]
                        try:
                            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                            if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 100_000:
                                lines.append(f"✅ TEST download OK con player={name} ({os.path.getsize(out_path)//1024}KB)")
                                lines.append("<b>Cookies funcionan.</b> Backfill IG debería funcionar.")
                                success = True
                                break
                            else:
                                err = (r.stderr or r.stdout or "")[:200]
                                lines.append(f"❌ player={name} rc={r.returncode}: <code>{err[:150]}</code>")
                        except Exception as e:
                            lines.append(f"❌ player={name} exception: {type(e).__name__}")

                if not success:
                    # Última tentativa diagnóstica: listar formatos disponibles
                    lines.append("\n<b>Diagnóstico --list-formats:</b>")
                    try:
                        r = subprocess.run(
                            ["yt-dlp", "--list-formats", "--cookies", p,
                             "--no-warnings", test_url],
                            capture_output=True, text=True, timeout=45,
                        )
                        fmts = (r.stdout or r.stderr or "")[-800:]
                        lines.append(f"<code>{fmts}</code>")
                    except Exception as e:
                        lines.append(f"list-formats exception: {type(e).__name__}")

    text = "\n".join(lines)
    print(text)
    tok = os.environ.get("TELEGRAM_BOT_TOKEN"); chat = os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                data=_json.dumps({"chat_id": int(chat), "text": text,
                                    "parse_mode": "HTML"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:
            print(f"tg notify fail: {e}")


@cli.command(name="ig-clean")
@click.option("--filter", "filter_", type=str, default="",
              help="Substring(s) del slug a borrar. Coma = OR (ej. 'padel,fractal,motor')")
@click.option("--not-whitelisted", is_flag=True,
              help="Borra reels cuyo slug NO empiece por ningún prefijo whitelist "
                   "(waitwhy/criminopatia/legal/ayudas/pov/trabajos)")
@click.option("--older-than-days", type=int, default=0,
              help="Solo borra reels de hace >N días (0 = todos)")
@click.option("--dry-run", is_flag=True, help="Solo lista, no borra")
@click.option("--yes", is_flag=True, help="Confirma sin preguntar")
def ig_clean_cmd(filter_: str, not_whitelisted: bool, older_than_days: int,
                 dry_run: bool, yes: bool):
    """Borra reels IG del log local via DELETE /{media_id}.

    Ejemplos:
      videogen ig-clean --filter padel --dry-run                → lista padel
      videogen ig-clean --filter tax,legal,motor --yes          → borra 3 nichos
      videogen ig-clean --not-whitelisted --dry-run             → lista fuera-whitelist
      videogen ig-clean --not-whitelisted --yes                 → limpieza histórica
      videogen ig-clean --older-than-days 7 --yes               → borra >7 días

    Sólo borra reels registrados en output/ig_publish_log.json como
    'ok' (con media_id). Actualiza el log tras cada borrado.
    """
    from .crosspost_full import IG_WHITELIST_PREFIXES
    from datetime import datetime, timezone, timedelta
    from .instagram_poster import IG_LOG_PATH, delete_ig_reel

    # Env var overrides para workflow_dispatch (no puede pasar --flags CLI)
    import os as _os
    env_filter = _os.environ.get("IG_CLEAN_FILTER", "").strip()
    env_older = _os.environ.get("IG_CLEAN_OLDER_DAYS", "").strip()
    env_dry = _os.environ.get("IG_CLEAN_DRY_RUN", "").strip().lower()
    if env_filter: filter_ = env_filter
    if env_older:
        try: older_than_days = int(env_older)
        except ValueError: pass
    if env_dry in ("true", "1", "yes"):
        dry_run = True
    elif env_dry in ("false", "0", "no"):
        dry_run = False
        yes = True  # workflow dispatch → auto-confirm si dry=false explícito

    if not IG_LOG_PATH.exists():
        console.print("[red]No hay log IG local[/]")
        return
    log = json.loads(IG_LOG_PATH.read_text(encoding="utf-8"))
    ok_entries = [e for e in log if e.get("status") == "ok" and e.get("media_id")]
    console.print(f"Total reels OK en log: {len(ok_entries)}")

    # Filtros
    cutoff = None
    if older_than_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    filter_tokens = [t.strip().lower() for t in filter_.split(",") if t.strip()] if filter_ else []
    wl_lower = tuple(p.lower() for p in IG_WHITELIST_PREFIXES)

    candidates = []
    for e in ok_entries:
        slug_l = (e.get("slug") or "").lower()
        if filter_tokens and not any(t in slug_l for t in filter_tokens):
            continue
        if not_whitelisted and slug_l.startswith(wl_lower):
            continue
        if cutoff:
            try:
                ts = datetime.fromisoformat(e.get("ts", ""))
                if ts > cutoff:
                    continue
            except Exception:
                continue
        candidates.append(e)

    console.print(f"[cyan]Candidatos a borrar: {len(candidates)}[/]")
    for e in candidates[:20]:
        console.print(f"  {e.get('ts','?')[:19]} · {e.get('media_id')} · {e.get('slug','?')[:50]}")
    if len(candidates) > 20:
        console.print(f"  ... y {len(candidates) - 20} más")

    if dry_run:
        console.print("[yellow]DRY-RUN — no se borra nada[/]")
        return
    if not candidates:
        console.print("[yellow]0 candidatos, nada que hacer[/]")
        return

    if not yes:
        console.print(f"[bold red]¿Borrar {len(candidates)} reels? Añade --yes para confirmar[/]")
        return

    # Borrar
    ok_count, fail_count = 0, 0
    borrados_media_ids = set()
    for i, e in enumerate(candidates, 1):
        mid = e["media_id"]
        success, msg = delete_ig_reel(mid)
        if success:
            ok_count += 1
            borrados_media_ids.add(mid)
            console.print(f"  [green]✓[/] {i}/{len(candidates)} {mid} — {e.get('slug','?')[:40]}")
        else:
            fail_count += 1
            console.print(f"  [red]✗[/] {i}/{len(candidates)} {mid} — {msg[:80]}")

    console.print(f"\n[bold]Resultado: {ok_count} borrados · {fail_count} fallos[/]")

    # Actualiza log — marca borrados
    if borrados_media_ids:
        for e in log:
            if e.get("media_id") in borrados_media_ids:
                e["status"] = "deleted"
                e["deleted_at"] = datetime.now(timezone.utc).isoformat()
        IG_LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"[dim]Log actualizado: {len(borrados_media_ids)} entries marcadas 'deleted'[/]")


@cli.command(name="ig-status")
def ig_status_cmd():
    """Diagnóstico Instagram: token OK + últimos 10 intentos IG (log local).

    Detecta las 4 causas más comunes de "no se suben reels":
      1. IG_TOKEN / IG_USER_ID vacíos en env
      2. Token caducado (60d) — la API responde HTTP 190
      3. Container ERROR — IG rechaza el mp4 (aspect ratio, url no fetchable)
      4. MP4 nunca generado o no encontrado

    Notifica a Telegram el estado + últimos 5 intentos (para chequeo diario).
    """
    import os
    from datetime import datetime, timezone, timedelta
    lines_tg = ["📸 <b>IG Status</b>"]
    print("\n═══ INSTAGRAM STATUS ═══\n")
    tok = os.environ.get("IG_TOKEN") or os.environ.get("IG_ACCESS_TOKEN") or ""
    uid = os.environ.get("IG_USER_ID") or os.environ.get("IG_BUSINESS_ACCOUNT_ID") or ""
    tok_ok = bool(tok)
    uid_ok = bool(uid)
    print(f"IG_TOKEN presente: {'✅' if tok_ok else '❌ VACÍO'}")
    print(f"IG_USER_ID presente: {'✅' if uid_ok else '❌ VACÍO'}")
    lines_tg.append(f"IG_TOKEN: {'✅' if tok_ok else '❌ VACÍO en GH Secrets'}")
    lines_tg.append(f"IG_USER_ID: {'✅' if uid_ok else '❌ VACÍO en GH Secrets'}")
    if tok_ok and uid_ok:
        from . import healthcheck
        ok, msg = healthcheck._check_instagram()
        print(f"Health API: {'✅' if ok else '❌'} — {msg}")
        lines_tg.append(f"API: {'✅' if ok else '❌'} {msg}")
    print("\n═══ ÚLTIMOS 10 INTENTOS IG ═══\n")
    from .instagram_poster import IG_LOG_PATH
    if not IG_LOG_PATH.exists():
        msg = f"⚠️ Sin log local: aún no se registró ningún intento tras instrumentación."
        print(msg)
        lines_tg.append(msg)
    else:
        log = json.loads(IG_LOG_PATH.read_text(encoding="utf-8"))
        # Conteo últimas 24h
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        last24 = [e for e in log if e.get("ts","") > cutoff]
        ok24 = sum(1 for e in last24 if e.get("status") == "ok")
        fail24 = len(last24) - ok24
        lines_tg.append(f"\n<b>Últimas 24h:</b> {ok24}✅ / {fail24}❌ (de {len(last24)})")
        for e in log[-10:]:
            icon = {"ok": "✅", "skip_no_token": "⏭️",
                     "fail_no_mp4": "❌", "fail_container_create": "❌",
                     "fail_container_ready": "❌", "fail_publish": "❌"}.get(
                        e.get("status"), "❓")
            print(f"{icon} {e.get('ts','?')[:19]} · {e.get('slug','?')[:40]:<40} · {e.get('status')}")
        # Solo los últimos 5 al Telegram para no spammear
        lines_tg.append("\n<b>Últimos 5 intentos:</b>")
        for e in log[-5:]:
            icon = {"ok": "✅", "skip_no_token": "⏭️",
                     "fail_no_mp4": "❌", "fail_container_create": "❌",
                     "fail_container_ready": "❌", "fail_publish": "❌"}.get(
                        e.get("status"), "❓")
            lines_tg.append(f"{icon} {e.get('slug','?')[:40]} · <i>{e.get('status')}</i>")

    try:
        from . import notify_batch
        notify_batch.add("\n".join(lines_tg), urgent=True)
    except Exception as e:
        print(f"telegram notify fail: {e}")


@cli.command(name="ambient-short")
def ambient_short_cmd():
    """Genera + sube 1 Short ambient (40s) al canal MenteEnCalma como cebo
    para long-form. Cross-fade imgs vertical + overlay CTA."""
    from .ambient import pipeline
    result = pipeline.run_short()
    if not result:
        raise SystemExit(1)
    print(json.dumps(result, indent=2, default=str))


@cli.command(name="social-boost")
def social_boost_cmd():
    """Postea a Bluesky + Mastodon + Threads un top-YT reciente con hook fresco."""
    from . import social_boost
    import os, json, urllib.request
    result = social_boost.boost_once()
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    lines = ["📣 <b>Social boost</b>"]
    for plat, r in result.items():
        icon = {"bluesky": "🦋", "mastodon": "🐘", "threads": "🧵"}.get(plat, "•")
        if r.get("status") == "no_candidate":
            lines.append(f"{icon} sin candidato disponible")
        elif r.get("posted"):
            lines.append(f"{icon} ✅ {r.get('title','')[:60]}")
        else:
            lines.append(f"{icon} ❌ fallo post")
    print("\n".join(lines))
    if tok and chat:
        try:
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                data=json.dumps({"chat_id": int(chat), "text": "\n".join(lines),
                                  "parse_mode": "HTML"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:
            print(f"tg notify fail: {e}")


@cli.command(name="tax-once")
def tax_once_cmd():
    """Genera + sube 1 short fiscal al canal TaxHack ES (2º canal blue-ocean)."""
    from .tax import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok", "paused"):
        raise SystemExit(1)


@cli.command(name="legal-once")
def legal_once_cmd():
    """Genera + sube 1 short legal-laboral al canal TusDerechos ES."""
    from .legal import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok", "paused"):
        raise SystemExit(1)


@cli.command(name="ayudas-once")
def ayudas_once_cmd():
    """Genera + sube 1 short ayudas/subvenciones al canal AyudaGob."""
    from .ayudas import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok",):
        raise SystemExit(1)


@cli.command(name="motor-once")
def motor_once_cmd():
    """Genera + sube 1 short coches 2ª mano al canal Motor60s."""
    from .motor import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok",):
        raise SystemExit(1)


# ─── LONG-FORM commands (1×/semana por canal) ───

@cli.command(name="tax-longform")
def tax_longform_cmd():
    """Genera + sube 1 long-form (~7 min) al canal TaxHack ES."""
    from .tax import pipeline
    result = pipeline.run_longform()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok",):
        raise SystemExit(1)


@cli.command(name="legal-longform")
def legal_longform_cmd():
    """Genera + sube 1 long-form legal-laboral al canal TusDerechos ES."""
    from .legal import pipeline
    result = pipeline.run_longform()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok",):
        raise SystemExit(1)


@cli.command(name="ayudas-longform")
def ayudas_longform_cmd():
    """Genera + sube 1 long-form ayudas al canal AyudaGob."""
    from .ayudas import pipeline
    result = pipeline.run_longform()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok",):
        raise SystemExit(1)


@cli.command(name="motor-longform")
def motor_longform_cmd():
    """Genera + sube 1 long-form motor 2ª mano al canal Motor60s."""
    from .motor import pipeline
    result = pipeline.run_longform()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok",):
        raise SystemExit(1)


@cli.command(name="pov-once")
def pov_once_cmd():
    """Genera + sube 1 POV histórico al canal TiempoAtrás ES."""
    from .pov import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok",):
        raise SystemExit(1)


@cli.command(name="pov-longform")
def pov_longform_cmd():
    """Genera + sube 1 long-form POV histórico (documental corto ~7min)."""
    from .pov import pipeline
    result = pipeline.run_longform()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok",):
        raise SystemExit(1)


@cli.command(name="ranking-once")
def ranking_once_cmd():
    """Genera + sube 1 bar chart race al canal TopRanking ES."""
    from .ranking import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok",):
        raise SystemExit(1)


@cli.command(name="ia-autonomos-once")
def ia_autonomos_once_cmd():
    """Genera + sube 1 short 'IA para autónomos ES' al canal YT_IA."""
    from .ia_autonomos import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok", "no_secrets"):
        raise SystemExit(1)


@cli.command(name="ia-autonomos-longform")
def ia_autonomos_longform_cmd():
    """Genera + sube 1 long-form 'IA para autónomos ES' al canal YT_IA."""
    from .ia_autonomos import pipeline
    result = pipeline.run_longform()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok", "no_secrets"):
        raise SystemExit(1)


@cli.command(name="ai-tools-once")
def ai_tools_once_cmd():
    """Genera + sube 1 Short EN 'Top 5 AI tools for X' al canal AI Tools Weekly (YT_AITOOLS)."""
    from .ai_tools import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok",):
        raise SystemExit(1)


@cli.command(name="ai-tools-longform")
def ai_tools_longform_cmd():
    """Genera + sube 1 long-form EN (~8 min) al canal AI Tools Weekly (YT_AITOOLS)."""
    from .ai_tools import pipeline
    result = pipeline.run_longform()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok",):
        raise SystemExit(1)


@cli.command(name="ranking-longform")
def ranking_longform_cmd():
    """Genera + sube 1 long-form Top-N (cuenta atrás) al canal TopRanking (YT_RANKING)."""
    from .ranking import pipeline
    result = pipeline.run_longform()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok", "no_secrets", "no_topic"):
        raise SystemExit(1)


@cli.command(name="rankings-en-once")
def rankings_en_once_cmd():
    """Genera + sube 1 bar chart race EN al canal Global Rankings (YT_RANKINGS)."""
    from .rankings_en import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok", "paused"):
        raise SystemExit(1)


@cli.command(name="trabajos-once")
def trabajos_once_cmd():
    """Genera + sube 1 short de curiosidades laborales al canal CuriosLaboral ES."""
    from .trabajos import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok", "paused"):
        raise SystemExit(1)


@cli.command(name="criminopatia-once")
def criminopatia_once_cmd():
    """Genera + sube 1 short de criminología forense al canal Criminopatía."""
    from .criminopatia import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok", "paused"):
        raise SystemExit(1)


@cli.command(name="satisfying-once")
def satisfying_once_cmd():
    """Genera + sube 1 fractal zoom 'satisfying' al canal Infinite Fractals (YT_SATISFYING)."""
    from .satisfying import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok", "skip_daily_cap"):
        raise SystemExit(1)


@cli.command(name="padel-once")
def padel_once_cmd():
    """Genera + sube 1 consejo de pádel (jugada en pista) al canal Pádel Pro ES (YT_PADEL)."""
    from .padel import pipeline
    result = pipeline.run_once()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") not in ("ok", "disabled"):
        raise SystemExit(1)


@cli.command(name="precache-scripts")
@click.option("--n", default=3, type=int, help="Scripts a generar por canal (default 3)")
def precache_scripts_cmd(n: int):
    """Pre-genera N scripts LLM por canal blue-ocean y los cachea en disk.

    Cron 03:37 UTC (baja demanda global Gemini). Evita rate-limits en runtime:
    cuando el cron de publicación dispara, coge del cache en vez de LLM.
    """
    from . import script_cache
    result = script_cache.precache_all(n_per_channel=n)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


@cli.command(name="yt-delete")
@click.argument("video_id")
@click.option("--channel", default=None, help="Prefix del canal (YT_AMBIENT, YT_TAX...). Vacío=WaitWhy.")
def yt_delete_cmd(video_id: str, channel: str | None):
    """Borra un video YT del canal indicado (o WaitWhy por defecto).

    Requiere scope youtube.force-ssl (ya cableado).
    Uso: videogen yt-delete VIDEO_ID --channel YT_AMBIENT
    """
    import os as _os
    prev = _os.environ.get("YT_CHANNEL_PREFIX", "")
    if channel:
        _os.environ["YT_CHANNEL_PREFIX"] = channel
    else:
        _os.environ.pop("YT_CHANNEL_PREFIX", None)
    try:
        from . import upload_youtube
        import googleapiclient.discovery
        creds = upload_youtube._get_credentials()
        yt = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
        yt.videos().delete(id=video_id).execute()
        print(f"✅ Video {video_id} borrado del canal {channel or 'MAIN'}")
    except Exception as e:
        print(f"❌ Delete fail: {type(e).__name__}: {e}")
        raise SystemExit(1)
    finally:
        if prev:
            _os.environ["YT_CHANNEL_PREFIX"] = prev
        else:
            _os.environ.pop("YT_CHANNEL_PREFIX", None)


@cli.command(name="retry-failed")
def retry_failed_cmd():
    """Auto-retry workflows GH Actions con status=failure en última hora.

    Filosofía: transitorios (Gemini 503, Pixabay HTML) se resuelven solos.
    Solo re-ejecuta 1 vez (attempt=1). Si vuelve a fallar, queda como
    failure hasta acción manual (no loop infinito).

    Requiere REPO_ADMIN_PAT con scope actions:write.
    """
    from . import retry_failed
    result = retry_failed.retry_recent_failures(minutes_lookback=90)
    print(json.dumps(result, indent=2, ensure_ascii=False))


@cli.command(name="healthcheck")
def healthcheck_cmd():
    """Chequea salud de TODOS los servicios externos + tokens YT/IG/Threads.

    Detecta problemas ANTES de que un cron real falle. Notif Telegram
    con estado ✅/❌ + acción sugerida.
    """
    from . import healthcheck
    result = healthcheck.check_all()
    if result["down_count"] > 0:
        # Exit code no-zero para que GH Actions marque el run como failure
        # (pero solo si hay servicios caídos — todo verde = 0)
        raise SystemExit(1)


@cli.command(name="ypp-check")
def ypp_check_cmd():
    """Chequea distancia a monetización YouTube en todos los canales.

    Notifica Telegram con estado + gap a próximos umbrales (500 subs
    → YT Shopping / Super Thanks, 1000 subs → YPP full).
    """
    from . import ypp_watch
    result = ypp_watch.check_all()
    print(json.dumps(result, indent=2, ensure_ascii=False))


@cli.command(name="shorts-audit")
@click.option("--channel", default=None,
              help="Prefix del canal. Vacío = todos.")
@click.option("--n", default=20, type=int, help="Últimos N Shorts.")
@click.option("--notify/--no-notify", default=True,
              help="Envía notificación Telegram con underperformers.")
def shorts_audit_cmd(channel: str | None, n: int, notify: bool):
    """Audita rendimiento Shorts últimos N — marca underperformers.

    Umbrales YT Shorts 2026: 65% retention <30s, 50% en 30-60s.
    Sin scope yt-analytics.readonly usamos proxy views/día vs mediana.
    """
    from . import shorts_audit
    if channel:
        result = shorts_audit.audit_channel(
            channel if channel != "MAIN" else "", n=n, notify=notify,
        )
    else:
        result = shorts_audit.audit_all(n=n)
    print(json.dumps(result, indent=2, ensure_ascii=False))


@cli.command(name="topics-refresh")
def topics_refresh_cmd():
    """Regenera topic pool dinámico según tendencias RSS de cada nicho.
    Se ejecuta cada 14 días automáticamente vía el propio pipeline, o manualmente."""
    from . import topic_refresher
    result = topic_refresher.refresh_all_niches()
    print(json.dumps(result, indent=2, ensure_ascii=False))


@cli.command(name="playlists-refresh")
@click.option("--channel", default=None,
              help="Prefix del canal (YT_TAX, YT_LEGAL...). Vacío = todos.")
def playlists_refresh_cmd(channel: str | None):
    """Agrupa uploads por sub-tema en playlists YT. Cron semanal domingo 06:00 UTC.

    +40% session watch time según YT Algorithm 2026 (palanca #1 tras
    desacople Shorts/long-form late 2025).
    """
    from . import playlists
    if channel:
        result = playlists.refresh_channel(channel if channel != "MAIN" else "")
    else:
        result = playlists.refresh_all()
    print(json.dumps(result, indent=2, ensure_ascii=False))


@cli.command(name="series-start")
def series_start_cmd():
    """Inicia nueva miniserie de 5 partes sobre un caso gordo aleatorio."""
    from . import series_generator
    result = series_generator.start_new_series()
    if not result:
        print("  ❌ no se pudo iniciar serie")
        raise SystemExit(1)
    print(json.dumps({"case": result["case_name"],
                       "parts": len(result["parts"])}, indent=2, ensure_ascii=False))


@cli.command(name="series-status")
def series_status_cmd():
    """Muestra estado de la miniserie activa."""
    from . import series_generator
    active = series_generator._load(series_generator.ACTIVE_SERIES, None)
    if not active:
        print("Sin miniserie activa")
        return
    print(json.dumps({
        "case": active["case_name"],
        "next_part": active["next_part"],
        "last_published_at": active.get("last_published_at"),
    }, indent=2, ensure_ascii=False))


@cli.command(name="community-poll-create")
def community_poll_create_cmd():
    """DOMINGO: publica encuesta community en Bluesky con 4 casos candidatos."""
    from . import community_poll
    result = community_poll.create_poll()
    print(json.dumps(result, indent=2, ensure_ascii=False))


@cli.command(name="community-poll-resolve")
def community_poll_resolve_cmd():
    """LUNES: lee likes de la encuesta, elige ganador, escribe community_pick.json."""
    from . import community_poll
    result = community_poll.resolve_poll()
    print(json.dumps(result, indent=2, ensure_ascii=False))


@cli.command(name="newsjack-once")
def newsjack_once_cmd():
    """Detecta noticia HOY de corrupción/juicio + genera Short en <2h.
    RSS de medios ES + Gemini scoring + autogen."""
    from . import newsjack
    import os, json, urllib.request
    result = newsjack.run_once()
    lines = ["🚨 <b>Newsjack</b>"]
    if result.get("status") == "no_candidate":
        lines.append("· sin candidato relevante hoy")
    elif result.get("status") == "gen_fail":
        lines.append(f"· ❌ {result.get('error','')[:100]}")
    else:
        lines.append(f"· ✅ {result.get('slug','')}")
        lines.append(f"· topic: {result.get('topic','')[:100]}")
    print("\n".join(lines))
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                data=json.dumps({"chat_id": int(chat), "text": "\n".join(lines),
                                  "parse_mode": "HTML"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:
            print(f"tg notify fail: {e}")


@cli.command(name="narrative-post")
def narrative_post_cmd():
    """Publica 1 hilo narrativo (5 posts encadenados) en Bluesky+Mastodon+Threads."""
    from . import narrative_post
    import os, json, urllib.request
    result = narrative_post.run_once()
    lines = ["🧵 <b>Hilo narrativo</b>"]
    if result.get("status") == "no_candidate":
        lines.append("· sin candidato (todos <14d)")
    elif result.get("status") == "gen_fail":
        lines.append("· ❌ generación Gemini falló")
    else:
        lines.append(f"· <i>{result.get('title','')[:70]}</i>")
        lines.append(f"· {result.get('posts_count',0)} posts")
        for plat in ("bluesky", "mastodon", "threads"):
            icon = {"bluesky": "🦋", "mastodon": "🐘", "threads": "🧵"}[plat]
            val = result.get(plat)
            mark = "—" if val is None else ("✅" if val else "❌")
            lines.append(f"{icon} {mark}")
    print("\n".join(lines))
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                data=json.dumps({"chat_id": int(chat), "text": "\n".join(lines),
                                  "parse_mode": "HTML"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:
            print(f"tg notify fail: {e}")


@cli.command(name="backfill-once")
@click.option("--per-platform", type=int, default=2,
              help="Cuántos videos backfillear por plataforma (default 2)")
@click.option("--platforms", type=str, default="",
              help="Plataformas coma-sep: 'instagram' | 'tiktok,threads' | vacío=todas")
def backfill_once_cmd(per_platform: int, platforms: str):
    """Repostea top-N Shorts YT históricos a TikTok + IG + Threads.
    Idempotente vía ledger output/backfill_log.json."""
    from . import backfill
    import os, json, urllib.request

    # Env vars overrides (para workflow_dispatch que solo puede pasar env vars)
    env_platforms = os.environ.get("BACKFILL_PLATFORMS", "").strip()
    env_per_platform = os.environ.get("BACKFILL_PER_PLATFORM", "").strip()
    if env_platforms:
        platforms = env_platforms
    if env_per_platform:
        try:
            per_platform = int(env_per_platform)
        except ValueError:
            pass
    plats = [p.strip() for p in platforms.split(",") if p.strip()] if platforms else None
    print(f"backfill-once: platforms={plats or 'ALL'} per_platform={per_platform}")
    results = backfill.backfill_once(per_platform=per_platform, platforms=plats)

    # Report a Telegram si está configurado
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        lines = ["🔁 <b>Backfill diario</b>"]
        any_activity = False
        for plat, r in results.items():
            icon = {"tiktok": "🎵", "instagram": "📸", "threads": "🧵"}.get(plat, "•")
            posted = r.get("posted", [])
            failed = r.get("failed", [])
            if not posted and not failed:
                lines.append(f"{icon} {plat}: 0 candidatos")
            for x in posted:
                any_activity = True
                lines.append(f"{icon} {plat} ✅: {x['title'][:60]} ({x['views']}v)")
            for x in failed:
                any_activity = True
                reason = x.get("fail_reason") or "download/post falló"
                lines.append(f"{icon} {plat} ❌: {x['title'][:60]}\n    ↳ {reason[:500]}")
        if any_activity or not results:
            try:
                req = urllib.request.Request(
                    f"https://api.telegram.org/bot{tok}/sendMessage",
                    data=json.dumps({"chat_id": int(chat), "text": "\n".join(lines),
                                      "parse_mode": "HTML"}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=30).read()
            except Exception as e:
                print(f"tg notify fail: {e}")

    for plat, r in results.items():
        print(f"{plat}: {len(r.get('posted', []))} posted, {len(r.get('failed', []))} failed")


@cli.command(name="reauth-buttons")
@click.option("--only", default="", help="Solo estos canales (nombres separados por coma), ej. 'WaitWhy'.")
def reauth_buttons_cmd(only: str):
    """Envía a Telegram los botones de reautorización de los canales YT (aunque el
    token siga válido) — para añadir el permiso de analítica. --only filtra por nombre."""
    from . import healthcheck
    names = [s.strip() for s in only.split(",") if s.strip()] or None
    n = healthcheck.send_reauth_all(only=names)
    print(f"reauth buttons enviados: {n}" + (f" (solo {names})" if names else ""))
    if not n:
        raise SystemExit(1)


@cli.command(name="snapshot")
def snapshot_cmd():
    """Snapshot de métricas de TODAS las plataformas + regenera el panel (sin Telegram)."""
    from . import analytics, dashboard
    counts = analytics.snapshot_all(progress=lambda m: print(f"  {m}"))
    print("snapshot:", json.dumps(counts, ensure_ascii=False))
    dashboard.write()
    print("✓ panel regenerado")


@cli.command(name="traffic-report")
@click.option("--days", default=28, show_default=True, help="Ventana de días.")
def traffic_report_cmd(days: int):
    """Funnel RRSS→YouTube: fuentes de tráfico por canal. EXT_URL = clics desde
    enlaces EXTERNOS (Bluesky/Mastodon/Threads llevan link clicable; IG/TikTok no).
    Mide si las RRSS traen tráfico real a YouTube. Requiere reauth con scope
    yt-analytics.readonly (canales sin reauth salen 'sin datos', graceful)."""
    import os
    import requests
    from . import stats
    from .healthcheck import YT_CHANNELS
    lines = []
    for prefix, name in YT_CHANNELS:
        d = stats.fetch_traffic_sources(prefix, days=days)
        if not d or not d.get("total_views"):
            print(f"  {name}: sin datos (¿reauth analytics pendiente?)")
            continue
        ext = d.get("external_pct", 0); extv = d.get("external_views", 0)
        det = d.get("external_detail", {})
        top = ", ".join(f"{k}:{v}" for k, v in list(det.items())[:3])
        line = f"{name}: {d['total_views']} views · EXT {ext}% ({extv})" + (f" · {top}" if top else "")
        print("  " + line)
        lines.append(line)
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if tok and chat and lines:
        txt = (f"📊 <b>Funnel RRSS→YouTube ({days}d)</b>\n"
               f"EXT_URL = clics desde enlaces externos (Bluesky/Mastodon/Threads)\n\n"
               + "\n".join("• " + l for l in lines))
        try:
            requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": chat, "text": txt, "parse_mode": "HTML"}, timeout=15)
        except Exception as e:
            print("  telegram fail:", e)
    if not lines:
        print("Ningún canal con scope analytics todavía → reautoriza para activar la medición del funnel.")


@cli.command(name="broadcast-test")
def broadcast_test_cmd():
    """Manda un mensaje de prueba al canal de difusión Telegram (verifica config +
    que el bot es admin)."""
    from . import social_broadcast
    ok = social_broadcast.broadcast_test()
    if not ok:
        raise SystemExit(1)


@cli.command(name="broadcast-setup")
@click.option("--seed", default=10, show_default=True, help="Nº de vídeos a sembrar.")
def broadcast_setup_cmd(seed: int):
    """Configura el canal de difusión: nombre+descripción SEO (keywords ES) + siembra
    los últimos vídeos de WaitWhy para que no esté vacío. Uso puntual."""
    from . import social_broadcast
    social_broadcast.setup_channel_seo()
    n = social_broadcast.seed_channel(limit=seed)
    print(f"broadcast-setup: seed {n} vídeos")


@cli.command(name="dashboard")
@click.option("--serve", "serve_", is_flag=True,
              help="Abre el panel en LOCAL (localhost) en vez de solo regenerar el JSON.")
@click.option("--port", default=5056, show_default=True, help="Puerto del servidor local.")
@click.option("--no-open", is_flag=True, help="No abrir el navegador automáticamente.")
def dashboard_cmd(serve_: bool, port: int, no_open: bool):
    """Panel de control multi-canal (Centro de Mando).

    Sin flags: regenera docs/dashboard/data.json (lo que usa el job diario).
    --serve: regenera y lo SIRVE EN LOCAL en http://127.0.0.1:<port>/ (abre el navegador).

    Agrega TODAS las métricas reales (YouTube/IG/TikTok/Bluesky/Mastodon/Threads),
    top/peor contenido, análisis de temas y la agenda (cron de cada canal).
    """
    from . import dashboard
    if serve_:
        dashboard.serve(port=port, open_browser=not no_open)
        return
    dest = dashboard.write()
    data = json.loads(dest.read_text(encoding="utf-8"))
    print(f"✓ {dest} ({dest.stat().st_size/1024:.0f} KB)")
    print(f"  canales={len(data['channels'])} redes={len(data['socials'])} "
          f"agenda_próx={len(data['schedule']['upcoming'])} histórico={len(data['schedule']['history'])}")
    print("  Para verlo en local:  videogen dashboard --serve")


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
