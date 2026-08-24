"""Bot de Telegram para videogen.

Funciones:
  • Envías un prompt (texto) → genera el video bilingüe → te manda ambos a Telegram
    → botones [✅ Subir] / [🗑 Descartar] → si OK, sube a YouTube ES+EN.
  • /stats → resumen de stats de YouTube de tus videos subidos.
  • Resumen diario automático (stats + recordatorio de horas óptimas por plataforma).

Lanzar:  videogen bot
"""
from __future__ import annotations

import asyncio
import datetime as dt
from functools import partial

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import ideas, service, stats
from .config import PENDING_DIR, UPLOADED_DIR, telegram_chat_id, telegram_token
import os

# slug → datos pendientes de aprobación (para los callbacks)
PENDING: dict[str, str] = {}


async def _run_blocking(fn, *args):
    """Ejecuta una función bloqueante (pipeline) sin congelar el event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(fn, *args))


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"🎬 *videogen bot* listo.\n\n"
        f"Tu chat id es `{chat_id}` — ponlo en `.env` como TELEGRAM_CHAT_ID "
        f"para recibir el resumen diario.\n\n"
        f"Envíame una *idea* y genero el video bilingüe.\n"
        f"Escribe /help para ver todo lo que puedo hacer.",
        parse_mode="Markdown",
    )


HELP_TEXT = (
    "🎬 *videogen bot* — qué puedo hacer\n\n"
    "*Para generar un video:*\n"
    "Solo escríbeme tu idea como un mensaje normal. Ejemplos:\n"
    "• `Curiosidades del cuerpo humano que no sabías`\n"
    "• `Por qué el cielo es azul`\n"
    "• `Datos del Mundial 2026`\n"
    "Genero el video en español e inglés, te los envío para revisar, "
    "y con el botón ✅ los subo a YouTube.\n\n"
    "💡 Cuanto más concreta la idea (con datos), mejor el video. "
    "Puedes pegar datos reales en el mensaje y los usaré.\n\n"
    "🖼️ Si el video va de un famoso (CR7, Musk…), meto su FOTO REAL "
    "(licencia libre de Wikimedia, con atribución automática).\n\n"
    "🎨 Si NO es de un famoso, genero un *frame de imagen IA* (Pollinations, "
    "gratis) para el arranque, más impactante. Para desactivarlo en un video, "
    "empieza tu mensaje con `noia` (ej: `noia el coste de fabricar un iPhone`).\n\n"
    "🪝 Todos los videos llevan un *texto-hook* grande en pantalla en el segundo 0 "
    "(para de scroll en TikTok/Reels y sube la retención).\n\n"
    "*También entiendo lenguaje natural* (no solo comandos):\n"
    "• «envíame el último vídeo con y sin subs» → te mando los archivos\n"
    "• «mándame el del iPhone» → busca por palabras del título y lo envía\n"
    "• «qué tengo programado» / «lista» → muestra los últimos vídeos\n"
    "• «tt del iphone 897 11» / «ig pulpo 230 2» → registro manual de stats TikTok/Instagram\n"
    "• «gráficas» / «cómo van los números» → manda las gráficas de analytics\n"
    "• «atomiza el del mcdonald's» → genera clips promo del long-form para TT/IG\n"
    "• «haz un tiktok de X» / «genera tt sobre X» → genera Short EXCLUSIVO para TikTok (sin YT, 28-34s, comment-bait, sin música)\n"
    "Si no es una petición, lo trato como idea y te genero un vídeo.\n\n"
    "*Comandos:*\n"
    "/ideas — ideas de video de dinero específicas (responde con una y la genero)\n"
    "/send — envía los archivos del último vídeo (con y sin subs). `/send iphone` busca por hint.\n"
    "/snapshot — gráficas de progreso por plataforma (YT auto, IG si tienes token, TT manual)\n"
    "/atomize <slug> — extrae 4-5 clips promo de un long-form para subir a TT/IG/Shorts (con CTA al canal)\n"
    "/autogen — fuerza la generación diaria automática AHORA (idem job 08:00 CEST)\n"
    "/longgen — genera long-form polarizante + atomiza en 5 Shorts + programa todo (idem job dom 10:00). Es el FUNNEL que monetiza.\n"
    "\n"
    "*Mantenimiento*\n"
    "Si recibes «🚨 TOKEN YT CADUCADO» → en la Mac ejecuta `videogen reauth` (1 comando, 30s, abre navegador y listo). Google revoca el token cada ~7 días.\n"
    "/stats — estadísticas de YouTube (suscriptores + por video)\n"
    "/optimal — mejores horas para publicar (YouTube/TikTok)\n"
    "/ui — enlace a la UI web (misma WiFi)\n"
    "/start — iniciar y ver tu chat id\n"
    "/help — esta ayuda\n\n"
    "📅 Cada día a las 11:00 te mando stats + ideas frescas de video.\n\n"
    "*Tras generar un video:*\n"
    "✅ Subir ahora — publica ES + EN al instante\n"
    "🗓 Programar — elige un slot (hoy/mañana 14:00 o 21:00) y YouTube lo publica solo a esa hora\n"
    "🗑 Descartar — lo elimina\n"
    "🔁 Cross-post — tras subir, botón para repartirlo en TikTok/Instagram/Facebook/Pinterest/Snapchat (más alcance gratis)\n\n"
    "🎵 Para TikTok: usa la variante `_tiktok.mp4` (sin música) y añade "
    "audio trending en la app.\n"
    "📊 Cada mañana recibes un resumen automático de stats + recordatorio."
)


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def ui_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from . import webapp
    ip = webapp._lan_ip()
    await update.message.reply_text(
        f"🖥 *UI web* (ábrela en la misma WiFi que el ordenador):\n"
        f"http://{ip}:5005\n\n"
        f"_Tip: aquí en el bot ya puedes hacer todo (generar, revisar, subir). "
        f"La UI es solo la versión visual con historial._",
        parse_mode="Markdown",
    )


async def optimal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⏰ *Mejores horas para subir* (hora local)\n\n"
        f"▶️ YouTube Shorts: {stats.OPTIMAL_TIMES['youtube']}\n"
        f"🎵 TikTok: {stats.OPTIMAL_TIMES['tiktok']}",
        parse_mode="Markdown",
    )


async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Consultando stats de YouTube…")
    await _send_stats(update.effective_chat.id, ctx)


async def ideas_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💡 Pensando ideas…")
    await _send_ideas(update.effective_chat.id, ctx, n=6)


async def _send_ideas(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE, n: int = 5):
    try:
        items = await _run_blocking(lambda: ideas.generate_ideas(n))
    except Exception:
        items = []
    if not items:
        await ctx.bot.send_message(chat_id, "No pude generar ideas ahora (Gemini ocupado). Reintenta en un rato.")
        return
    lines = ["💡 *Ideas de hoy* (responde con la que te guste y la genero):\n"]
    for i, idea in enumerate(items, 1):
        lines.append(f"{i}. {idea}")
    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")


async def _send_stats(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        data = await _run_blocking(stats.fetch_youtube_stats)
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"⚠️ No pude leer stats de YouTube: {e}")
        return
    # Cabecera con stats del canal (suscriptores)
    header = []
    try:
        ch = await _run_blocking(stats.fetch_channel_stats)
    except Exception:
        ch = None
    if ch:
        subs = "oculto" if ch.get("hidden_subs") else f"{ch['subscribers']:,}"
        header.append(
            f"📺 *{ch['title']}*\n👥 {subs} subs · {ch['views']:,} views totales · {ch['videos']} videos\n"
        )

    if not data:
        msg = "\n".join(header) if header else ""
        msg += "\nAún no hay videos subidos con stats por video."
        await ctx.bot.send_message(chat_id, msg or "Sin datos todavía.", parse_mode="Markdown")
        return
    total_v = sum(d["views"] for d in data)
    total_l = sum(d["likes"] for d in data)
    lines = header + [f"📊 *Por video* — {len(data)} videos · {total_v:,} views · {total_l:,} likes\n"]
    for d in data[:8]:
        lines.append(f"• {d['views']:,} 👁  {d['likes']:,} ❤️  — {d['title'][:48]}")
    lines.append("\n🎵 *TikTok*: sin API pública — revisa el panel de TikTok manualmente.")
    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")


def _classify_message(text: str) -> dict:
    """Clasifica un mensaje libre en una intención. PERMISIVO con 'generate':
    en duda, asume que el usuario quiere crear un vídeo (comportamiento clásico).

    Devuelve dict con al menos {'intent': str}, posibles intents:
      generate · send_files · list · stats · ideas · help · unknown
    Campos extra según intent (with_subs, without_subs, slug_hint, topic).
    """
    from .config import gemini_key

    key = gemini_key()
    if not key or not text:
        return {"intent": "generate", "topic": text}
    system = (
        "You classify Telegram messages from the channel owner of a money-curiosity "
        "YouTube Shorts factory.\n"
        "Intents:\n"
        "- generate: user wants a NEW video on a topic. DEFAULT — when in doubt, choose this.\n"
        "- send_files: user wants you to SEND an already-generated video file (e.g. 'envíame', 'mándame', 'pásame', 'send me', 'man da' the video, with/without subs).\n"
        "- list: user asks what is generated/scheduled/pending ('qué tengo', 'lista', 'pendientes', 'qué hay programado').\n"
        "- stats: user asks for channel stats / views (numbers from YT API).\n"
        "- charts: user asks for the analytics graphs / chart ('gráfica', 'graphs', 'analytics', 'cómo van los números').\n"
        "- atomize: user asks to atomize/extract clips from a LONG-FORM video to promote it on TikTok/IG/Shorts. Examples: 'atomiza el del mcdonald's', 'extrae clips del long-form de X', 'haz clips promo del largo de iphone'. slug_hint = part of the title.\n"
        "- tt_generate: user asks to generate a NEW TikTok-exclusive video (28-34s, native style for TT virality, NO YT). Examples: 'haz un tiktok de X', 'genera tt sobre X', 'crea un short tiktok-first de X', 'haz un viral de tiktok de X'. The `topic` field is the topic to generate.\n"
        "- log_views: user is REPORTING numbers to log (manual entry for TikTok or Instagram). Triggers when the message mentions a platform abbreviation (tt, tiktok, ig, insta, instagram, yt, youtube) AND numeric data like views/likes. Examples: 'tt del iphone 897 11', 'ig pulpo 230 views 2 likes', 'instagram cr7 450 5'.\n"
        "- ideas: user asks for video ideas.\n"
        "- help: user asks how to use the bot.\n"
        "- unknown: a question unrelated to the above (you'll be answered with a polite fallback).\n"
        'Return ONLY JSON: {"intent":"...", "with_subs":bool, "without_subs":bool, '
        '"slug_hint":"...", "topic":"...", "platform":"...", "views":int, "likes":int}.\n'
        "  platform: 'tiktok'|'instagram'|'youtube' — only for log_views.\n"
        "  views/likes: integers from the message — only for log_views.\n"
        "  with_subs/without_subs: only for send_files. If user says 'con y sin subs' → both true. "
        "If they only mention 'sin subs' → without_subs=true, with_subs=false. If unclear → both true.\n"
        "  slug_hint: substring of the topic the user mentions, lowercase, if any (e.g. 'iphone', 'cr7'). Empty otherwise.\n"
        "  topic: only for intent=generate, the topic to generate (clean phrase).\n"
        "Bias to GENERATE if the message looks like a topic phrase (e.g. 'el coste real del oro').\n"
    )
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=f"Message: {text}",
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                temperature=0.0,
                max_output_tokens=300,
            ),
        )
        import json
        import re
        raw = (resp.text or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE)
        data = json.loads(raw or "{}")
        if not isinstance(data, dict) or "intent" not in data:
            return {"intent": "generate", "topic": text}
        return data
    except Exception:
        return {"intent": "generate", "topic": text}


def _find_slug(hint: str) -> dict | None:
    """Encuentra el item de historial que mejor casa con `hint` (substring),
    o el más reciente si hint vacío."""
    items = service.list_history()
    if not items:
        return None
    hint = (hint or "").lower().strip()
    if hint:
        for it in items:
            blob = " ".join([
                it.get("slug", ""), it.get("topic", ""),
                it.get("title_es", ""), it.get("title_en", ""),
            ]).lower()
            if hint in blob:
                return it
    return items[0]


async def _send_videos(
    chat_id: int, slug: str, with_subs: bool, without_subs: bool,
    ctx: ContextTypes.DEFAULT_TYPE, title: str = "",
) -> None:
    """Envía a Telegram las variantes pedidas (con/sin subtítulos) del slug,
    y SIEMPRE acompaña con el caption para pegar en la descripción del vídeo
    en otras redes (TikTok/Reels/etc.).

    Genera la versión sin subs y los share comprimidos si no existen."""
    import html
    from . import compose, crosspost
    d = None
    for base in (UPLOADED_DIR, PENDING_DIR):
        if (base / slug).exists():
            d = base / slug
            break
    if d is None:
        await ctx.bot.send_message(chat_id, f"No encuentro el vídeo «{slug}».")
        return
    if not with_subs and not without_subs:
        with_subs = True  # algo hay que enviar
    sent = 0
    name = title or slug
    if with_subs:
        master = d / "video_es_vertical.mp4"
        share = d / "share_es.mp4"
        if master.exists():
            try:
                if not share.exists():
                    await _run_blocking(lambda: compose.make_share(master, share))
                with open(share, "rb") as fh:
                    await ctx.bot.send_video(
                        chat_id, video=fh,
                        caption=f"📥 {name} · CON subtítulos",
                        read_timeout=300, write_timeout=300, connect_timeout=60,
                        supports_streaming=True,
                    )
                sent += 1
            except Exception as e:
                await ctx.bot.send_message(chat_id, f"⚠️ Error enviando con subs: {e}")
    if without_subs:
        try:
            nosubs = await _run_blocking(lambda: service.recompose_no_subs(slug, "es"))
            if nosubs:
                share_ns = nosubs.with_name("share_nosubs_es.mp4")
                if not share_ns.exists():
                    await _run_blocking(lambda: compose.make_share(nosubs, share_ns))
                with open(share_ns, "rb") as fh:
                    await ctx.bot.send_video(
                        chat_id, video=fh,
                        caption=f"📥 {name} · SIN subtítulos (TikTok/Reels los autogeneran)",
                        read_timeout=300, write_timeout=300, connect_timeout=60,
                        supports_streaming=True,
                    )
                sent += 1
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"⚠️ Error enviando sin subs: {e}")
    if sent == 0:
        await ctx.bot.send_message(chat_id, "No pude enviar ningún archivo.")
        return
    # Caption SIEMPRE: título + hashtags listos para pegar en otras redes
    try:
        scripts = service.script.load_scripts(d)
        caption = crosspost.build_caption(scripts.es)
        await ctx.bot.send_message(
            chat_id,
            "📝 <b>Caption para la descripción</b> (cópialo y pégalo en TikTok/Reels/etc.)\n\n"
            f"<pre>{html.escape(caption)}</pre>",
            parse_mode="HTML",
        )
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"⚠️ No pude generar el caption: {e}")


async def _handle_send_intent(chat_id: int, intent: dict, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    item = _find_slug(intent.get("slug_hint", ""))
    if item is None:
        await ctx.bot.send_message(chat_id, "Aún no tienes vídeos generados.")
        return
    title = item.get("title_es") or item.get("topic") or item["slug"]
    await ctx.bot.send_message(chat_id, f"📦 Preparando «{title[:60]}»…")
    with_subs = bool(intent.get("with_subs", True))
    without_subs = bool(intent.get("without_subs", True))
    await _send_videos(chat_id, item["slug"], with_subs, without_subs, ctx, title=title)


async def _handle_list_intent(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    items = service.list_history()[:8]
    if not items:
        await ctx.bot.send_message(chat_id, "Aún no tienes vídeos.")
        return
    lines = ["📋 *Últimos vídeos:*"]
    for it in items:
        emoji = "🚀" if it["status"] == "uploaded" else "📝"
        title = it.get("title_es") or it.get("topic") or it["slug"]
        yt = next(iter((it.get("youtube") or {}).values()), "")
        lines.append(f"{emoji} {title[:60]}\n  `{it['slug']}`" + (f"\n  {yt}" if yt else ""))
    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")


async def _handle_log_views(chat_id: int, intent: dict, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra a mano una lectura (TikTok/Instagram típicamente)."""
    from . import analytics
    platform = (intent.get("platform") or "").lower().strip()
    if platform in ("tt", "ttok"):
        platform = "tiktok"
    if platform in ("ig", "insta"):
        platform = "instagram"
    if platform in ("yt",):
        platform = "youtube"
    if platform not in analytics.PLATFORMS:
        await ctx.bot.send_message(chat_id, "No tengo claro qué plataforma. Prueba: «tt del iphone 897 11».")
        return
    views = int(intent.get("views") or 0)
    likes = int(intent.get("likes") or 0)
    if views <= 0:
        await ctx.bot.send_message(chat_id, "Necesito un número de views. Ej: «tt iphone 897 11».")
        return
    item = _find_slug(intent.get("slug_hint", ""))
    slug = (item or {}).get("slug")
    title = (item or {}).get("title_es") or (item or {}).get("topic") or intent.get("slug_hint", "")
    await _run_blocking(
        lambda: analytics.record_manual(
            platform=platform, views=views, likes=likes, slug=slug, title=title,
        )
    )
    rate = (likes / views * 100) if views else 0
    await ctx.bot.send_message(
        chat_id,
        f"📝 Registrado en {platform.upper()}: «{(title or slug or '?')[:50]}»\n"
        f"   {views:,} views · {likes:,} likes · {rate:.1f}% like-rate",
    )


