"""Canal de difusión propio (Telegram) → palanca de tráfico externo a YouTube.

El funnel (25/09) demostró que el tráfico externo a YT viene de gente COMPARTIENDO
por mensajería (WhatsApp/Telegram), no de los crosspost automáticos a Bluesky/
Mastodon/Threads. Un canal PÚBLICO de Telegram que publique cada vídeo nuevo con su
enlace ataca justo esa fuente: Telegram no suprime links salientes y la gente reenvía.

Coste 0. Graceful: si no está configurado `TELEGRAM_BROADCAST_CHANNEL`, no hace nada.

Setup (una vez): crear un canal público de Telegram, añadir el bot como ADMIN, y
poner en GitHub Secrets `TELEGRAM_BROADCAST_CHANNEL` = @usuario_del_canal (o el id
-100…). El bot ya usa `TELEGRAM_BOT_TOKEN`.
"""
from __future__ import annotations

import os

# Nombre legible por prefijo de canal (para un mensaje bonito). Fallback: el prefijo.
_PREFIX_NAME = {
    "": "WaitWhy", "YT_TAX": "TaxHack", "YT_LEGAL": "TusDerechos",
    "YT_AYUDAS": "AyudaGob", "YT_MOTOR": "Motor60s", "YT_POV": "TiempoAtrás",
    "YT_RANKING": "TopRanking", "YT_AMBIENT": "MenteEnCalma", "YT_IA": "IA Autónomos",
    "YT_AITOOLS": "AI Tools Weekly", "YT_TRABAJOS": "CuriosLaboral",
    "YT_CRIMINOPATIA": "Criminopatía", "YT_RANKINGS": "Global Rankings",
}


def broadcast_new_video(title: str, video_id: str, channel_prefix: str = "") -> bool:
    """Publica el vídeo recién subido en el canal de difusión de Telegram.
    Devuelve True si se envió, False si no está configurado o falló (nunca lanza)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chan = os.environ.get("TELEGRAM_BROADCAST_CHANNEL", "").strip()
    if not (token and chan and video_id):
        return False
    name = _PREFIX_NAME.get(channel_prefix, channel_prefix or "WaitWhy")
    url = f"https://youtu.be/{video_id}"
    # Texto simple + link clicable (Telegram no lo suprime). El emoji + canal ayudan
    # a que sea reenviable/escaneable en un vistazo.
    text = f"🎬 <b>{name}</b>\n{(title or '').strip()[:200]}\n\n{url}"
    try:
        import requests
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chan, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": False},
            timeout=15,
        )
        if r.status_code == 200:
            print(f"  broadcast: ✅ {name} → canal Telegram")
            return True
        print(f"  broadcast: fail {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"  broadcast: skip ({type(e).__name__}: {str(e)[:80]})")
    return False


def broadcast_test() -> bool:
    """Envía un mensaje de prueba al canal de difusión para verificar config +
    que el bot es admin. Devuelve True si Telegram acepta el envío."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chan = os.environ.get("TELEGRAM_BROADCAST_CHANNEL", "").strip()
    if not token:
        print("broadcast-test: falta TELEGRAM_BOT_TOKEN"); return False
    if not chan:
        print("broadcast-test: falta TELEGRAM_BROADCAST_CHANNEL"); return False
    text = ("✅ <b>Canal de difusión conectado</b>\n"
            "Aquí se publicarán automáticamente los vídeos nuevos con su enlace de YouTube.")
    try:
        import requests
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chan, "text": text, "parse_mode": "HTML"}, timeout=15)
        if r.status_code == 200:
            print(f"broadcast-test: ✅ enviado a {chan}"); return True
        print(f"broadcast-test: ❌ {r.status_code} {r.text[:200]}")
        if "administrator" in r.text.lower() or "not enough rights" in r.text.lower() \
           or "chat not found" in r.text.lower():
            print("  → el bot NO es admin del canal (o el @usuario no es correcto).")
    except Exception as e:
        print(f"broadcast-test: error {type(e).__name__}: {str(e)[:120]}")
    return False
