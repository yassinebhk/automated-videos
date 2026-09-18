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
    # ⏸ PAUSADO 18/09 (consolidación media — 5 subs, mediana 2 views tras 30 vídeos).
    # Reactivar = borrar estas 2 líneas + `gh workflow enable ambient-daily/ambient-short-daily`.
    print("  ambient: ⏸ PAUSADO (consolidación media) — no genera"); return {"status": "paused", "channel": "ambient"}
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


def run_short() -> dict[str, Any] | None:
    """Genera + sube 1 Short ambient al canal MenteEnCalma (cebo → long-form)."""
    # ⏸ PAUSADO 18/09 (consolidación media). Reactivar = borrar estas 2 líneas.
    print("  ambient-short: ⏸ PAUSADO (consolidación media) — no genera"); return {"status": "paused", "channel": "ambient"}
    from . import shorts as ambient_shorts
    from ..upload_youtube import upload_video
    from pathlib import Path

    print("=== MenteEnCalma Short · start ===")
    meta = ambient_shorts.generate_ambient_short()
    if not meta:
        _notify("❌ MenteEnCalma Short: generación falló", urgent=True)
        return None

    # Sube al canal YT_AMBIENT
    prev_prefix = os.environ.get("YT_CHANNEL_PREFIX", "")
    os.environ["YT_CHANNEL_PREFIX"] = "YT_AMBIENT"
    try:
        vid = upload_video(
            Path(meta["video_path"]),
            title=meta["title"][:100],
            description=meta["description"][:4900],
            tags=meta.get("tags", []),
            category_id="10",  # Music
            is_short=True,
            privacy="public",
        )
        url = f"https://youtube.com/shorts/{vid}"
        _notify(f"🌙 <b>MenteEnCalma Short</b>\n<i>{meta['title'][:80]}</i>\n{url}")
        # MP4 al Telegram para TikTok
        try:
            from ..notify_batch import send_video_for_tiktok
            send_video_for_tiktok(meta["video_path"], "MenteEnCalma",
                                     meta["title"], url)
        except Exception:
            pass
        # Crosspost RRSS unificado (BS + MA + TH + IG @waitwhy_)
        try:
            from .. import crosspost_full
            teaser = "🌙 Sonido ambient para relajarte — audio real royalty-free"
            cross = crosspost_full.crosspost_short_from_mp4(
                Path(meta["video_path"]), meta["title"], url,
                teaser=teaser, channel_label="menteencalma",
                slug=meta.get("slug"),  # sin esto → mp4_path.stem = 'video_es_vertical' (colisión)
            )
            _notify(f"🌙 <b>MenteEnCalma · RRSS</b> {crosspost_full.summary_line(cross)}")
        except Exception as e:
            print(f"  menteencalma crosspost fail: {e}")
        return {"generated": meta, "url": url}
    except Exception as e:
        _notify(f"⚠️ MenteEnCalma Short upload fail: {type(e).__name__}: {str(e)[:150]}",
                 urgent=True)
        return {"generated": meta, "error": str(e)}
    finally:
        if prev_prefix:
            os.environ["YT_CHANNEL_PREFIX"] = prev_prefix
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)
