"""Notificaciones Telegram batched — 1 mensaje/proceso en vez de N.

Antes: cada canal enviaba 1 mensaje al publicar → 8 canales/día = 8+
notificaciones Telegram + social_boost + fallos = 12-15 msg/día = ruido.

Ahora: se acumulan durante el proceso y se envía UN mensaje al final
(atexit). Los mensajes marcados urgent=True saltan el buffer y se
mandan al momento (para fallos críticos que necesitas ver ya).

También ofrece `send_video_for_tiktok()` para adjuntar el MP4 vertical
del Short al chat Telegram, con caption clara — el user lo descarga y
lo sube manual a TikTok (workaround al Sandbox restringido).
"""
from __future__ import annotations

import atexit
import json
import os
import urllib.request
from pathlib import Path

_BUFFER: list[str] = []
_FLUSHED = False


def add(text: str, urgent: bool = False) -> None:
    """Encola un mensaje. urgent=True → envía inmediatamente."""
    if urgent:
        _send_message_now(text)
        return
    _BUFFER.append(text)


def flush() -> None:
    """Envía el buffer entero como un solo mensaje."""
    global _FLUSHED
    if _FLUSHED or not _BUFFER:
        return
    _FLUSHED = True
    combined = "\n\n────────\n\n".join(_BUFFER)
    # Telegram sendMessage cap ~4096 chars — truncamos con margen
    if len(combined) > 3900:
        combined = combined[:3900] + "\n\n<i>… (mensaje truncado)</i>"
    _send_message_now(combined)
    _BUFFER.clear()


atexit.register(flush)


def _send_message_now(text: str) -> None:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data=json.dumps({"chat_id": int(chat), "text": text,
                                "parse_mode": "HTML",
                                "disable_web_page_preview": True}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass


# Hashtags TT curados por nicho — mezcla generales (parati/fyp) + específicos.
# El user los copia junto al título al subir a TikTok. TT sigue distribuyendo
# por hashtags parcialmente en 2026 aunque menos que antes.
TT_HASHTAGS: dict[str, str] = {
    "WaitWhy":         "#parati #fyp #foryou #truecrime #españa #estafa #curiosidades #viral #misterio",
    "TaxHack ES":      "#parati #fyp #españa #dinero #impuestos #autonomos #ahorrar #hacienda #finanzas",
    "TusDerechos ES":  "#parati #fyp #españa #derechoslaborales #trabajo #trabajador #consejos #legal",
    "AyudaGob":        "#parati #fyp #españa #ayudas #subvenciones #gobierno #familia #dinero",
    "Motor60s":        "#parati #fyp #coches #cochesegundamano #motor #españa #comprarcoche #trucos",
    "TiempoAtrás ES":  "#parati #fyp #historia #españa #curiosidades #sabiasque #cultura #aprende",
    "TopRanking ES":   "#parati #fyp #ranking #top10 #dinero #famosos #curiosidades #comparación",
    "MenteEnCalma":    "#parati #fyp #relax #dormir #meditar #calma #ansiedad #descanso",
    "IA Autónomos ES": "#parati #fyp #ia #chatgpt #autonomos #productividad #tecnologia #españa #trucos",
}


def _tt_caption(channel_display: str, title: str, url_yt: str = "") -> str:
    """Compone caption completo para el sendVideo — copy-paste friendly.
    Incluye título sugerido + hashtags TT + tip de retention."""
    # `channel_display` puede venir como "TaxHack ES · motivo…" — extraemos
    # el nombre puro para buscar hashtags
    canal_pure = channel_display.split("·")[0].strip()
    hashtags = TT_HASHTAGS.get(canal_pure, "#parati #fyp #foryou #españa #curiosidades")
    parts = [
        f"📱 <b>TikTok · {channel_display}</b>",
        "",
        "📝 <b>TÍTULO</b> (copia/pega):",
        title[:150],
        "",
        "#️⃣ <b>HASHTAGS</b>:",
        hashtags,
        "",
        "⏱ Primeros 3s = 40% retention TT. Si no engancha, avisa y regenero.",
    ]
    if url_yt:
        parts.append(f"🔗 YT: {url_yt}")
    caption = "\n".join(parts)
    return caption[:1024]  # límite Telegram sendVideo caption


def send_video_for_tiktok(mp4_path: str | Path, channel_display: str,
                              title: str, url_yt: str = "") -> bool:
    """Envía el MP4 vertical del Short al chat Telegram para que el user
    lo descargue y lo suba manualmente a TikTok. El caption ya incluye
    título sugerido + hashtags TT + tip retention → subida en 30s.

    Telegram sendVideo acepta hasta 50MB por bot API. Shorts <60s con
    bitrate razonable = 5-15MB → suele caber. Si excede, skip con aviso.
    """
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return False
    p = Path(mp4_path)
    if not p.exists():
        return False
    size_mb = p.stat().st_size / 1_000_000
    if size_mb > 48:
        add(f"⚠️ TT · {channel_display}: MP4 muy grande ({size_mb:.1f}MB) — "
             f"descarga desde YT: {url_yt}")
        return False
    try:
        import requests
        caption = _tt_caption(channel_display, title, url_yt)
        with open(p, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{tok}/sendVideo",
                data={"chat_id": chat, "caption": caption,
                        "parse_mode": "HTML", "supports_streaming": True},
                files={"video": (p.name, f, "video/mp4")},
                timeout=180,
            )
        return r.status_code == 200
    except Exception as e:
        print(f"  tg sendVideo fail: {type(e).__name__}: {e}")
        return False
