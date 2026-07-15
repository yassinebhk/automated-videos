#!/bin/bash
# Reintento único del Pizza IVA long-form. Se auto-elimina tras ejecutar.
cd /Users/yassinebouhaikbouhoussaine/automated-videos
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH"

.venv/bin/python3 <<'PYEOF' >> /tmp/pizza_retry.log 2>&1
import os, html, requests, time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv(Path("/Users/yassinebouhaikbouhoussaine/automated-videos/.env"))
from videogen import service, atomize, script, upload_youtube
from videogen.config import telegram_chat_id, PENDING_DIR, UPLOADED_DIR
token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
chat = telegram_chat_id()
def tg(t): requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat, "text": t}, timeout=15)

SLUG = "hacienda-te-roba-40-por-ciento-pizza-iva"
tg("⏰ Reintento programado Pizza IVA (cuota reset)")

try:
    links = service.publish_long(SLUG, langs=("es",), privacy="public",
                                  progress=print, notify=False,
                                  publish_at="2026-07-07T12:00:00Z")  # mar 14:00 CEST
    tg(f"🗓 Long-form YT mar 7/7 14:00: {links.get('es','')}")
except Exception as e:
    tg(f"❌ Long-form falló: {str(e)[:200]}")
    raise

time.sleep(60)

clips = atomize.atomize_native(SLUG, lang="es", progress=lambda m: None)
scripts_long = script.load_long_scripts(UPLOADED_DIR/SLUG if (UPLOADED_DIR/SLUG).exists() else PENDING_DIR/SLUG)
loc = scripts_long.es

target_monday = datetime(2026, 7, 20, 21, 0, tzinfo=timezone(timedelta(hours=2)))
for i, clip in enumerate(clips[:5]):
    ch_name = loc.chapters[i].name if i < len(loc.chapters) else f"Cap {i+1}"
    clip_target = target_monday + timedelta(days=i)
    pa = clip_target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    title = f"{ch_name} 👀"[:100]
    desc = (f"{ch_name} — fragmento del análisis completo.\n\n"
            f"Vídeo completo (~9 min) en el canal.\n\n"
            f"{' '.join(loc.hashtags)} #shorts")[:5000]
    try:
        vid = upload_youtube.upload_video(clip, title=title, description=desc,
            tags=[h.lstrip("#") for h in loc.hashtags][:30],
            privacy="public", is_short=True, publish_at=pa)
        tg(f"📅 Pizza {i+1}/5 «{ch_name}» → {clip_target.strftime('%a %d/%m %H:%M')}\nhttps://youtube.com/shorts/{vid}")
        time.sleep(30)
    except Exception as e:
        tg(f"⚠️ Pizza {i+1} falló: {str(e)[:200]}")

bait_qs = atomize._generate_bait_questions(scripts_long, "es")
for i, clip in enumerate(clips[:5]):
    ch_name = loc.chapters[i].name if i < len(loc.chapters) else f"Cap {i+1}"
    bait = bait_qs[i] if i < len(bait_qs) else "¿Lo sabías?"
    cap = atomize.build_clip_caption_native(loc, ch_name, bait)
    with open(clip, "rb") as fh:
        requests.post(f"https://api.telegram.org/bot{token}/sendVideo",
            data={"chat_id": chat, "caption": f"🎬 Pizza {i+1}/5 · {ch_name}", "supports_streaming":"true"},
            files={"video": fh}, timeout=300)
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": f"📝 <b>Caption Pizza {i+1}</b>\n\n<pre>{html.escape(cap)}</pre>",
              "parse_mode": "HTML"}, timeout=15)
tg("✅ Pizza IVA completo: long + 5 clips + archivos TG")
PYEOF

# Auto-desregistrar tras ejecutar (una única vez)
launchctl unload ~/Library/LaunchAgents/com.videogen.pizza-retry.plist 2>/dev/null || true
rm -f ~/Library/LaunchAgents/com.videogen.pizza-retry.plist