async def _send_atomized(chat_id: int, slug: str, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Genera 4-5 Shorts promocionales del long-form `slug` y los manda al chat
    con sus captions. Reusa archivos cacheados si ya existen."""
    import html as _html
    from . import atomize, script

    item = _find_slug(slug) if slug else None
    if not item:
        await ctx.bot.send_message(chat_id, "No encuentro ese long-form.")
        return
    real_slug = item["slug"]
    # Comprueba que hay long_scripts.json (es un long-form)
    d = None
    for base in (UPLOADED_DIR, PENDING_DIR):
        if (base / real_slug).exists():
            d = base / real_slug
            break
    if d is None or not (d / "long_scripts.json").exists():
        await ctx.bot.send_message(
            chat_id, f"«{real_slug}» no es un long-form (no tiene long_scripts.json)."
        )
        return
    await ctx.bot.send_message(chat_id, "🔪 Atomizando long-form en clips… (~30s)")
    try:
        clips = await _run_blocking(lambda: atomize.atomize_long(
            real_slug, lang="es", handle="@waitwhy_ybb", channel="WaitWhy",
            progress=lambda m: None,
        ))
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"❌ Atomize falló: {e}")
        return
    if not clips:
        await ctx.bot.send_message(chat_id, "No salió ningún clip.")
        return
    scripts_long = script.load_long_scripts(d)
    loc = scripts_long.es
    await ctx.bot.send_message(
        chat_id,
        f"✅ {len(clips)} clips listos. Súbelos a TikTok/IG/Shorts después de que el "
        f"long-form esté público en YT.",
    )
    for i, clip in enumerate(clips):
        ch_name = loc.chapters[i].name if i < len(loc.chapters) else f"Capítulo {i+1}"
        try:
            with open(clip, "rb") as fh:
                await ctx.bot.send_video(
                    chat_id, video=fh,
                    caption=f"🎬 Clip {i+1}/{len(clips)} · «{ch_name}»",
                    read_timeout=300, write_timeout=300, connect_timeout=60,
                    supports_streaming=True,
                )
            cap = atomize.build_clip_caption(loc, ch_name, "@waitwhy_ybb", "WaitWhy")
            await ctx.bot.send_message(
                chat_id,
                f"📝 <b>Caption clip {i+1}</b> (cópialo)\n\n<pre>{_html.escape(cap)}</pre>",
                parse_mode="HTML",
            )
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"⚠️ Error en clip {i+1}: {e}")


async def atomize_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/atomize <slug>  → genera clips del long-form y los envía al chat."""
    if not ctx.args:
        await update.message.reply_text(
            "Uso: `/atomize <slug-del-long-form>` o NL: «atomiza el del mcdonald's».",
            parse_mode="Markdown",
        )
        return
    await _send_atomized(update.effective_chat.id, " ".join(ctx.args).strip(), ctx)


async def send_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/send [slug_hint]  → envía el vídeo más reciente (o el que casa con el hint),
    en sus dos variantes (con y sin subtítulos)."""
    hint = " ".join(ctx.args).strip() if ctx.args else ""
    await _handle_send_intent(
        update.effective_chat.id,
        {"slug_hint": hint, "with_subs": True, "without_subs": True},
        ctx,
    )


async def handle_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return
    chat_id = update.effective_chat.id

    # Opt-out de imagen IA: si el mensaje empieza por "noia", se omite el frame IA
    ai_hero = True
    if text.lower().startswith("noia"):
        ai_hero = False
        text = text[4:].lstrip(" :,-").strip()
        if not text:
            return

    # Clasificación NLU (Gemini): el bot entiende peticiones, no solo comandos.
    # En duda → generate (comportamiento clásico). Errores → generate.
    intent = await _run_blocking(lambda: _classify_message(text))
    kind = intent.get("intent", "generate")

    if kind == "send_files":
        await _handle_send_intent(chat_id, intent, ctx)
        return
    if kind == "list":
        await _handle_list_intent(chat_id, ctx)
        return
    if kind == "stats":
        await _send_stats(chat_id, ctx)
        return
    if kind == "charts":
        await _send_charts(chat_id, ctx)
        return
    if kind == "tt_generate":
        topic_tt = (intent.get("topic") or text).strip()
        await update.message.reply_text(f"🎵 Generando TikTok-exclusivo sobre: «{topic_tt[:60]}»…")
        try:
            slug = await _run_blocking(lambda: service.generate_tt_native(topic_tt, fmt=None))
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"❌ Error: {e}")
            return
        # Localiza el mp4 y mándalo
        from pathlib import Path
        d = PENDING_DIR / slug
        mp4s = list(d.glob("video_tt_*.mp4"))
        if not mp4s:
            await ctx.bot.send_message(chat_id, f"TT generado pero no encuentro mp4 en {d}")
            return
        mp4 = mp4s[0]
        from . import script as _script
        tt = _script.load_tt_native_script(d)
        await ctx.bot.send_message(
            chat_id,
            f"✅ TT-native listo · formato *{tt.format}*\n"
            f"📝 Bait: «{tt.comment_bait}»\n"
            f"⏱ Súbelo a TikTok y añade un audio trending al final.",
            parse_mode="Markdown",
        )
        try:
            with open(mp4, "rb") as fh:
                await ctx.bot.send_video(
                    chat_id, video=fh,
                    caption=f"🎵 {tt.title[:80]}",
                    read_timeout=300, write_timeout=300, connect_timeout=60,
                    supports_streaming=True,
                )
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"⚠️ No pude enviar el archivo ({mp4.stat().st_size/1e6:.1f} MB): {e}")
        # Caption copiable
        import html as _html
        spam = {"#fyp", "#parati", "#reels", "#shorts", "#viral", "#foryou", "#foryoupage"}
        niche_tags = [h for h in tt.hashtags if h.lower() not in spam][:5]
        cap = f"{tt.comment_bait} 👇\n\n{' '.join(niche_tags)}"
        await ctx.bot.send_message(
            chat_id,
            f"📝 <b>Caption</b>\n\n<pre>{_html.escape(cap)}</pre>",
            parse_mode="HTML",
        )
        return

    if kind == "atomize":
        hint = (intent.get("slug_hint") or "").strip()
        item = _find_slug(hint) if hint else None
        slug = (item or {}).get("slug", "") if item else ""
        if not slug:
            await ctx.bot.send_message(chat_id, "Dime el slug del long-form (p. ej. «atomiza el del mcdonald's»).")
            return
        await _send_atomized(chat_id, slug, ctx)
        return
    if kind == "log_views":
        await _handle_log_views(chat_id, intent, ctx)
        return
    if kind == "ideas":
        await _send_ideas(chat_id, ctx)
        return
    if kind == "help":
        await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")
        return
    if kind == "unknown":
        await update.message.reply_text(
            "No estoy seguro de qué pides. Puedes:\n"
            "• Escribirme una idea para generar un vídeo\n"
            "• `envíame el último vídeo con y sin subs`\n"
            "• `qué tengo programado` / /help"
        )
        return

    # generate (default): usa el topic limpio que devolvió Gemini, o el texto original.
    topic = (intent.get("topic") or text).strip()
    status_msg = await update.message.reply_text("🛠 Generando… (te aviso del progreso)")

    last = {"txt": ""}

    def progress(msg: str):
        last["txt"] = msg  # se muestra al final; evitamos spam de edits

    try:
        slug = await _run_blocking(lambda: service.generate(topic, ("es", "en"), progress, ai_hero=ai_hero))
    except Exception as e:
        await status_msg.edit_text(f"❌ Error generando: {e}")
        return

    PENDING[slug] = topic
    meta = service.get_meta(slug)
    import html as _html
    _title = _html.escape(meta.get('es', {}).get('title', ''))
    await status_msg.edit_text(f"✅ Generado: <b>{_title}</b>", parse_mode="HTML")

    # Envía preview comprimido de cada idioma (pequeño → sin timeout)
    from . import compose
    for lang in ("es", "en"):
        p = service.video_path(slug, lang)
        if not p:
            continue
        try:
            preview = await _run_blocking(
                lambda p=p: compose.make_preview(p, p.with_name(f"preview_{lang}.mp4"))
            )
            with open(preview, "rb") as fh:
                await ctx.bot.send_video(
                    chat_id, video=fh, caption=f"{lang.upper()}",
                    read_timeout=180, write_timeout=180, connect_timeout=60,
                )
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"⚠️ No pude enviar el preview {lang.upper()}: {e}")

    # El botón de aprobar SIEMPRE se muestra (aunque falle el preview)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Subir ahora", callback_data=f"pub:{slug}"),
            InlineKeyboardButton("🗓 Programar", callback_data=f"sch:{slug}"),
        ],
        [InlineKeyboardButton("🗑 Descartar", callback_data=f"del:{slug}")],
    ])
    await ctx.bot.send_message(chat_id, "¿Subo estos videos a YouTube (ES + EN)?", reply_markup=kb)


def _slot_publish_at(code: str) -> tuple[str, str]:
    """code: t21/m14/m21 (today/tomorrow + hora) → (rfc3339_utc, etiqueta local)."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now().astimezone()
    base = now if code.startswith("t") else now + timedelta(days=1)
    hour = int(code[1:])
    local = base.replace(hour=hour, minute=0, second=0, microsecond=0)
    if local <= now:  # si ya pasó, lo movemos a mañana
        local = local + timedelta(days=1)
    utc = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return utc, local.strftime("%d/%m %H:%M")


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    action, slug = parts[0], parts[1]
    chat_id = q.message.chat.id

    if action == "del":
        PENDING.pop(slug, None)
        await q.edit_message_text("🗑 Descartado.")
        return

    if action == "pub":
        await q.edit_message_text("🚀 Subiendo a YouTube…")
        try:
            links = await _run_blocking(
                lambda: service.publish(slug, ("es", "en"), "public", lambda m: None, notify=False)
            )
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"❌ Error al subir: {e}")
            return
        PENDING.pop(slug, None)
        txt = "🎉 Publicado en YouTube:\n" + "\n".join(f"{k.upper()}: {v}" for k, v in links.items())
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔁 Cross-post", callback_data=f"xp:{slug}"),
            InlineKeyboardButton("📥 Enviar archivos", callback_data=f"snd:{slug}"),
        ]])
        await ctx.bot.send_message(chat_id, txt, reply_markup=kb)
        return

    if action == "sch":  # menú de slots de programación
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Hoy 21:00", callback_data=f"go:{slug}:t21"),
                InlineKeyboardButton("Hoy 14:00", callback_data=f"go:{slug}:t14"),
            ],
            [
                InlineKeyboardButton("Mañana 21:00", callback_data=f"go:{slug}:m21"),
                InlineKeyboardButton("Mañana 14:00", callback_data=f"go:{slug}:m14"),
            ],
        ])
        await q.edit_message_text(
            "🗓 ¿Cuándo publico el Short? (si la hora ya pasó, va al día siguiente)",
            reply_markup=kb,
        )
        return

    if action == "go":  # programar a un slot
        code = parts[2]
        publish_at, label = _slot_publish_at(code)
        await q.edit_message_text(f"🗓 Programando para {label}…")
        try:
            links = await _run_blocking(
                lambda: service.publish(
                    slug, ("es", "en"), "public", lambda m: None,
                    notify=False, publish_at=publish_at,
                )
            )
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"❌ Error al programar: {e}")
            return
        PENDING.pop(slug, None)
        txt = (
            f"🗓 Programado para *{label}* (se publica solo a esa hora):\n"
            + "\n".join(f"{k.upper()}: {v}" for k, v in links.items())
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔁 Cross-post", callback_data=f"xp:{slug}"),
            InlineKeyboardButton("📥 Enviar archivos", callback_data=f"snd:{slug}"),
        ]])
        await ctx.bot.send_message(chat_id, txt, parse_mode="Markdown", reply_markup=kb)
        return

    if action == "snd":
        # Carga el título para el caption sin tener que listar todo el historial
        item = _find_slug(slug)
        title = (item or {}).get("title_es") or (item or {}).get("topic") or slug
        await ctx.bot.send_message(chat_id, f"📦 Preparando «{title[:60]}»…")
        await _send_videos(chat_id, slug, with_subs=True, without_subs=True, ctx=ctx, title=title)
        return

    if action == "xp":
        await _send_crosspost(chat_id, slug, ctx)


