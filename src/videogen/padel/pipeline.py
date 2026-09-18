"""Pipeline Padel Pro (EN) — táctica ANIMADA con Manim (motor ganador 18/09).

Cada run: rota 1 de las 8 tácticas (globo, pared, bandeja, remate, dejada, saque,
posición, defensa) → anima con Manim + voz Edge didáctica + música → sube a
YT_PADEL (Short) + crosspost IG/TikTok/RRSS. 100% gratis, sin metraje real ni IA.

Ver memoria [[padel-formato-ganador-manim]]. NO volver a diagramas ni Pexels.
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import ROOT


LEDGER_PATH = ROOT / "output" / "padel_ledger.json"
YT_PREFIX = "YT_PADEL"
DISPLAY_NAME = "Padel Pro"
PADEL_ROOT = ROOT / "output" / "padel_uploaded"
# Cap 5 hashtags (anti-baneo IG) + caption limpio por canal. Ver [[ig-antiban-multicanal]].
IG_HASHTAGS = ["padel", "padeltips", "padeltactics", "padeltennis", "shorts"]


def _load_ledger() -> dict[str, str]:
    if not LEDGER_PATH.exists():
        return {}
    try:
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(key: str) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    d = _load_ledger()
    d[key] = datetime.now(timezone.utc).isoformat()
    LEDGER_PATH.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def _pick_key(keys: list[str]) -> str:
    """Rota: el topic usado hace más tiempo (o nunca)."""
    used = _load_ledger()
    never = [k for k in keys if k not in used]
    if never:
        return random.choice(never)
    return min(keys, key=lambda k: used.get(k, ""))


def _flat(s: str) -> str:
    return " ".join((s or "").split())


_FMT_LABEL = {"tactic": "Padel Tactics", "fact": "Padel Facts",
              "compare": "Padel Gear", "checklist": "Padel Tips"}


def _notify(text: str, urgent: bool = False) -> None:
    from ..notify_batch import add
    add(text, urgent=urgent)


def run_once() -> dict[str, Any]:
    """Genera + sube 1 vídeo de pádel (rota entre tácticas, curiosidades,
    comparativas de material y checklists de recomendaciones)."""
    from . import render, topics
    pool = topics.all_topics()
    by_key = {t["key"]: t for t in pool}
    key = _pick_key(list(by_key.keys()))
    topic = by_key[key]
    fmt = topic.get("format", "tactic")
    print(f"  padel: topic={key} · format={fmt} ({len(pool)} en pool)")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"padel_{key}_{ts}"
    work = PADEL_ROOT / slug
    final = render.render_topic(topic, work)
    if not final or not Path(final).exists():
        _notify(f"❌ Padel falló render · {key}", urgent=True)
        return {"status": "gen_fail", "topic": key}

    headline = _flat(topic.get("title", "Padel"))
    label = _FMT_LABEL.get(fmt, "Padel")
    title = f"{headline} — {label} #padel #shorts"[:100]
    description = (
        f"{headline} · {label}, animated so it actually makes sense.\n\n"
        f"Follow for more padel every week.\n\n"
        f"#padel #padeltips #padeltennis #padelpro #shorts"
    )
    tags = ["padel", "padel tips", "padel tactics", "padel tennis",
            "padel gear", "how to play padel", "shorts"]

    # YT upload (YT_PADEL) — si no hay creds, sigue a IG/TT igual
    from ..upload_youtube import upload_video
    prev = os.environ.get("YT_CHANNEL_PREFIX", "")
    os.environ["YT_CHANNEL_PREFIX"] = YT_PREFIX
    has_creds = bool(os.environ.get(YT_PREFIX + "_REFRESH_TOKEN"))
    print(f"  padel: prefix={YT_PREFIX} · has_refresh={has_creds}")
    url, yt_status = "", "skip_no_creds"
    if has_creds:
        try:
            vid = upload_video(
                Path(final), title=title, description=description[:4900], tags=tags,
                category_id="17", is_short=True, privacy="public",  # 17 = Sports
            )
            url = f"https://youtube.com/shorts/{vid}"
            yt_status = "ok"
        except Exception as e:
            print(f"  padel upload fail: {type(e).__name__}: {e}")
            yt_status = f"fail: {type(e).__name__}"
    if prev:
        os.environ["YT_CHANNEL_PREFIX"] = prev
    else:
        os.environ.pop("YT_CHANNEL_PREFIX", None)

    _mark_used(key)
    _notify(f"✅ <b>{DISPLAY_NAME}</b> · YT: {url or yt_status}\n<i>{label}: {headline}</i>")

    # Crosspost RRSS (no requiere URL YT)
    try:
        from .. import crosspost_full
        cross = crosspost_full.crosspost_short_from_mp4(
            Path(final), title, url,
            teaser=f"🎾 {label}: {headline}",
            channel_label="padel", slug=slug,
        )
        _notify(f"🎾 <b>Padel · RRSS</b> {crosspost_full.summary_line(cross)}")
    except Exception as e:
        print(f"  padel crosspost fail: {e}")
    # TikTok (Telegram para publicación manual / draft)
    try:
        from ..notify_batch import send_video_for_tiktok
        send_video_for_tiktok(str(final), DISPLAY_NAME, title, url)
    except Exception as e:
        print(f"  padel: TT tg fail — {e}")
    # Instagram Reel (token por canal IG_PADEL_TOKEN vía prefix)
    try:
        from .. import social_reels
        social_reels.post_ig_reel(str(final), title, url, slug,
                                  hashtags=IG_HASHTAGS, prefix=YT_PREFIX)
    except Exception as e:
        print(f"  padel: ig fail — {e}")

    return {"status": "ok", "slug": slug, "url": url, "topic": key,
            "format": fmt, "yt_status": yt_status}
