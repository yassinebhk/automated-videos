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


def _upload_atomized_clip_as_short(
    clip_path, chapter_name: str, parent_topic: str,
    hashtags: list[str], publish_at_utc: str,
) -> str:
    """Sube un clip atomizado de un long-form como un YT Short independiente,
    programado a publish_at_utc. Devuelve el video_id."""
    from . import upload_youtube
    # Título corto y polarizante reutilizando el nombre del capítulo
    title = f"{chapter_name} 👀"[:100]
    desc = (
        f"{chapter_name} — un fragmento del análisis completo.\n\n"
        f"El vídeo completo (~9 min): en mi canal.\n\n"
        f"{' '.join(hashtags)} #shorts"
    )[:5000]
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


def _autogen_already_today() -> bool:
    """¿Hay algún vídeo generado hoy? (mira mtime de carpetas en history)."""
    from datetime import datetime
    today = datetime.now().astimezone().date()
    for it in service.list_history():
        try:
            mt = datetime.fromtimestamp(it.get("mtime", 0)).astimezone().date()
            if mt == today:
                return True
        except Exception:
            continue
    return False


def _longform_generated_this_week() -> bool:
    """¿Hay un long-form creado en los últimos 6 días? (dedup del catchup semanal).

    Itera directamente sobre PENDING/UPLOADED buscando `long_scripts.json` — no
    puede pasar por `list_history()` porque éste filtra por `scripts.json`
    (Shorts) y los long-forms no lo tienen, con lo que se perdía la señal y el
    catchup podía disparar 2 veces el mismo domingo (bug real 13/07/26)."""
    from datetime import datetime, timedelta
    cutoff = datetime.now().astimezone() - timedelta(days=6)
    for base in (UPLOADED_DIR, PENDING_DIR):
        if not base.exists():
            continue
        for d in base.iterdir():
            if not d.is_dir():
                continue
            f = d / "long_scripts.json"
            if not f.exists():
                continue
            try:
                mt = datetime.fromtimestamp(f.stat().st_mtime).astimezone()
                if mt >= cutoff:
                    return True
            except Exception:
                continue
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
    ideas_list = []
    for attempt in range(3):
        try:
            ideas_list = await _run_blocking(lambda: ideas.generate_ideas(10))
            if ideas_list:
                break
        except Exception:
            pass
        if attempt < 2:
            await asyncio.sleep(15 * (attempt + 1))
    if not ideas_list:
        await ctx.bot.send_message(chat_id, "❌ Gemini sin respuesta para ideas, abort.")
        return

    # Dedup vs long-forms + shorts ya subidos, usando la MISMA fuente de verdad
    # que autogen: los títulos reales de YouTube API (persistente entre Actions
    # runs, a diferencia de `service.list_history()` que lee el filesystem
    # local — efímero en GitHub Actions, causa por la que el 19/07 se repitió
    # Mario Conde en el weekly aunque ya se había subido el 13/07).
    import re as _re
    def _proper_nouns(s: str) -> set[str]:
        return {w.lower() for w in _re.findall(r"\b(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{3,}|[A-ZÁÉÍÓÚÑ]{4,})\b", s)}

    recent_titles: list[str] = []
    try:
        recent_titles = await _run_blocking(lambda: stats.fetch_recent_titles(30))
        print(f"  longgen dedup: {len(recent_titles)} títulos recientes desde YT API")
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
        recent_nouns |= _proper_nouns(t)
    recent_nouns -= {"como", "cómo", "españa", "españoles", "españolas", "millones",
                     "banco", "bolsa", "estafa", "fraude", "caso", "sentencia",
                     "billones", "euros", "año", "años"}
    print(f"  longgen dedup: nombres propios recientes = {sorted(recent_nouns)[:20]}…")

    fresh = []
    for idea in ideas_list:
        t = idea.lower().strip()
        if any(t in s or s in t for s in seen_titles if s):
            print(f"  longgen: SKIP substring — «{idea[:60]}»")
            continue
        overlap = _proper_nouns(idea) & recent_nouns
        if overlap:
            print(f"  longgen: SKIP nombres propios {overlap} — «{idea[:60]}»")
            continue
        fresh.append(idea)
    if not fresh:
        msg = "⚠️ Todas las ideas ya cubiertas en YT (por nombre propio). Abort."
        print(msg)
        await ctx.bot.send_message(chat_id, msg)
        return
    topic = fresh[0]
    print(f"  longgen: topic elegido «{topic[:80]}»")
    await ctx.bot.send_message(chat_id, f"📝 Topic long-form: «{topic[:80]}»\n⚙️ Generando (~10-15 min)…")

    # 2. Genera long-form
    try:
        slug = await _run_blocking(
            lambda: service.generate_long(topic, target_minutes=8, langs=("es",), progress=lambda m: None)
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
    await ctx.bot.send_message(
        chat_id,
        f"🚨 *TOKEN YT CADUCADO* — autogen no puede subir hoy.\n\n"
        f"Causa: {reason}\n\n"
        f"*Fix (30 seg, en tu Mac)*:\n"
        f"```\ncd ~/automated-videos\n.venv/bin/videogen reauth\n```\n"
        f"→ se abre el navegador → elige cuenta → acepta → listo.",
        parse_mode="Markdown",
    )


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

    await ctx.bot.send_message(chat_id, "🤖 *Generación diaria automática iniciada*", parse_mode="Markdown")

    ok, reason = _check_yt_token()
    if not ok:
        await _send_yt_token_alert(chat_id, ctx, reason)
        return

    ideas_list = []
    for attempt in range(3):
        try:
            ideas_list = await _run_blocking(lambda: ideas.generate_ideas(8))
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
        recent_titles = await _run_blocking(lambda: stats.fetch_recent_titles(20))
        print(f"  dedup: {len(recent_titles)} títulos recientes desde YT API")
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
        fresh.append(idea)
    if not fresh:
        msg = "⚠️ Todas las ideas ya generadas o repiten casos recientes. Pasa /ideas para más."
        print(msg)
        await ctx.bot.send_message(chat_id, msg)
        return
    topic = fresh[0]
    print(f"  dedup: elegido «{topic[:80]}»")
    await ctx.bot.send_message(chat_id, f"📝 Topic elegido: «{topic[:80]}»\n⚙️ Generando…")

    # 3. Generar el Short
    try:
        slug = await _run_blocking(lambda: service.generate(topic, ("es",), lambda m: None, ai_hero=True))
        print(f"  autogen: Short generado slug={slug}")
    except Exception as e:
        # Log a stdout + traceback para que aparezca en logs de Actions,
        # además del mensaje a Telegram.
        import traceback as _tb
        _tb.print_exc()
        print(f"  autogen: ❌ generación falló → {type(e).__name__}: {e}")
        await ctx.bot.send_message(chat_id, f"❌ Generación falló: {type(e).__name__}: {str(e)[:300]}")
        return

    # 4. Programar a YT para esa noche 21:00 CEST
    now = datetime.now().astimezone()
    target = now.replace(hour=21, minute=0, second=0, microsecond=0)
    if target <= now + timedelta(hours=2):  # menos de 2h → mañana
        target = target + timedelta(days=1)
    publish_at = target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    label_local = target.strftime("%d/%m %H:%M %Z")

    try:
        links = await _run_blocking(
            lambda: service.publish(slug, ("es",), "public", lambda m: None,
                                    notify=False, publish_at=publish_at)
        )
        print(f"  autogen: YT publicado → {links.get('es','')}")
        await ctx.bot.send_message(
            chat_id,
            f"🗓 YT programado <b>{label_local}</b>\n{links.get('es','')}",
            parse_mode="HTML",
        )
    except Exception as e:
        import traceback as _tb
        _tb.print_exc()
        print(f"  autogen: ❌ schedule YT falló → {type(e).__name__}: {e}")
        await ctx.bot.send_message(chat_id, f"⚠️ Schedule YT falló: {type(e).__name__}: {str(e)[:300]}")
        return

    # 5. Versión sin subs + caption → móvil para TT/IG
    try:
        nosubs = await _run_blocking(lambda: service.recompose_no_subs(slug, "es"))
        if not nosubs:
            await ctx.bot.send_message(chat_id, "⚠️ No-subs falló, omito TT/IG.")
            return
        share_ns = nosubs.with_name("share_nosubs_es.mp4")
        if not share_ns.exists():
            await _run_blocking(lambda: compose.make_share(nosubs, share_ns))
        loc = service.script.load_scripts(nosubs.parent).es
        cap = crosspost.build_caption(loc)
        with open(share_ns, "rb") as fh:
            await ctx.bot.send_video(
                chat_id, video=fh,
                caption=f"📥 {loc.title[:70]} · SIN subs (TT/IG)",
                read_timeout=300, write_timeout=300, connect_timeout=60,
                supports_streaming=True,
            )
        import html as _html
        await ctx.bot.send_message(
            chat_id,
            f"📝 <b>Caption</b>\n\n<pre>{_html.escape(cap)}</pre>",
            parse_mode="HTML",
        )
    except Exception as e:
        await ctx.bot.send_message(chat_id, f"⚠️ TT/IG falló: {e}")


async def daily_summary(ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = ctx.job.chat_id
    # Health check token: si caducado, alerta visible primero
    ok, reason = _check_yt_token()
    if not ok:
        await _send_yt_token_alert(chat_id, ctx, reason)
    await ctx.bot.send_message(
        chat_id,
        f"☀️ *Buenos días* — resumen diario\n\n"
        f"⏰ Sube hoy en:\n"
        f"▶️ YouTube: {stats.OPTIMAL_TIMES['youtube']}\n"
        f"🎵 TikTok: {stats.OPTIMAL_TIMES['tiktok']}",
        parse_mode="Markdown",
    )
    await _send_stats(chat_id, ctx)
    await _send_charts(chat_id, ctx)
    await _send_ideas(chat_id, ctx, n=6)


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
