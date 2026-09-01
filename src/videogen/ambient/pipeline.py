"""Pipeline end-to-end: genera + sube + notifica.

Ejecutable vía `videogen ambient-once` (CLI).
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from . import generator, uploader


def run_once() -> dict[str, Any] | None:
    """Genera 1 video ambient + sube a YT + notifica Telegram."""
    print("=== AMBIENT · start ===")
    meta = generator.generate_ambient_video()
    if not meta:
        _notify("❌ Ambient: generación falló")
        return None

    print(f"  ambient: video listo {meta['duration_seconds']}s → uploading...")
    up = uploader.upload_ambient(meta)
    if not up:
        _notify(f"⚠️ Ambient: '{meta['title'][:60]}' generado pero upload falló")
        return {"generated": meta, "uploaded": None}

    _notify(
        f"🌙 <b>Ambient upload OK</b>\n"
        f"<i>{meta['title'][:80]}</i>\n"
        f"⏱ {meta['duration_seconds']//60} min · tema: {meta['topic_key']}\n"
        f"{up['url']}"
    )
    return {"generated": meta, "uploaded": up}


def _notify(text: str) -> None:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data=json.dumps({"chat_id": int(chat), "text": text,
                              "parse_mode": "HTML",
                              "disable_web_page_preview": False}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=30).read()
    except Exception as e:
        print(f"  ambient: tg notify fail — {e}")
