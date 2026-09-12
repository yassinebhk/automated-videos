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
    """Genera 1 video ambient (MenteEnCalma) + sube a YT + notifica Telegram."""
    print("=== MenteEnCalma · start ===")
    meta = generator.generate_ambient_video()
    if not meta:
        _notify("❌ MenteEnCalma: generación falló")
        return None

    # Disclaimer legal en descripción — NO claims médicos falsos (política veracidad)
    disclaimer = (
        "\n\n⚠️ Este audio es solo para acompañar tu momento de relax/estudio/sueño. "
        "NO sustituye a tratamiento médico ni psicológico. Si tienes problemas de "
        "ansiedad/insomnio persistentes, consulta con un profesional sanitario. "
        "Los efectos de ondas binaurales/música varían por persona — usa con "
        "auriculares (binaurales) y a volumen moderado."
    )
    meta["description"] = meta.get("description", "") + disclaimer

    print(f"  MenteEnCalma: video listo {meta['duration_seconds']}s → uploading...")
    up = uploader.upload_ambient(meta)
    if not up:
        _notify(f"⚠️ MenteEnCalma: '{meta['title'][:60]}' generado pero upload falló")
        return {"generated": meta, "uploaded": None}

    _notify(
        f"🌙 <b>MenteEnCalma upload OK</b>\n"
        f"<i>{meta['title'][:80]}</i>\n"
        f"⏱ {meta['duration_seconds']//60} min · tema: {meta['topic_key']}\n"
        f"{up['url']}"
    )
    return {"generated": meta, "uploaded": up}


def _notify(text: str, urgent: bool = False) -> None:
    """Encola notificación (batched al final del proceso).
    urgent=True → envía inmediatamente (fallos críticos)."""
    from ..notify_batch import add
    add(text, urgent=urgent)
