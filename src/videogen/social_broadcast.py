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

# Hashtags por nicho para la búsqueda interna de Telegram (Public Post Search) y
# discovery. Set corto y relevante por prefijo; fallback genérico.
_PREFIX_TAGS = {
    "": "#corrupción #España #casojudicial #truecrime",
    "YT_TAX": "#autónomos #impuestos #España #dinero",
    "YT_LEGAL": "#derechos #laboral #España #trabajo",
    "YT_AYUDAS": "#ayudas #subvenciones #España",
    "YT_MOTOR": "#coches #motor #España",
    "YT_POV": "#historia #España #curiosidades",
    "YT_RANKING": "#ranking #top10 #datos",
    "YT_AMBIENT": "#relax #dormir #concentración",
    "YT_IA": "#IA #autónomos #tecnología",
    "YT_AITOOLS": "#AI #tech #productivity",
    "YT_CRIMINOPATIA": "#truecrime #España #crimen",
    "YT_TRABAJOS": "#empleo #trabajo #España",
}


def broadcast_new_video(title: str, video_id: str, channel_prefix: str = "") -> bool:
    """Publica el vídeo recién subido en el canal de difusión de Telegram.
    Devuelve True si se envió, False si no está configurado o falló (nunca lanza)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chan = os.environ.get("TELEGRAM_BROADCAST_CHANNEL", "").strip()
    if not (token and chan and video_id):
        return False
    name = _PREFIX_NAME.get(channel_prefix, channel_prefix or "WaitWhy")
    tags = _PREFIX_TAGS.get(channel_prefix, "#España #vídeo")
    url = f"https://youtu.be/{video_id}"
    # Texto simple + link clicable (Telegram no lo suprime) + hashtags ES (búsqueda
    # interna). El emoji + canal ayudan a que sea reenviable/escaneable en un vistazo.
    text = f"🎬 <b>{name}</b>\n{(title or '').strip()[:200]}\n\n{url}\n\n{tags}"
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


def setup_channel_seo() -> bool:
    """Pone nombre + descripción con keywords ES al canal (para búsqueda interna +
    recomendaciones de Telegram). Requiere que el bot sea admin con 'change info'.
    Graceful: si no tiene ese permiso, avisa (se puede poner a mano)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chan = os.environ.get("TELEGRAM_BROADCAST_CHANNEL", "").strip()
    if not (token and chan):
        print("setup-seo: falta TELEGRAM_BOT_TOKEN/CHANNEL"); return False
    title = "WaitWhy · Corrupción, Casos y Curiosidades ES"
    desc = ("🔎 Casos de corrupción y estafas en España (con sentencia y fuentes "
            "verificables), true crime, curiosidades y rankings. Vídeo nuevo cada día.\n"
            "#corrupción #España #truecrime #casojudicial")
    import requests
    ok = True
    for method, payload in [("setChatTitle", {"title": title}),
                            ("setChatDescription", {"description": desc})]:
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/{method}",
                              json={"chat_id": chan, **payload}, timeout=15)
            if r.status_code == 200:
                print(f"setup-seo: ✅ {method}")
            else:
                ok = False
                print(f"setup-seo: ❌ {method} {r.status_code} {r.text[:150]}")
                if "rights" in r.text.lower() or "administrator" in r.text.lower():
                    print("  → el bot necesita permiso 'Change channel info' (o ponlo a mano).")
        except Exception as e:
            ok = False; print(f"setup-seo: error {method} {type(e).__name__}")
    return ok


def seed_channel(limit: int = 10, channel_key: str = "waitwhy") -> int:
    """Siembra el canal con los últimos vídeos (evita canal vacío = no convierte).
    Lee docs/dashboard/data.json (all_videos por canal). Devuelve nº posts enviados."""
    import json
    import time
    from .config import ROOT
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chan = os.environ.get("TELEGRAM_BROADCAST_CHANNEL", "").strip()
    if not (token and chan):
        print("seed: falta TELEGRAM_BOT_TOKEN/CHANNEL"); return 0
    p = ROOT / "docs" / "dashboard" / "data.json"
    if not p.exists():
        print("seed: no hay data.json"); return 0
    data = json.loads(p.read_text(encoding="utf-8"))
    ch = next((c for c in data.get("channels", []) if c.get("key") == channel_key), None)
    vids = (ch or {}).get("all_videos", [])[:limit]
    if not vids:
        print(f"seed: sin vídeos para {channel_key}"); return 0
    import requests
    tags = _PREFIX_TAGS.get("", "#España")
    sent = 0
    # Orden cronológico ascendente para que el canal quede con el más nuevo abajo.
    for v in reversed(vids):
        url = v.get("url") or (f"https://youtu.be/{v['video_id']}" if v.get("video_id") else "")
        if not url:
            continue
        text = f"🎬 {(v.get('title') or '').strip()[:200]}\n\n{url}\n\n{tags}"
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              json={"chat_id": chan, "text": text, "parse_mode": "HTML"},
                              timeout=15)
            if r.status_code == 200:
                sent += 1
            else:
                print(f"seed: fail {r.status_code} {r.text[:120]}")
                if r.status_code == 429:
                    time.sleep(3)
        except Exception as e:
            print(f"seed: error {type(e).__name__}")
        time.sleep(1.3)  # rate limit Telegram (1 msg/s por chat)
    print(f"seed: {sent} vídeos enviados al canal")
    return sent


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