async def _send_crosspost(chat_id: int, slug: str, ctx: ContextTypes.DEFAULT_TYPE):
    """Envía el archivo sin música + caption + links de todas las redes."""
    from . import crosspost

    d = None
    for base in (UPLOADED_DIR, PENDING_DIR):
        if (base / slug).exists():
            d = base / slug
            break
    if d is None:
        await ctx.bot.send_message(chat_id, "No encuentro el video.")
        return
    scripts = service.script.load_scripts(d)
    loc = scripts.es
    caption = crosspost.build_caption(loc)

    # Versión SIN subtítulos quemados (TikTok/Reels autogeneran captions) + share ligero
    from . import compose
    f = None
    try:
        nosubs = await _run_blocking(lambda: service.recompose_no_subs(slug, "es"))
        if nosubs:
            f = await _run_blocking(lambda: compose.make_share(nosubs, nosubs.with_name("share_nosubs_es.mp4")))
    except Exception:
        f = None
    if f is None:
        f = crosspost.crosspost_file(d, "es")  # fallback (con subs)

    # Archivo CON música+voz (autosuficiente, súbelo tal cual)
    if f and f.exists():
        try:
            with open(f, "rb") as fh:
                await ctx.bot.send_video(
                    chat_id, video=fh,
                    caption="📥 Para cross-post: SIN subtítulos (TikTok/Reels los autogeneran) · voz + música · súbelo tal cual.",
                    read_timeout=300, write_timeout=300, connect_timeout=60,
                )
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"⚠️ No pude enviar el archivo: {e}")

    links = "\n".join(
        f"• {p['name']}: {p['url']}" + (f"  ({p['note']})" if p["note"] else "")
        for p in crosspost.PLATFORMS.values()
    )
    await ctx.bot.send_message(
        chat_id,
        f"🔁 *Cross-post* (multiplica alcance gratis):\n\n"
        f"1️⃣ Descarga el archivo de arriba al móvil.\n"
        f"2️⃣ En cada app, dale a *+* y elige el video de la galería:\n{links}\n\n"
        f"⚠️ *NO le pongas canción encima* — ya tiene voz + música. Si añades audio trending, "
        f"déjalo a volumen MUY bajo y sube el 'sonido original' al máximo para que se oiga la voz.",
        parse_mode="Markdown",
    )
    # Caption aparte en bloque copiable (tap-to-copy en móvil)
    import html as _html
    await ctx.bot.send_message(
        chat_id,
        "📝 <b>Caption para la descripción</b> (cópialo y pégalo en cada red)\n\n"
        f"<pre>{_html.escape(caption)}</pre>",
        parse_mode="HTML",
    )


REMINDERS_FILE = (PENDING_DIR.parent / "reminders.json")


def _load_reminders() -> list[dict]:
    if not REMINDERS_FILE.exists():
        return []
    try:
        import json as _json
        return _json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_reminders(rs: list[dict]) -> None:
    import json as _json
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REMINDERS_FILE.write_text(_json.dumps(rs, indent=2, ensure_ascii=False), encoding="utf-8")


def add_reminder(slug: str, ts: float, platforms: str = "TikTok + Instagram") -> dict:
    """API pública: añade un recordatorio. El bot lo programa en su próxima
    arrancada (o vía _schedule_all_reminders si llamamos desde aquí)."""
    rs = _load_reminders()
    item = {"slug": slug, "ts": float(ts), "platforms": platforms}
    rs.append(item)
    _save_reminders(rs)
    return item


async def _reminder_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Disparado por JobQueue a la hora indicada: manda reminder + archivos + caption."""
    data = ctx.job.data or {}
    chat_id = ctx.job.chat_id
    slug = data.get("slug")
    platforms = data.get("platforms", "TikTok + Instagram")
    if not slug:
        return
    item = _find_slug(slug)
    title = (item or {}).get("title_es") or (item or {}).get("topic") or slug
    await ctx.bot.send_message(
        chat_id,
        f"⏰ *¡Es la hora!* Sube ahora «{title[:60]}» a *{platforms}*.\n"
        f"Te paso los 2 archivos + el caption listos para arrastrar.",
        parse_mode="Markdown",
    )
    await _send_videos(chat_id, slug, with_subs=True, without_subs=True, ctx=ctx, title=title)
    # Limpia este reminder del fichero (evita doble disparo si se reinicia)
    rs = _load_reminders()
    rs = [r for r in rs if not (r.get("slug") == slug and abs(r.get("ts", 0) - data.get("ts", 0)) < 1)]
    _save_reminders(rs)


def _schedule_all_reminders(application, chat_id: int) -> int:
    """Al arrancar el bot: carga reminders.json y programa los futuros."""
    import time as _time
    rs = _load_reminders()
    now = _time.time()
    n = 0
    for r in rs:
        when = float(r.get("ts", 0))
        if when <= now:
            continue
        application.job_queue.run_once(
            _reminder_job,
            when=when - now,
            data=r,
            chat_id=chat_id,
            name=f"rem:{r.get('slug')}:{int(when)}",
        )
        n += 1
    return n


async def _send_charts(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Snapshot + render + envío de las gráficas por plataforma."""
    from . import analytics

    def _do():
        analytics.snapshot_all()
        return analytics.render_all()

    try:
        charts = await _run_blocking(_do)
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"⚠️ Analytics falló: {e}")
        return
    if not charts:
        await ctx.bot.send_message(chat_id, "No hay datos aún para graficar.")
        return
    for plat, path in charts.items():
        try:
            with open(path, "rb") as fh:
                await ctx.bot.send_photo(
                    chat_id, photo=fh,
                    caption=f"📊 {plat.upper()} — últimos 30 días",
                )
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"⚠️ No pude enviar gráfica {plat}: {e}")


# Casos conocidos, orden = prioridad (más específico primero para evitar que
# "Popular" gane a "Banco Popular" o similar). Cada entry mapea → nombre corto
# canónico que aparecerá en los títulos de Shorts atomizados.
_KNOWN_CASES: list[tuple[str, str]] = [
    ("ruiz-mateos", "Ruiz-Mateos"), ("rumasa", "RUMASA"),
    ("gürtel", "Gürtel"), ("gurtel", "Gürtel"),
    ("bárcenas", "Bárcenas"), ("barcenas", "Bárcenas"),
    ("mario conde", "Mario Conde"), ("banesto", "Banesto"),
    ("fórum filatélico", "Fórum Filatélico"), ("forum filatelico", "Fórum Filatélico"),
    ("afinsa", "AFINSA"), ("nummers", "Fórum Filatélico"),
    ("ere andalucía", "ERE Andalucía"), ("ere andalucia", "ERE Andalucía"),
    ("aceite de colza", "Colza"), ("colza", "Colza"),
    ("urdangarin", "Urdangarin"), ("nóos", "Nóos"), ("noos", "Nóos"),
    ("bankia", "Bankia"), ("preferentes", "Preferentes"),
    ("villarejo", "Villarejo"), ("púnica", "Púnica"), ("punica", "Púnica"),
    ("popular", "Banco Popular"),
    ("arbistar", "Arbistar"), ("kuailian", "Kuailian"),
    ("idental", "iDental"), ("gescartera", "Gescartera"),
    ("filesa", "Filesa"), ("matesa", "MATESA"), ("ibercorp", "Ibercorp"),
    ("palma arena", "Palma Arena"), ("pescanova", "Pescanova"),
    ("malaya", "Malaya"), ("roca", "Malaya"), ("marbella", "Malaya"),
    ("terra networks", "Terra"), ("airtel", "Airtel"),
]


