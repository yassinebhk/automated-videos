#!/bin/bash
# Espera a que vuelva DNS y ejecuta snapshot analytics + saca views de los 2
# Mario Conde subidos el 13/07 para ver si el pivote true crime arranca.
# Auto-desregistra su propio LaunchAgent tras ejecutar (una única vez).

cd /Users/yassinebouhaikbouhoussaine/automated-videos
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH"

LOG=/tmp/snapshot_when_online.log
echo "[$(date '+%F %T')] arranca — esperando DNS…" >> "$LOG"

# Espera hasta 30 min a que resuelva DNS
for i in $(seq 1 60); do
    if host oauth2.googleapis.com >/dev/null 2>&1; then
        echo "[$(date '+%F %T')] DNS OK tras ${i} intentos" >> "$LOG"
        break
    fi
    sleep 30
done

if ! host oauth2.googleapis.com >/dev/null 2>&1; then
    echo "[$(date '+%F %T')] DNS sigue sin resolver tras 30min — abort" >> "$LOG"
    exit 1
fi

.venv/bin/python <<'PYEOF' >> "$LOG" 2>&1
import os, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path("/Users/yassinebouhaikbouhoussaine/automated-videos/.env"))
from videogen import analytics, stats
from videogen.config import telegram_chat_id

token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
chat = telegram_chat_id()
def tg(t):
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  json={"chat_id": chat, "text": t, "parse_mode": "HTML"}, timeout=15)

# 1) Snapshot general
try:
    counts = analytics.snapshot_all(progress=print)
    tg(f"📸 Snapshot forzado tras red caída: {counts}")
except Exception as e:
    tg(f"❌ Snapshot falló: {str(e)[:200]}")
    raise

# 2) Views concretos de los 2 Mario Conde del pivote true crime
TARGETS = {
    "YOuF92pkDYY": "Mario Conde/Banesto (10:32)",
    "-D8d3T4fF_o": "Mario Conde/Banesto (12:32) DUP",
}
try:
    s = stats.fetch_channel_stats()
    lines = ["📊 <b>Pivote true crime — views hoy</b>"]
    recent_by_id = {v.get("video_id"): v for v in s.get("recent", []) if v.get("video_id")}
    for vid, label in TARGETS.items():
        v = recent_by_id.get(vid)
        if v:
            lines.append(f"• {label}: <b>{v.get('views', 0)}v {v.get('likes', 0)}❤</b>")
        else:
            lines.append(f"• {label}: (no en top-recent — buscar por ID)")
    lines.append(f"\n<b>Canal:</b> {s.get('subs', '?')} subs · {s.get('views', '?')} views totales")
    tg("\n".join(lines))
except Exception as e:
    tg(f"❌ Fetch views Mario Conde falló: {str(e)[:200]}")
PYEOF

echo "[$(date '+%F %T')] fin" >> "$LOG"

# Auto-desregistrar
launchctl unload ~/Library/LaunchAgents/com.videogen.snapshot-wait.plist 2>/dev/null || true
rm -f ~/Library/LaunchAgents/com.videogen.snapshot-wait.plist
rm -f "$0"
