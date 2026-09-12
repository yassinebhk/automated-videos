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


def send_video_for_tiktok(mp4_path: str | Path, channel_display: str,
                              title: str, url_yt: str = "") -> bool:
    """Envía el MP4 vertical del Short al chat Telegram para que el user
    lo descargue y lo suba manualmente a TikTok.

    Telegram sendVideo acepta hasta 50MB por bot API. Shorts <60s con
    bitrate razonable = 5-15MB → siempre cabe. Si el archivo excede
    ese límite, se hace skip silencioso (no rompe pipeline).
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
        caption = (
            f"📱 <b>TikTok · {channel_display}</b>\n"
            f"<i>{title[:180]}</i>\n"
            f"↓ Descarga este MP4 y súbelo a la app TikTok manualmente."
        )
        if url_yt:
            caption += f"\nYT: {url_yt}"
        with open(p, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{tok}/sendVideo",
                data={"chat_id": chat, "caption": caption[:1024],
                        "parse_mode": "HTML", "supports_streaming": True},
                files={"video": (p.name, f, "video/mp4")},
                timeout=180,
            )
        return r.status_code == 200
    except Exception as e:
        print(f"  tg sendVideo fail: {type(e).__name__}: {e}")
        return False