def _case_prefix_from(topic: str) -> str:
    """Extrae un identificador corto del caso desde el topic del long-form
    para prefijar los títulos de los Shorts atomizados y evitar que colisionen
    entre casos distintos (bug: "La Intervención y el Escándalo 👀" se subió
    2× — de Bárcenas y de otro caso, mismo título literal).

    Estrategia:
    1. Match contra _KNOWN_CASES (nombre canónico corto).
    2. Fallback: proper noun más largo del topic (mediante dedup_common).
    3. Fallback final: "Caso".
    """
    tl = topic.lower()
    for needle, name in _KNOWN_CASES:
        if needle in tl:
            return name
    # Fallback proper nouns (extendido para incluir ü/ï que el regex base no
    # cubre; también evita que "Ruiz-Mateos" se rompa en 2 tokens).
    import re as _re
    tokens = _re.findall(r"[A-ZÁÉÍÓÚÜÏÑ][a-záéíóúüïñ]{3,}(?:-[A-ZÁÉÍÓÚÜÏÑ][a-záéíóúüïñ]+)?", topic)
    from . import dedup_common
    filtered = [t for t in tokens if t.lower() not in dedup_common.NON_NOUNS_STOP]
    if filtered:
        return max(filtered, key=len)
    return "Caso"


def _upload_atomized_clip_as_short(
    clip_path, chapter_name: str, parent_topic: str,
    hashtags: list[str], publish_at_utc: str,
) -> str:
    """Sube un clip atomizado de un long-form como un YT Short independiente,
    programado a publish_at_utc. Devuelve el video_id."""
    from . import upload_youtube
    # Título: <Caso>: <capítulo> 👀 — el prefijo del caso evita colisiones
    # entre Shorts de long-forms distintos (bug 07-22/23: mismos títulos de
    # capítulos genéricos se solapaban entre casos).
    case = _case_prefix_from(parent_topic)
    title = f"{case}: {chapter_name} 👀"[:100]
    # SEO-boost: primeras 2 líneas visibles + CTA fuerte + playlist
    from . import service as _svc
    base_desc = f"{case} — {chapter_name}. Un fragmento del análisis completo (~9 min)."
    desc = _svc._enrich_description_seo(base_desc, f"{case}: {chapter_name}", hashtags, is_short=True)
    tags = [h.lstrip("#") for h in hashtags][:30]
    return upload_youtube.upload_video(
        clip_path,
        title=title,
        description=desc,
        tags=tags,
        privacy="public",
        is_short=True,
        publish_at=publish_at_utc,
    )


def _extract_case_names(titles: list[str]) -> list[str]:
    """Extrae nombres de casos de los títulos YT para pasarlos como
    exclusión a Gemini. Mira los patrones "Caso [X] —", "X: cómo Y", etc.
    """
    import re
    cases: set[str] = set()
    # Casos que sabemos que están (aunque el título no los liste explícito)
    KNOWN = [
        "Aceite de Colza", "Mario Conde / Banesto", "Fórum Filatélico / AFINSA",
        "RUMASA / Ruiz-Mateos", "Gescartera / Antonio Camacho",
        "Bankia / Rato", "Preferentes bancarias",
        "Bárcenas / Gürtel / Correa", "ERE Andalucía", "Idental",
        "Filesa", "Nóos / Urdangarin", "Malaya / Roca / Marbella",
        "Arbistar / Kuailian", "Popular vendido 1€",
    ]
    # Buscar heurística: si el keyword aparece en algún título, dar por cubierto
    lower_titles = " ".join(t.lower() for t in titles)
    for k in KNOWN:
        # Primera palabra del caso como keyword
        key = k.split(" ")[0].lower().rstrip(",")
        if key in lower_titles:
            cases.add(k)
    return sorted(cases)


def _shorts_published_today_count() -> int:
    """Cuenta shorts publicados hoy en YouTube (fuente de verdad persistente,
    a diferencia de list_history() local que es efímero en Actions).

    Falla → 0 para no bloquear autogen si YT API cae momentáneamente.
    """
    from datetime import datetime, timezone
    try:
        import json, requests
        from pathlib import Path
        tok_path = Path(__file__).parent.parent.parent / "secrets" / "youtube_token.json"
        tok = json.loads(tok_path.read_text())
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": tok["client_id"], "client_secret": tok["client_secret"],
            "refresh_token": tok["refresh_token"], "grant_type": "refresh_token",
        }, timeout=15).json()
        H = {"Authorization": f"Bearer {r['access_token']}"}
        ch = requests.get("https://www.googleapis.com/youtube/v3/channels",
                          params={"part": "contentDetails", "mine": "true"},
                          headers=H, timeout=15).json()
        upl = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        r = requests.get("https://www.googleapis.com/youtube/v3/playlistItems",
                         params={"part": "contentDetails,snippet",
                                 "playlistId": upl, "maxResults": 10},
                         headers=H, timeout=15).json()
        today = datetime.now(timezone.utc).date()
        n = 0
        for it in r.get("items", []):
            pub = it.get("snippet", {}).get("publishedAt", "")[:10]
            if pub and datetime.fromisoformat(pub).date() == today:
                n += 1
        return n
    except Exception as e:
        print(f"  _shorts_published_today_count: error {e}, devuelvo 0")
        return 0


def _autogen_already_today(max_per_day: int = 2) -> bool:
    """¿Ya se alcanzó el tope diario de shorts? (default: 2/día).

    Reemplaza al chequeo local basado en filesystem (roto en Actions) por un
    conteo real de uploads YT del día. `max_per_day=2` es la palanca C
    (2 shorts/día) para acelerar el ritmo de subida sin duplicar en el mismo
    slot.
    """
    return _shorts_published_today_count() >= max_per_day


def _next_episode_num(recent_titles: list[str]) -> int:
    """Devuelve el próximo #N para la serie "Estafas Españolas #N: ...".

    Extrae N de los títulos existentes vía regex "#(\\d+):" y devuelve max+1.
    Si no hay ninguno, arranca en #1. Es idempotente entre runs (fuente de
    verdad = YT API)."""
    import re as _re
    ns = []
    for t in recent_titles:
        m = _re.search(r"#(\d+)[:\s]", t)
        if m:
            try:
                ns.append(int(m.group(1)))
            except ValueError:
                pass
    return (max(ns) + 1) if ns else 1


def _longform_generated_this_week() -> bool:
    """¿Hay un long-form subido a YT en los últimos 6 días?

    IMPORTANTE: fuente de verdad = YouTube API (duración >150s). El filesystem
    local es efímero en GitHub Actions y devolvía siempre False, causando que
    el weekly-longform-catchup disparara 13× cada domingo (bug catastrófico
    26/07: 24 videos duplicados subidos en un día).
    """
    from datetime import datetime, timedelta, timezone
    try:
        import json, requests, re
        from pathlib import Path
        tok_path = Path(__file__).parent.parent.parent / "secrets" / "youtube_token.json"
        tok = json.loads(tok_path.read_text())
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": tok["client_id"], "client_secret": tok["client_secret"],
            "refresh_token": tok["refresh_token"], "grant_type": "refresh_token",
        }, timeout=15).json()
        H = {"Authorization": f"Bearer {r['access_token']}"}
        ch = requests.get("https://www.googleapis.com/youtube/v3/channels",
                          params={"part": "contentDetails", "mine": "true"},
                          headers=H, timeout=15).json()
        upl = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        pl = requests.get("https://www.googleapis.com/youtube/v3/playlistItems",
                          params={"part": "contentDetails,snippet",
                                  "playlistId": upl, "maxResults": 30},
                          headers=H, timeout=15).json()
        vids = [i["contentDetails"]["videoId"] for i in pl.get("items", [])]
        vres = requests.get("https://www.googleapis.com/youtube/v3/videos",
                            params={"part": "contentDetails,snippet",
                                    "id": ",".join(vids)},
                            headers=H, timeout=15).json()
        cutoff = datetime.now(timezone.utc) - timedelta(days=6)
        for v in vres.get("items", []):
            pub = v["snippet"].get("publishedAt")
            if not pub:
                continue
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if dt < cutoff:
                continue
            # Duración ISO 8601 (PT#M#S) — long-form si >= 3 min
            dur = v["contentDetails"].get("duration", "")
            m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur)
            if not m:
                continue
            secs = (int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60
                    + int(m.group(3) or 0))
            if secs >= 150:  # >= 2:30 → seguro es long-form, no Short
                print(f"  _longform_generated_this_week: FOUND {v['snippet']['title'][:50]} "
                      f"({secs}s, {pub[:10]})")
                return True
        return False
    except Exception as e:
        print(f"  _longform_generated_this_week: YT API fail ({e}) — devolvió False")
        return False


