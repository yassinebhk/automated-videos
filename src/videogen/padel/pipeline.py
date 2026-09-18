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


def _pick_tactic(keys: list[str]) -> str:
    """Rota: la táctica usada hace más tiempo (o nunca)."""
    used = _load_ledger()
    never = [k for k in keys if k not in used]
    if never:
        return random.choice(never)
    return min(keys, key=lambda k: used.get(k, ""))


def _notify(text: str, urgent: bool = False) -> None:
    from ..notify_batch import add
    add(text, urgent=urgent)


def run_once() -> dict[str, Any]:
    """Genera + sube 1 táctica animada de pádel."""
    from . import manim_scene, render
    keys = list(manim_scene.TACTICS.keys())
    tactic = _pick_tactic(keys)
    info = manim_scene.TACTICS[tactic]
    print(f"  padel: táctica={tactic} · escena={info['scene']}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"padel_{tactic}_{ts}"
    work = PADEL_ROOT / slug
    final = render.render_tactic(tactic, work)
    if not final or not Path(final).exists():
        _notify(f"❌ Padel falló render · {tactic}", urgent=True)
        return {"status": "gen_fail", "tactic": tactic}

    title = f"{info['title']} — Padel Tactics #padel #shorts"[:100]
    description = (
        f"{info['title']}: a clear, step-by-step padel tactic — animated so it actually "
        f"makes sense.\n\nFollow for more padel tactics every week.\n\n"
        f"#padel #padeltips #padeltactics #padeltennis #shorts"
    )
    tags = ["padel", "padel tips", "padel tactics", "padel tennis",
            "padel strategy", "how to play padel", "shorts"]

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

    _mark_used(tactic)
    _notify(f"✅ <b>{DISPLAY_NAME}</b> · YT: {url or yt_status}\n<i>{info['title']} ({info['es']})</i>")

    # Crosspost RRSS (no requiere URL YT)
    try:
        from .. import crosspost_full
        cross = crosspost_full.crosspost_short_from_mp4(
            Path(final), title, url,
            teaser=f"🎾 Padel tactic: {info['title']}",
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

    return {"status": "ok", "slug": slug, "url": url, "tactic": tactic, "yt_status": yt_status}