async def _weekly_longgen_catchup(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Catchup del job semanal de long-form. Corre cada hora en domingo (10-22)
    y lunes (10-14). Si esta semana no se ha creado long-form todavía y la Mac
    está despierta ahora, dispara. Idempotente: si ya hay long-form reciente,
    no hace nada."""
    from datetime import datetime
    now = datetime.now().astimezone()
    wd, hr = now.weekday(), now.hour
    # Solo domingo 10-22 o lunes 10-14 (buffer si domingo pasó de largo)
    valid = (wd == 6 and 10 <= hr < 22) or (wd == 0 and 10 <= hr < 14)
    if not valid:
        return
    if _longform_generated_this_week():
        return
    await _auto_generate_weekly_longform(ctx)


async def _hourly_autogen_check(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Ejecuta cada hora. Si la Mac estaba dormida a las 08:00 y se despierta
    más tarde, este job pilla el primer momento útil del día y genera. Solo
    actúa entre 08-22 (no de noche) y si hoy no se ha generado nada todavía."""
    from datetime import datetime
    now = datetime.now().astimezone()
    if now.hour < 8 or now.hour >= 22:
        return  # noche, dejamos descansar
    if _autogen_already_today():
        return  # ya hay vídeo de hoy, no spamear
    # No hay nada hoy y la Mac está despierta → genera ahora
    await _auto_generate_daily_short(ctx)


async def _auto_generate_weekly_longform(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Job semanal (domingos 10:00): genera long-form + atomiza + programa todo.
    Wrapper con lock cross-job."""
    chat_id = ctx.job.chat_id
    if not _acquire_generation_lock("longgen_weekly", ttl_seconds=3600):  # 1h TTL
        await ctx.bot.send_message(chat_id, "⏳ Otra generación en curso — longgen pospuesto.")
        return
    try:
        await _run_longgen_weekly(chat_id, ctx)
    finally:
        _release_generation_lock()


async def _run_longgen_weekly(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Cuerpo del longgen semanal (sin lock)."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from . import ideas, atomize, script, compose, crosspost

    await ctx.bot.send_message(chat_id, "🎬 *Long-form semanal iniciado*", parse_mode="Markdown")

    # 0. Token check
    ok, reason = _check_yt_token()
    if not ok:
        await _send_yt_token_alert(chat_id, ctx, reason)
        return

    # 1. Ideas frescas + dedup vs long-forms ya generados
    # Casos ya cubiertos → pasar como exclusión a Gemini (mismo fix que autogen)
    try:
        # days=180: solo bloquea casos publicados últimos 6 meses. Un caso más
        # viejo puede revisitarse con nuevo ángulo. Fix bug 08-12 (dedup eterno).
        recent_pre = await _run_blocking(lambda: stats.fetch_recent_titles(50, days=180))
        exclude_long = _extract_case_names(recent_pre)
    except Exception:
        exclude_long = []
    ideas_list = []
    for attempt in range(3):
        try:
            ideas_list = await _run_blocking(
                lambda: ideas.generate_ideas(10, exclude_cases=exclude_long)
            )
            if ideas_list:
                break
        except Exception:
            pass
        if attempt < 2:
            await asyncio.sleep(15 * (attempt + 1))
    if not ideas_list:
        await ctx.bot.send_message(chat_id, "❌ Gemini sin respuesta para ideas, abort.")
        return

    # Dedup vs long-forms + shorts ya subidos. Fuente de verdad: YouTube API
    # (persistente entre Actions runs, filesystem local es efímero). Usa el
    # módulo `dedup_common` compartido con autogen para 3 capas:
    #   - substring del topic completo
    #   - intersección de nombres propios (regex MixedCase + ALLCAPS)
    #   - KEYWORDS_ALREADY_COVERED (blacklist manual — CRÍTICO: sin esto el
    #     26/07 se generaron 4 longforms duplicados de Colza/Fórum/RUMASA)
    from . import dedup_common
    recent_titles: list[str] = []
    try:
        recent_titles = await _run_blocking(lambda: stats.fetch_recent_titles(50, days=180))
        print(f"  longgen dedup: {len(recent_titles)} títulos últimos 180 días desde YT API")
    except Exception as e:
        print(f"  longgen dedup: fallo YT API ({e}) — fallback local")
        for it in service.list_history()[:30]:
            for f in ("topic", "title_es", "title_en"):
                v = str(it.get(f) or "")
                if v:
                    recent_titles.append(v)

    seen_titles = {t.lower() for t in recent_titles if t}
    recent_nouns: set[str] = set()
    for t in recent_titles:
        recent_nouns |= dedup_common.proper_nouns(t)
    fresh, skipped = dedup_common.dedup_ideas(ideas_list, seen_titles, recent_nouns)
    for idea, reason in skipped:
        print(f"  longgen: SKIP {reason} — «{idea[:60]}»")
    if not fresh:
        msg = "⚠️ Todas las ideas ya cubiertas en YT (título/propn/keyword). Abort."
        print(msg)
        await ctx.bot.send_message(chat_id, msg)
        return
    topic = fresh[0]
    print(f"  longgen: topic elegido «{topic[:80]}»")
    try:
        from . import case_ledger
        key = case_ledger.register_used_case(topic)
        if key:
            print(f"  case_ledger: registrado key={key}")
    except Exception as _e:
        print(f"  case_ledger: skip ({type(_e).__name__}: {_e})")
    await ctx.bot.send_message(chat_id, f"📝 Topic long-form: «{topic[:80]}»\n⚙️ Generando (~10-15 min)…")

    # 2. Genera long-form — DURACIÓN ROTATIVA para escapar del detector
    # "rythm of bot-driven production" (YT 2026): en vez de siempre ~8 min,
    # rota entre 5, 8, 12 según el día ISO del año — patrón determinista pero
    # variable, sin randomness (evita drift entre runs).
    import datetime as _dt2
    _rot = [5, 8, 12][_dt2.datetime.now(_dt2.timezone.utc).isocalendar().week % 3]
    print(f"  longgen: target_minutes rotativo esta semana → {_rot}")
    try:
        slug = await _run_blocking(
            lambda: service.generate_long(topic, target_minutes=_rot, langs=("es",), progress=lambda m: None)
        )
        print(f"  longgen: long-form generado slug={slug}")
    except Exception as e:
        import traceback as _tb
        _tb.print_exc()
        print(f"  longgen: ❌ generate_long falló → {type(e).__name__}: {e}")
        await ctx.bot.send_message(chat_id, f"❌ Generación long falló: {type(e).__name__}: {str(e)[:300]}")
        return

    # 3. Programa long-form para HOY 20:00 CEST (si tarde, mañana)
    now = datetime.now().astimezone()
    long_target = now.replace(hour=20, minute=0, second=0, microsecond=0)
    if long_target <= now + timedelta(hours=2):
        long_target = long_target + timedelta(days=1)
    publish_at_long = long_target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        links = await _run_blocking(
            lambda: service.publish_long(slug, langs=("es",), privacy="public",
                                         progress=lambda m: None, notify=False,
                                         publish_at=publish_at_long)
        )
        # Playlist segmentada + first-comment strategy para long-form
        try:
            long_url = links.get('es', '')
            if long_url:
                long_video_id = long_url.rsplit("/", 1)[-1].split("?")[0]
                from . import playlists as _pl
                _pl.add_video_to_category(long_video_id, topic)
                # First-comment se hace por catchup (bug 08-17: scheduled → 403)
        except Exception as e:
            print(f"  longgen: ⚠ post-publish hooks error {type(e).__name__}: {e}")

        # Regenerar feed de podcast (Spotify/Apple) — cada long-form es un
        # episodio automático. El feed.xml + los MP3 se commitean en docs/
        # y GitHub Pages los sirve. new_slug=slug fuerza copia del MP3 recién
        # generado (que aún vive en output/uploaded/, no en docs/).
        try:
            from . import podcast_feed as _pf
            _pf.rebuild_feed(new_slug=slug)
        except Exception as e:
            print(f"  longgen: ⚠ podcast feed error {type(e).__name__}: {e}")
        await ctx.bot.send_message(
            chat_id,
            f"🗓 Long-form programado <b>{long_target.strftime('%d/%m %H:%M %Z')}</b>\n{links.get('es','')}",
            parse_mode="HTML",
        )
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"⚠️ Schedule long falló: {e}")
        return

    # 4. Atomizar (5 clips TT-native, sin mención YT)
    try:
        clips = await _run_blocking(
            lambda: atomize.atomize_native(slug, lang="es", progress=lambda m: None)
        )
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"⚠️ Atomize falló: {e}")
        return

    # Pausa entre el upload del long-form y el primer clip (rate limit interno).
    # 5 min de margen para no disparar cooldown YT de bursts en canales pequeños.
    await asyncio.sleep(300)

    # 5. Sube cada clip como YT Short, programado lun-vie 21:00 CEST a partir de mañana
    scripts_long = script.load_long_scripts(
        UPLOADED_DIR / slug if (UPLOADED_DIR / slug).exists() else PENDING_DIR / slug
    )
    loc = scripts_long.es

    # Encontrar el lunes próximo
    days_until_mon = (0 - now.weekday()) % 7
    if days_until_mon == 0:  # hoy es lunes, próximo = en 7 días
        days_until_mon = 7
    monday = now + timedelta(days=days_until_mon)
    monday_21 = monday.replace(hour=21, minute=0, second=0, microsecond=0)

    short_links = []
    for i, clip in enumerate(clips[:5]):
        ch_name = loc.chapters[i].name if i < len(loc.chapters) else f"Cap {i+1}"
        clip_target = monday_21 + timedelta(days=i)
        publish_at = clip_target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            vid = await _run_blocking(
                lambda c=clip, n=ch_name, p=publish_at: _upload_atomized_clip_as_short(
                    c, n, topic, loc.hashtags, p,
                )
            )
            url = f"https://youtube.com/shorts/{vid}"
            short_links.append((clip_target, ch_name, url))
            # Playlist segmentada. First-comment lo hace el catchup 2h.
            try:
                from . import playlists as _pl
                _pl.add_video_to_category(vid, topic)
            except Exception as _e:
                print(f"  longgen: ⚠ atom playlist add {type(_e).__name__}: {_e}")
            await ctx.bot.send_message(
                chat_id,
                f"📅 Clip {i+1}/5 «{ch_name}» → {clip_target.strftime('%a %d/%m %H:%M')} · {url}",
            )
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"⚠️ Clip {i+1} falló: {e}")
        # RATE LIMIT INTERNO: espera 5 min entre clip y clip para NO disparar el
        # cooldown de reputación de YT (canales <100 subs son sensibles a bursts).
        # Salto para el último clip.
        if i < len(clips[:5]) - 1:
            await asyncio.sleep(300)

    # 6. Manda los 5 clips a Telegram para TT/IG manuales
    import html as _html
    await ctx.bot.send_message(
        chat_id,
        f"📦 Te paso los 5 clips también para TT/IG (manuales)…",
    )
    bait_qs = atomize._generate_bait_questions(scripts_long, "es")
    for i, clip in enumerate(clips[:5]):
        ch_name = loc.chapters[i].name if i < len(loc.chapters) else f"Cap {i+1}"
        bait = bait_qs[i] if i < len(bait_qs) else "¿Lo sabías?"
        cap = atomize.build_clip_caption_native(loc, ch_name, bait)
        try:
            with open(clip, "rb") as fh:
                await ctx.bot.send_video(
                    chat_id, video=fh,
                    caption=f"🎬 Native {i+1}/5 · {ch_name}",
                    read_timeout=300, write_timeout=300, connect_timeout=60,
                    supports_streaming=True,
                )
            await ctx.bot.send_message(
                chat_id,
                f"📝 <b>Caption {i+1}</b>\n\n<pre>{_html.escape(cap)}</pre>",
                parse_mode="HTML",
            )
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"⚠️ Envío clip {i+1}: {e}")

    await ctx.bot.send_message(
        chat_id,
        "✅ *Semana programada*: 1 long-form hoy + 5 Shorts derivados lun-vie\n"
        "+ los 5 archivos en este chat para TT/IG cuando quieras.",
        parse_mode="Markdown",
    )


async def longgen_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/longgen → dispara la generación semanal AHORA (idem job domingo 10:00)."""
    class _FakeJob:
        chat_id = update.effective_chat.id
    ctx.job = _FakeJob()
    await _auto_generate_weekly_longform(ctx)


async def autogen_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/autogen → dispara la generación diaria AHORA (mismo flujo del job 08:00)."""
    class _FakeJob:
        chat_id = update.effective_chat.id
    ctx.job = _FakeJob()
    await _auto_generate_daily_short(ctx)


async def snapshot_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/snapshot → fuerza un snapshot ahora y manda las gráficas."""
    await update.message.reply_text("📸 Tomando snapshot…")
    await _send_charts(update.effective_chat.id, ctx)


async def tiktok_auth_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/tiktok_auth → link inline para autorizar TikTok via OAuth desde el móvil.

    Callback en Vercel guarda TIKTOK_ACCESS_TOKEN + REFRESH_TOKEN + OPEN_ID como
    GH Secrets, y avisa por Telegram. Ver vercel-webhook/api/tiktok-callback.js.
    """
    import os
    webhook_base = os.environ.get("WEBHOOK_URL", "").rstrip("/")
    chat_id = update.effective_chat.id
    if not webhook_base:
        await update.message.reply_text(
            "🔴 WEBHOOK_URL no configurado — no puedo generar link OAuth."
        )
        return
    auth_url = f"{webhook_base}/api/tiktok-auth?t={chat_id}"
    reply_markup = {
        "inline_keyboard": [[
            {"text": "🎵 Conectar TikTok (30s)", "url": auth_url}
        ]]
    }
    await ctx.bot.send_message(
        chat_id,
        "🎵 <b>Conectar TikTok</b>\n\n"
        "Tap el botón → autoriza a WaitWhy Autopost en TikTok → "
        "tokens se guardan solos.\n\n"
        "Al terminar te llegará confirmación aquí con los scopes activos.",
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


import time as _time
_GENERATION_LOCK = PENDING_DIR.parent / ".generation.lock"


def _acquire_generation_lock(kind: str, ttl_seconds: int = 1800) -> bool:
    """Lock cross-job para evitar paralelizar generaciones (que revientan cuota Gemini).
    Devuelve True si adquirido, False si otro job lleva el lock. TTL: 30 min por defecto
    (para que un job muerto no bloquee eternamente)."""
    now = _time.time()
    if _GENERATION_LOCK.exists():
        try:
            age = now - _GENERATION_LOCK.stat().st_mtime
            if age < ttl_seconds:
                return False
            _GENERATION_LOCK.unlink()  # lock viejo, lo consideramos huérfano
        except Exception:
            pass
    try:
        _GENERATION_LOCK.parent.mkdir(parents=True, exist_ok=True)
        _GENERATION_LOCK.write_text(f"{kind} {now:.0f}")
        return True
    except Exception:
        return False


def _release_generation_lock() -> None:
    try:
        _GENERATION_LOCK.unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _check_yt_token() -> tuple[bool, str]:
    """Devuelve (ok, msg). Detecta token YT caducado para alertar antes de subir."""
    try:
        from . import stats
        ch = stats.fetch_channel_stats()
        if ch is None:
            return False, "Token YT no encontrado o sin permisos."
        return True, ""
    except Exception as e:
        s = str(e)
        if "invalid_grant" in s or "RefreshError" in type(e).__name__:
            return False, "token YT caducado (Google revoca cada ~7 días en Testing mode)"
        return False, f"{type(e).__name__}: {s[:120]}"


async def _send_yt_token_alert(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE, reason: str) -> None:
    """Alerta de token YT caducado con botón inline para reauth desde móvil.

    Si WEBHOOK_URL está configurado, muestra botón que abre el flow OAuth en
    Safari/Chrome del móvil → 30s → done. Fallback: instrucciones CLI para
    hacer en el Mac.
    """
    import os
    webhook_base = os.environ.get("WEBHOOK_URL", "").rstrip("/")

    text = (
        f"🚨 <b>TOKEN YT CADUCADO</b>\n"
        f"El autogen no puede subir videos hasta que renueves.\n\n"
        f"<i>Causa: {reason[:200]}</i>"
    )

    reply_markup = None
    if webhook_base:
        # Botón inline con URL — abre en el navegador del móvil
        auth_url = f"{webhook_base}/api/yt-auth?t={chat_id}"
        reply_markup = {
            "inline_keyboard": [[
                {"text": "🔐 Renovar token YT (30s)", "url": auth_url}
            ]]
        }
        text += (
            "\n\n<b>Tap el botón</b> → autoriza en Google → "
            "el token se actualiza solo. Volveras a este chat con la "
            "confirmación."
        )
    else:
        # Fallback CLI si WEBHOOK_URL no configurado
        text += (
            "\n\n<b>Fix (30 seg en el Mac):</b>\n"
            "<pre>cd ~/automated-videos\n.venv/bin/videogen reauth</pre>"
        )

    # ctx.bot.send_message acepta reply_markup en PTB; en HTTP runner
    # necesitamos pasarlo como kwarg (nuestro _post lo acepta como json extra).
    kwargs = {"parse_mode": "HTML"}
    if reply_markup:
        kwargs["reply_markup"] = reply_markup
    await ctx.bot.send_message(chat_id, text, **kwargs)


async def _auto_generate_daily_short(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Job diario: genera 1 Short, lo programa a YT para esa noche (21:00 CEST),
    manda la versión sin subs a Telegram para TT/IG manuales. Dedup contra historial."""
    chat_id = ctx.job.chat_id
    if not _acquire_generation_lock("autogen_daily"):
        logging.info("autogen daily: skip, otra generación en curso")
        return
    try:
        await _run_autogen_daily(chat_id, ctx)
    finally:
        _release_generation_lock()


async def _run_autogen_daily(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Cuerpo del autogen diario (sin manejo de lock)."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from . import ideas, compose, crosspost

    # Sin mensaje "iniciada" — reduce ruido. Solo se manda el resumen al final.
    print("  autogen: iniciada")

    ok, reason = _check_yt_token()
    if not ok:
        await _send_yt_token_alert(chat_id, ctx, reason)
        return

    # Casos ya cubiertos → pasarlos a Gemini como exclusión explícita.
    # Sin esto Gemini insiste con los mismos 8 casos del inicio del brief
    # y el dedup bloquea TODO (bug 28/07). days=90: solo últimos 3 meses,
    # tras eso permite revisitar con nuevo ángulo (bug 08-12).
    try:
        recent_titles_pre = await _run_blocking(lambda: stats.fetch_recent_titles(50, days=90))
        exclude = _extract_case_names(recent_titles_pre)
    except Exception:
        exclude = []

    ideas_list = []
    for attempt in range(3):
        try:
            ideas_list = await _run_blocking(
                lambda: ideas.generate_ideas(8, exclude_cases=exclude)
            )
            if ideas_list:
                break
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"⚠️ Ideas falló (intento {attempt+1}/3): {e}")
        if attempt < 2:
            await asyncio.sleep(15 * (attempt + 1))  # 15s, 30s
    if not ideas_list:
        await ctx.bot.send_message(chat_id, "❌ Gemini no devolvió ideas tras 3 intentos. Salto la generación de hoy.")
        return

    # 2. Deduplicar contra historial. Fuente de verdad = YouTube API, NO
    #    `service.list_history()` (lee filesystem local, que en GitHub Actions
    #    es efímero → dedup ciego → repite casos ya subidos).
    #    Capas:
    #    (a) substring del título completo (dedup exacto)
    #    (b) intersección de nombres propios con los últimos 20 uploads reales
    import re as _re
    import logging as _logging
    def _proper_nouns(s: str) -> set[str]:
        return {w.lower() for w in _re.findall(r"\b(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{3,}|[A-ZÁÉÍÓÚÑ]{4,})\b", s)}

    recent_titles: list[str] = []
    try:
        recent_titles = await _run_blocking(lambda: stats.fetch_recent_titles(50, days=90))
        print(f"  dedup: {len(recent_titles)} títulos últimos 90 días desde YT API")
    except Exception as e:
        print(f"  dedup: fallo YT API ({e}) — fallback a filesystem local")
        # Fallback al filesystem local (funciona en Mac, no en Actions)
        for it in service.list_history()[:20]:
            for f in ("topic", "title_es", "title_en"):
                v = str(it.get(f) or "")
                if v:
                    recent_titles.append(v)

    seen_titles = {t.lower() for t in recent_titles if t}
    recent_nouns: set[str] = set()
    for t in recent_titles:
        recent_nouns |= _proper_nouns(t)
    # Stopwords que no cuentan como nombre propio útil para dedup
    recent_nouns -= {"como", "cómo", "españa", "españoles", "españolas", "millones",
                     "banco", "bolsa", "estafa", "fraude", "caso", "sentencia",
                     "billones", "euros", "año", "años"}

    # Lista negra manual de casos ya cubiertos — red de seguridad cuando el fetch
    # de 50 títulos no basta (2 shorts/día + 5 clips/semana atomizados de long-forms
    # empujan videos importantes fuera del top-50 rápidamente). Los tokens se
    # buscan en minúsculas contra el `topic` de la idea.
    KEYWORDS_ALREADY_COVERED = {
        "colza", "aceite",            # Aceite de Colza (1981)
        "mario conde", "banesto",     # Banesto
        "fórum", "forum", "filatélico", "afinsa", "nummers",
        "rumasa", "ruiz-mateos", "ruiz mateos",
        "gescartera", "camacho",
        "bankia", "rato",
        "preferentes",
        "bárcenas", "barcenas", "gürtel", "gurtel", "correa",
        "ere andalucía", "ere andalucia",
        "idental",
        "filesa",
    }
    print(f"  dedup: nombres propios recientes = {sorted(recent_nouns)[:15]}…")

    fresh = []
    for idea in ideas_list:
        t = idea.lower().strip()
        if any(t in s or s in t for s in seen_titles if s):
            print(f"  dedup: SKIP substring match — «{idea[:60]}»")
            continue
        overlap = _proper_nouns(idea) & recent_nouns
        if overlap:
            print(f"  dedup: SKIP nombres propios {overlap} — «{idea[:60]}»")
            continue
        kw_hit = {kw for kw in KEYWORDS_ALREADY_COVERED if kw in t}
        if kw_hit:
            print(f"  dedup: SKIP keywords {kw_hit} — «{idea[:60]}»")
            continue
        fresh.append(idea)
    if not fresh:
        msg = "⚠️ Todas las ideas ya generadas o repiten casos recientes. Pasa /ideas para más."
        print(msg)
        await ctx.bot.send_message(chat_id, msg)
        return
    topic = fresh[0]

    # Palanca B — SERIE numerada: prefijar topic con "[Episodio #N ...]" para
    # que el prompt genere titles del tipo "Estafas Españolas #47: <hook>"
    # + thumbnail_text con "#47" grande. YT premia binge-watching de series.
    episode_num = _next_episode_num(recent_titles)
    topic_with_ep = (
        f"[Episodio #{episode_num} de la serie 'Estafas Españolas'. "
        f"El title DEBE seguir el patrón SEO 'Caso [NombreConocido] — [gancho] · #{episode_num}' "
        f"(o fallback '[Persona] — [dato shock] · #{episode_num}' si el caso no tiene nombre 'Caso X'). "
        f"El thumbnail_text DEBE mostrar la CIFRA clave del caso en 2 líneas (cifra + verbo emocional).] "
        f"{topic}"
    )
    print(f"  dedup: elegido «{topic[:80]}» — episodio #{episode_num}")
    # Registrar en el ledger para excluir del pool en futuras generaciones
    try:
        from . import case_ledger
        key = case_ledger.register_used_case(topic)
        if key:
            print(f"  case_ledger: registrado key={key}")
    except Exception as _e:
        print(f"  case_ledger: skip ({type(_e).__name__}: {_e})")
    await ctx.bot.send_message(
        chat_id,
        f"📝 Topic elegido (#Episodio {episode_num}): «{topic[:80]}»\n⚙️ Generando…"
    )

    # 3. Generar el Short
    try:
        slug = await _run_blocking(lambda: service.generate(topic_with_ep, ("es",), lambda m: None, ai_hero=True))
        print(f"  autogen: Short generado slug={slug}")
    except Exception as e:
        # Log a stdout + traceback para que aparezca en logs de Actions,
        # además del mensaje a Telegram.
        import traceback as _tb
        _tb.print_exc()
        print(f"  autogen: ❌ generación falló → {type(e).__name__}: {e}")
        await ctx.bot.send_message(chat_id, f"❌ Generación falló: {type(e).__name__}: {str(e)[:300]}")
        return

    # 4. Programar a YT — hora configurable vía env AUTOGEN_PUBLISH_HOUR (default 21 CEST)
    # A/B testing horarios: auditoría 30/07 sugiere que 14:00 CEST rinde 2x más que 21:00,
    # pero muestra pequeña. Los 2 workflows daily-short setean horas distintas para testear.
    import os as _os
    publish_hour = int(_os.environ.get("AUTOGEN_PUBLISH_HOUR", "21"))
    now = datetime.now().astimezone()
    target = now.replace(hour=publish_hour, minute=0, second=0, microsecond=0)
    if target <= now + timedelta(hours=2):  # menos de 2h → mañana
        target = target + timedelta(days=1)
    publish_at = target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    label_local = target.strftime("%d/%m %H:%M %Z")

    try:
        links = await _run_blocking(
            lambda: service.publish(slug, ("es",), "public", lambda m: None,
                                    notify=False, publish_at=publish_at)
        )
        yt_url = links.get('es', '')
        print(f"  autogen: YT publicado → {yt_url}")

        # Playlist segmentada. First-comment se hace por catchup cada 2h
        # después de que YT publique el video (bug 08-17: videos scheduled
        # están privados, comment API devuelve 403).
        try:
            if yt_url:
                video_id = yt_url.rsplit("/", 1)[-1]
                from . import playlists as _pl
                _pl.add_video_to_category(video_id, topic)
        except Exception as e:
            print(f"  autogen: ⚠ playlist add error {type(e).__name__}: {e}")

        # Mensaje YT diferido — se juntará con el resumen social al final.
        yt_msg = f"🗓 YT programado <b>{label_local}</b>\n{yt_url}"
    except Exception as e:
        import traceback as _tb
        _tb.print_exc()
        print(f"  autogen: ❌ schedule YT falló → {type(e).__name__}: {e}")
        await ctx.bot.send_message(chat_id, f"⚠️ Schedule YT falló: {type(e).__name__}: {str(e)[:300]}")
        return

    # 4b. Bluesky + Mastodon con formato viral (hook + cifra + reply thread).
    from . import bluesky_poster, mastodon_poster
    from .service import script as _script_mod
    from .config import UPLOADED_DIR
    slug_dir = UPLOADED_DIR / slug
    title_social = topic  # fallback
    teaser_social = ""
    if slug_dir.exists():
        try:
            loc = _script_mod.load_scripts(slug_dir).es
            title_social = loc.title
            # Teaser: hook 0-5s del guion, ya optimizado para viralizar
            if hasattr(loc, "teaser") and getattr(loc.teaser, "text", None):
                teaser_social = loc.teaser.text
        except Exception:
            pass

    # Post en todos los canales; los mensajes intermedios silenciados,
    # solo mostramos icono OK/skip en el resumen final.
    social_status: list[str] = []

    try:
        bsky_res = await _run_blocking(
            lambda: bluesky_poster.post_short_to_bluesky(title_social, yt_url, teaser=teaser_social)
        )
        social_status.append("🦋 Bluesky ✅" if (bsky_res and not bsky_res.get("dry_run")) else "🦋 —")
    except Exception as e:
        print(f"  autogen: bluesky skip ({type(e).__name__}: {e})")
        social_status.append("🦋 —")

    try:
        masto_res = await _run_blocking(
            lambda: mastodon_poster.post_short_to_mastodon(title_social, yt_url, teaser=teaser_social)
        )
        social_status.append("🐘 Mastodon ✅" if (masto_res and not masto_res.get("dry_run")) else "🐘 —")
    except Exception as e:
        print(f"  autogen: mastodon skip ({type(e).__name__}: {e})")
        social_status.append("🐘 —")

    # Reddit (title real del script)
    try:
        from . import reddit_poster
        loc_real = _script_mod.load_scripts(slug_dir).es if slug_dir.exists() else None
        title_real = loc_real.title if loc_real else topic
        result = await _run_blocking(lambda: reddit_poster.post_short_to_reddit(title_real, yt_url))
        social_status.append(f"🔴 r/{result['subreddit']} ✅" if (result and not result.get("dry_run")) else "🔴 —")
    except Exception as e:
        print(f"  autogen: reddit skip ({type(e).__name__}: {e})")
        social_status.append("🔴 —")

    try:
        from . import x_poster
        xr = await _run_blocking(lambda: x_poster.post_short_to_x(title_social, yt_url, teaser=teaser_social))
        social_status.append("🐦 X ✅" if (xr and not xr.get("dry_run")) else "🐦 —")
    except Exception as e:
        print(f"  autogen: x skip ({type(e).__name__}: {e})")
        social_status.append("🐦 —")

    try:
        from . import threads_poster
        tr = await _run_blocking(lambda: threads_poster.post_short_to_threads(title_social, yt_url, teaser=teaser_social))
        social_status.append("🧵 Threads ✅" if (tr and not tr.get("dry_run")) else "🧵 —")
    except Exception as e:
        print(f"  autogen: threads skip ({type(e).__name__}: {e})")
        social_status.append("🧵 —")

    try:
        from . import instagram_poster
        from .config import UPLOADED_DIR as _UD
        vertical_mp4 = _UD / slug / "video_es_vertical.mp4"
        ig_status = "📸 —"
        if vertical_mp4.exists():
            ir = await _run_blocking(
                lambda: instagram_poster.post_reel_to_instagram(
                    title_social, yt_url, vertical_mp4, slug, teaser=teaser_social,
                )
            )
            if ir and not ir.get("dry_run"):
                ig_status = "📸 IG ✅"
        social_status.append(ig_status)
    except Exception as e:
        print(f"  autogen: instagram skip ({type(e).__name__}: {e})")
        social_status.append("📸 —")

    try:
        from . import tiktok_poster
        from .config import UPLOADED_DIR as _UD
        vertical_mp4 = _UD / slug / "video_es_vertical.mp4"
        tt_status = "🎵 —"
        if vertical_mp4.exists():
            tr = await _run_blocking(
                lambda: tiktok_poster.post_video_to_tiktok(
                    title_social, vertical_mp4, slug,
                )
            )
            if tr and not tr.get("dry_run") and tr.get("publish_id"):
                kind = tr.get("kind", "?")
                tt_status = "🎵 TT ✅" if kind == "direct" else "🎵 TT 📥"  # 📥 = draft
        social_status.append(tt_status)
    except Exception as e:
        print(f"  autogen: tiktok skip ({type(e).__name__}: {e})")
        social_status.append("🎵 —")

    # UN solo mensaje final: YT + resumen social. Reduce ruido de 8 msg → 1.
    # (Eliminado el step "No-subs falló, omito TT/IG" — IG ya se cross-postea
    # automático arriba, y ese mensaje solo generaba ruido.)
    await ctx.bot.send_message(
        chat_id,
        f"{yt_msg}\n\n" + "  ·  ".join(social_status),
        parse_mode="HTML",
    )


async def _send_social_stats(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Reporta stats de Bluesky + Mastodon (followers + engagement 24h)."""
    import os
    lines = ["🦋🐘 <b>Redes sociales — últimas 24h</b>"]

    # Bluesky
    bh = os.environ.get("BLUESKY_HANDLE")
    bp = os.environ.get("BLUESKY_APP_PASSWORD")
    if bh and bp:
        try:
            from atproto import Client
            c = Client()
            profile = c.login(bh, bp)
            # Contar likes/reposts/replies en los últimos 5 posts propios
            feed = c.get_author_feed(profile.did, limit=10)
            recent_stats = []
            for item in feed.feed[:5]:
                p = item.post
                if p.author.did != profile.did:
                    continue
                recent_stats.append({
                    "likes": p.like_count or 0,
                    "reposts": p.repost_count or 0,
                    "replies": p.reply_count or 0,
                })
            total_likes = sum(x["likes"] for x in recent_stats)
            total_reposts = sum(x["reposts"] for x in recent_stats)
            lines.append(
                f"🦋 Bluesky @{bh}\n"
                f"  Followers: {profile.followers_count} · Following: {profile.follows_count}\n"
                f"  Últimos {len(recent_stats)} posts: {total_likes}❤ · {total_reposts}🔁"
            )
        except Exception as e:
            lines.append(f"🦋 Bluesky: fallo lectura ({type(e).__name__})")
    else:
        lines.append("🦋 Bluesky: no configurado")

    # Mastodon
    mi = os.environ.get("MASTODON_INSTANCE", "https://mastodon.social").rstrip("/")
    mt = os.environ.get("MASTODON_ACCESS_TOKEN")
    if mt:
        try:
            import requests as _req
            H = {"Authorization": f"Bearer {mt}"}
            me = _req.get(f"{mi}/api/v1/accounts/verify_credentials",
                          headers=H, timeout=15).json()
            # Últimos 5 toots + engagement
            toots = _req.get(f"{mi}/api/v1/accounts/{me['id']}/statuses",
                             headers=H, params={"limit": 5}, timeout=15).json()
            tf = sum(int(t.get("favourites_count", 0)) for t in toots)
            tr = sum(int(t.get("reblogs_count", 0)) for t in toots)
            lines.append(
                f"🐘 Mastodon @{me['username']}@{mi.replace('https://','')}\n"
                f"  Followers: {me.get('followers_count',0)} · Following: {me.get('following_count',0)}\n"
                f"  Últimos {len(toots)} toots: {tf}❤ · {tr}🔁"
            )
        except Exception as e:
            lines.append(f"🐘 Mastodon: fallo lectura ({type(e).__name__})")
    else:
        lines.append("🐘 Mastodon: no configurado")

    await ctx.bot.send_message(chat_id, "\n\n".join(lines), parse_mode="HTML")


def _fetch_youtube_totals() -> dict:
    """Devuelve totales del canal + top 3 videos del día + comentarios."""
    import json as _json, requests as _req
    from pathlib import Path
    tok_path = Path(__file__).parent.parent.parent / "secrets" / "youtube_token.json"
    tok = _json.loads(tok_path.read_text())
    r = _req.post("https://oauth2.googleapis.com/token", data={
        "client_id": tok["client_id"], "client_secret": tok["client_secret"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token",
    }, timeout=15).json()
    H = {"Authorization": f"Bearer {r['access_token']}"}
    ch = _req.get("https://www.googleapis.com/youtube/v3/channels",
                  params={"part": "statistics,contentDetails", "mine": "true"},
                  headers=H, timeout=15).json()
    st = ch["items"][0]["statistics"]
    upl = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    r = _req.get("https://www.googleapis.com/youtube/v3/playlistItems",
                 params={"part": "contentDetails,snippet",
                         "playlistId": upl, "maxResults": 15},
                 headers=H, timeout=15).json()
    vids_recent = [(i["contentDetails"]["videoId"],
                    i["snippet"]["publishedAt"],
                    i["snippet"]["title"]) for i in r.get("items", [])]
    ids = [v[0] for v in vids_recent]
    vres = _req.get("https://www.googleapis.com/youtube/v3/videos",
                    params={"part": "statistics,snippet,status", "id": ",".join(ids)},
                    headers=H, timeout=15).json()
    videos = []
    for v in vres.get("items", []):
        vst = v.get("statistics", {})
        # Filtrar videos aún privados/scheduled (aparecen con views=0
        # y contaminan el top3 del daily report — bug 08-17).
        if v.get("status", {}).get("privacyStatus") != "public":
            continue
        videos.append({
            "id": v["id"],
            "title": v["snippet"]["title"],
            "pub": v["snippet"]["publishedAt"],
            "views": int(vst.get("viewCount", 0)),
            "likes": int(vst.get("likeCount", 0)),
            "comments": int(vst.get("commentCount", 0)),
        })
    return {
        "subs": int(st.get("subscriberCount", 0)),
        "views": int(st.get("viewCount", 0)),
        "videos": int(st.get("videoCount", 0)),
        "recent": videos,
    }


def _prev_snapshot_from_history() -> dict:
    """Snapshot 'channel' más cercana a hace 20-30h para calcular Δ 24h.

    Antes usaba la última fila cualquiera → si el histórico tenía saltos
    largos, el delta se comparaba contra hace semanas y salían números
    inflados. Ahora prioriza filas con ts entre 20-30h atrás; si no hay,
    coge la más reciente que NO sea de hoy; fallback último.
    """
    import json as _json, time
    from pathlib import Path
    hp = Path(__file__).parent.parent.parent / "output" / "stats_history.jsonl"
    if not hp.exists():
        return {}
    now = time.time()
    channels = []
    for line in hp.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = _json.loads(line)
        except Exception:
            continue
        if row.get("kind") != "channel":
            continue
        ts = row.get("ts", 0)
        channels.append((ts, row))
    if not channels:
        return {}
    channels.sort(key=lambda x: x[0])

    # 1) Ideal: hace 20-30h
    ideal = [r for ts, r in channels if 20*3600 <= (now - ts) <= 30*3600]
    if ideal:
        return ideal[-1]
    # 2) La más reciente que sea de AYER (no de hoy) o antes
    today_ts = now - (now % 86400)  # 00:00 hoy UTC aprox
    older = [r for ts, r in channels if ts < today_ts]
    if older:
        return older[-1]
    # 3) Fallback: primera del día si solo hay filas de hoy
    return channels[0][1]


def _save_snapshot(subs: int, views: int, videos_n: int) -> None:
    """Añade fila 'channel' a stats_history para tracking futuro."""
    import json as _json, time
    from datetime import datetime
    from pathlib import Path
    hp = Path(__file__).parent.parent.parent / "output" / "stats_history.jsonl"
    hp.parent.mkdir(parents=True, exist_ok=True)
    row = {"platform": "youtube", "kind": "channel",
           "subs": subs, "views": views, "videos": videos_n,
           "source": "daily_summary", "ts": int(time.time()),
           "date": datetime.now().strftime("%Y-%m-%d")}
    with hp.open("a", encoding="utf-8") as f:
        f.write(_json.dumps(row) + "\n")


def _read_pinned_id() -> int | None:
    from pathlib import Path
    p = Path(__file__).parent.parent.parent / "output" / "pinned_summary_id.txt"
    if p.exists():
        try:
            return int(p.read_text().strip())
        except Exception:
            return None
    return None


def _write_pinned_id(msg_id: int) -> None:
    from pathlib import Path
    p = Path(__file__).parent.parent.parent / "output" / "pinned_summary_id.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(msg_id))


def _fmt_delta(cur: int, prev: int) -> str:
    d = cur - prev
    if d == 0:
        return "±0"
    return f"{d:+d}"


async def _build_daily_report(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Compone el mensaje ÚNICO del reporte diario y lo envía. Devuelve
    message_id para poder fijarlo."""
    from datetime import datetime, timedelta, timezone
    import os as _os

    # --- 1) YouTube global + delta 24h ---
    try:
        yt = await _run_blocking(_fetch_youtube_totals)
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"⚠️ Fallo YT API: {e}")
        return None
    prev = _prev_snapshot_from_history()
    d_subs = _fmt_delta(yt["subs"], int(prev.get("subs", yt["subs"])))
    d_views = _fmt_delta(yt["views"], int(prev.get("views", yt["views"])))
    d_videos = _fmt_delta(yt["videos"], int(prev.get("videos", yt["videos"])))
    _save_snapshot(yt["subs"], yt["views"], yt["videos"])

    # Top 3 videos del último día
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=30)
    recent_day = [v for v in yt["recent"]
                  if datetime.fromisoformat(v["pub"].replace("Z", "+00:00")) >= day_ago]
    recent_day.sort(key=lambda v: -v["views"])
    top3 = recent_day[:3]

    # Suma engagement 24h
    total_likes_24h = sum(v["likes"] for v in recent_day)
    total_comments_24h = sum(v["comments"] for v in recent_day)

    # --- 2) Bluesky ---
    bsky_line = "🦋 <b>Bluesky</b>: no configurado"
    try:
        bh = _os.environ.get("BLUESKY_HANDLE")
        bp = _os.environ.get("BLUESKY_APP_PASSWORD")
        if bh and bp:
            from atproto import Client as _BC
            c = _BC()
            p = c.login(bh, bp)
            feed = c.get_author_feed(p.did, limit=10)
            mine = [i.post for i in feed.feed if i.post.author.did == p.did][:5]
            tl = sum(pp.like_count or 0 for pp in mine)
            tr = sum(pp.repost_count or 0 for pp in mine)
            tc = sum(pp.reply_count or 0 for pp in mine)
            bsky_line = (f"🦋 <b>Bluesky</b> @{bh}\n"
                         f"   👥 {p.followers_count} followers · "
                         f"últimos {len(mine)} posts: {tl}❤ {tr}🔁 {tc}💬")
    except Exception:
        pass

    # --- 3) Mastodon ---
    masto_line = "🐘 <b>Mastodon</b>: no configurado"
    try:
        import requests as _req
        mi = _os.environ.get("MASTODON_INSTANCE", "https://mastodon.social").rstrip("/")
        mt = _os.environ.get("MASTODON_ACCESS_TOKEN")
        if mt:
            MH = {"Authorization": f"Bearer {mt}"}
            me = _req.get(f"{mi}/api/v1/accounts/verify_credentials",
                          headers=MH, timeout=15).json()
            ts = _req.get(f"{mi}/api/v1/accounts/{me['id']}/statuses",
                          headers=MH, params={"limit": 5}, timeout=15).json()
            tf = sum(int(t.get("favourites_count", 0)) for t in ts)
            tre = sum(int(t.get("reblogs_count", 0)) for t in ts)
            trp = sum(int(t.get("replies_count", 0)) for t in ts)
            masto_line = (f"🐘 <b>Mastodon</b> @{me['username']}\n"
                          f"   👥 {me['followers_count']} followers · "
                          f"últimos {len(ts)} toots: {tf}❤ {tre}🔁 {trp}💬")
    except Exception:
        pass

    # --- 4) Salud sistema: token YT + próximo cron ---
    token_ok, _ = _check_yt_token()
    token_line = "✅ activo" if token_ok else "🔴 CADUCADO — hacer /reauth"

    # --- 5) Compose mensaje HTML denso ---
    today_str = datetime.now().strftime("%d/%m/%Y")
    lines = [
        f"🌅 <b>Resumen {today_str}</b>",
        "",
        f"📺 <b>YouTube · @waitwhy_ybb</b>",
        f"   👥 Subs: <b>{yt['subs']}</b> ({d_subs})",
        f"   👁 Views: <b>{yt['views']:,}</b> ({d_views})",
        f"   🎬 Videos: <b>{yt['videos']}</b> ({d_videos})",
        f"   ❤ Likes 24h: <b>{total_likes_24h}</b>",
        f"   💬 Comentarios 24h: <b>{total_comments_24h}</b>",
        "",
    ]
    if top3:
        lines.append(f"🏆 <b>Top {len(top3)} de las últimas 24h</b>")
        for i, v in enumerate(top3, 1):
            title_short = v["title"][:55]
            lr = (v["likes"] / v["views"] * 100) if v["views"] > 0 else 0
            lines.append(
                f"   {i}. <b>{v['views']}v</b> · {v['likes']}❤ · "
                f"{v['comments']}💬 · {lr:.1f}%LR\n      <i>{title_short}</i>"
            )
        lines.append("")
    lines += [bsky_line, "", masto_line, "", "🤖 <b>Sistema</b>", f"   Token YT: {token_line}",
              "   Cron: daily-short 08:00+13:00 CEST · long-form dom 10:00",
              "",
              '<a href="https://youtube.com/playlist?list=PLK08iO9LACck">📼 Playlist Estafas Españolas</a>']
    text = "\n".join(lines)

    # Enviar y devolver message_id (compat PTB Message y HTTP dict runner)
    resp = await ctx.bot.send_message(chat_id, text, parse_mode="HTML",
                                       disable_web_page_preview=True)
    if hasattr(resp, "message_id"):
        return resp.message_id
    if isinstance(resp, dict):
        return resp.get("result", {}).get("message_id") or resp.get("message_id")
    return None


async def daily_summary(ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = ctx.job.chat_id

    # Health check token PRIMERO (si expirado, alerta visible antes)
    ok, reason = _check_yt_token()
    if not ok:
        await _send_yt_token_alert(chat_id, ctx, reason)

    # 1) Resumen ÚNICO como mensaje fijable
    new_msg_id = await _build_daily_report(chat_id, ctx)
    if new_msg_id:
        try:
            prev_id = _read_pinned_id()
            if prev_id and prev_id != new_msg_id:
                try:
                    await ctx.bot.unpin_chat_message(chat_id, prev_id)
                except Exception:
                    pass  # ya despinneado o eliminado
            await ctx.bot.pin_chat_message(chat_id, new_msg_id,
                                            disable_notification=True)
            _write_pinned_id(new_msg_id)
        except Exception as e:
            print(f"  daily_summary: pin fail ({e})")

    # 2) Gráficas + ideas (mensajes adicionales, no pineados)
    try:
        await _send_charts(chat_id, ctx)
    except Exception as e:
        print(f"  daily_summary: charts fail ({e})")
    try:
        await _send_ideas(chat_id, ctx, n=6)
    except Exception as e:
        print(f"  daily_summary: ideas fail ({e})")


def run():
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    app = (
        Application.builder()
        .token(telegram_token())
        .read_timeout(180)
        .write_timeout(180)
        .connect_timeout(60)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("ideas", ideas_cmd))
    app.add_handler(CommandHandler("ui", ui_cmd))
    app.add_handler(CommandHandler("optimal", optimal))
    # Handler global de errores: evita el flood de "No error handlers are registered"
    # y captura errores de parse Markdown/HTML sin exponer tracebacks al usuario.
    async def _on_error(update, ctx):
        import logging
        err = ctx.error
        msg = str(err)[:120]
        # Distinguir tipos comunes
        if "can't parse entities" in msg.lower() or "parse_mode" in msg.lower():
            logging.warning(f"Telegram parse error (msg descartado): {msg}")
        elif "connect" in msg.lower() or "nodename" in msg.lower() or "network" in msg.lower():
            logging.warning(f"Red temporalmente caída (se reintenta): {msg}")
        else:
            logging.error(f"Error no manejado: {type(err).__name__}: {msg}")
    app.add_error_handler(_on_error)

    app.add_handler(CommandHandler("send", send_cmd))
    app.add_handler(CommandHandler("snapshot", snapshot_cmd))
    app.add_handler(CommandHandler("atomize", atomize_cmd))
    app.add_handler(CommandHandler("autogen", autogen_cmd))
    app.add_handler(CommandHandler("longgen", longgen_cmd))
    app.add_handler(CommandHandler("tiktok_auth", tiktok_auth_cmd))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_prompt))

    # Menú de comandos de Telegram (los que aparecen al escribir "/")
    async def _set_commands(application):
        from telegram import BotCommand
        await application.bot.set_my_commands([
            BotCommand("ideas", "Ideas de video de hoy"),
            BotCommand("send", "Envía archivos del último (o por hint)"),
            BotCommand("snapshot", "Gráficas de stats por plataforma ahora"),
            BotCommand("atomize", "Saca clips promo de un long-form (slug)"),
            BotCommand("autogen", "Genera+programa+envía 1 Short ahora (idem job 08:00)"),
            BotCommand("longgen", "Genera long-form + 5 clips derivados + programa todo (idem job dom 10:00)"),
            BotCommand("tiktok_auth", "🎵 Conectar TikTok via OAuth (una vez)"),
            BotCommand("help", "Ayuda: qué puedo hacer"),
            BotCommand("stats", "Estadísticas de YouTube"),
            BotCommand("ui", "Enlace a la UI web"),
            BotCommand("optimal", "Mejores horas para publicar"),
            BotCommand("start", "Iniciar / ver chat id"),
        ])
    app.post_init = _set_commands

    # Resumen diario si hay chat_id configurado
    chat_id = telegram_chat_id()
    if chat_id:
        hhmm = os.environ.get("TELEGRAM_DAILY_HOUR", "09:00")
        try:
            h, m = map(int, hhmm.split(":"))
        except Exception:
            h, m = 9, 0
        app.job_queue.run_daily(
            daily_summary, time=dt.time(hour=h, minute=m), chat_id=int(chat_id)
        )
        # Job AUTOGEN: genera + programa + envía 1 Short diario
        ah_str = os.environ.get("AUTOGEN_HOUR", "08:00")
        try:
            ah, am = map(int, ah_str.split(":"))
        except Exception:
            ah, am = 8, 0
        app.job_queue.run_daily(
            _auto_generate_daily_short,
            time=dt.time(hour=ah, minute=am),
            chat_id=int(chat_id),
        )
        print(f"🤖 autogen diario a las {ah:02d}:{am:02d} (configurable: AUTOGEN_HOUR)")
        # Catchup horario: si la Mac estaba dormida a la hora del autogen,
        # cualquier hora útil del día (08-22) lo pilla y dispara.
        app.job_queue.run_repeating(
            _hourly_autogen_check,
            interval=3600,  # cada 1h
            first=120,      # primera ejecución en 2 min tras arrancar el bot
            chat_id=int(chat_id),
        )
        print("⏱  catchup horario activo (08-22h): si Mac dormía, dispara al despertar")
        # Job SEMANAL long-form: domingo 10:00 CEST. Genera + atomiza + programa todo.
        wh_str = os.environ.get("WEEKLY_LONG_HOUR", "10:00")
        try:
            wh, wm = map(int, wh_str.split(":"))
        except Exception:
            wh, wm = 10, 0
        app.job_queue.run_daily(
            _auto_generate_weekly_longform,
            time=dt.time(hour=wh, minute=wm),
            days=(6,),  # domingo (0=lun, 6=dom en PTB)
            chat_id=int(chat_id),
        )
        print(f"🎬 long-form semanal: domingos {wh:02d}:{wm:02d} (configurable: WEEKLY_LONG_HOUR)")
        # Catchup semanal: dispara aunque Mac durmiera el domingo — busca el
        # primer momento útil (dom 10-22 o lun 10-14) y si no hay long-form
        # esta semana, lo genera.
        app.job_queue.run_repeating(
            _weekly_longgen_catchup,
            interval=3600,  # cada 1h
            first=300,      # primera ejecución en 5 min tras arrancar
            chat_id=int(chat_id),
        )
        print("⏱  catchup semanal activo (dom 10-22 · lun 10-14): rescata la semana si Mac durmió")
        # Carga reminders pendientes (alertas TT/IG programadas)
        n = _schedule_all_reminders(app, int(chat_id))
        if n:
            print(f"⏰ {n} reminder(s) programados desde reminders.json")

    print("🤖 videogen bot corriendo. Ctrl+C para parar.")
    app.run_polling()
