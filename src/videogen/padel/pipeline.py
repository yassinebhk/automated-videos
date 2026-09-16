"""Pipeline Padel Pro (EN) — consejo de pádel sobre METRAJE REAL.

Reusa el pipeline narrado probado (service.generate/publish): B-roll real de Pexels
por visual_keywords de pádel + subtítulos sincronizados + voz Edge en-US + compose.
ai_hero=False (todo metraje real, sin imagen IA). Upload YT_PADEL + IG + TikTok.
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Any

from ..config import ROOT
from . import topic_pool


LEDGER_PATH = ROOT / "output" / "padel_ledger.json"
COOLDOWN_DAYS = 90
YT_PREFIX = "YT_PADEL"
DISPLAY_NAME = "Padel Pro"
EDGE_VOICE_EN = "en-US-GuyNeural"
IG_HASHTAGS = ["padel", "padeltips", "padeltactics", "sport", "padellife", "tennis"]


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


def _recently_used(key: str) -> bool:
    e = _load_ledger().get(key)
    if not e:
        return False
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(e)) < timedelta(days=COOLDOWN_DAYS)
    except Exception:
        return False


def _pick_topic() -> dict:
    pool = topic_pool.all_topics()
    fresh = [t for t in pool if not _recently_used(t["key"])]
    return random.choice(fresh or pool)


def _build_prompt(t: dict) -> str:
    return (
        f"[Padel Pro · English · ONE coaching tip over REAL padel footage] "
        f"Teach this padel tip: {t['titulo']}. "
        f"Mandatory hook (0-3s): {t['hook']}. "
        f"What to teach: {t['subject']} "
        f"Explain clearly in ~45s for a beginner-to-intermediate player, 3-4 short beats. "
        f"CRITICAL: every visual_keywords entry must be REAL PADEL GAMEPLAY in English "
        f"(padel match, padel rally, padel smash, padel net volley, padel players court, "
        f"padel serve, padel doubles) — always the word 'padel', never 'tennis'. "
        f"Title: '{t['titulo']} — Padel tip'. Closing CTA: 'Follow for more padel tips.'"
    )


def _set_env() -> None:
    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = "padel_system.md"
    os.environ["YT_CHANNEL_PREFIX"] = YT_PREFIX
    os.environ.setdefault("EDGE_VOICE_EN_PADEL", EDGE_VOICE_EN)


def _clear_env() -> None:
    os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
    os.environ.pop("YT_CHANNEL_PREFIX", None)


def _notify(text: str, urgent: bool = False) -> None:
    from ..notify_batch import add
    add(text, urgent=urgent)


def _mp4_for(slug: str):
    from ..config import UPLOADED_DIR, PENDING_DIR
    for b in (UPLOADED_DIR, PENDING_DIR):
        p = b / slug / "video_en_vertical.mp4"
        if p.exists():
            return p
    return None


def run_once() -> dict[str, Any]:
    from .. import service
    topic = _pick_topic()
    prompt = _build_prompt(topic)
    print(f"  padel: topic={topic['key']}")
    _set_env()
    print(f"  padel: prefix={YT_PREFIX} · has_refresh={bool(os.environ.get(YT_PREFIX + '_REFRESH_TOKEN'))}")
    try:
        slug = service.generate(prompt, ("en",), lambda m: print(f"  {m}"), ai_hero=False)
        print(f"  padel: vídeo EN (metraje real) generado, subiendo a {DISPLAY_NAME}…")
        links = service.publish(slug, ("en",), privacy="public",
                                progress=lambda m: print(f"  {m}"), notify=False)
        _mark_used(topic["key"])
        url = links.get("en", "?")
        _notify(f"✅ <b>{DISPLAY_NAME}</b> · {url}\n<i>{topic['titulo']}</i>")
        mp4 = _mp4_for(slug)
        if mp4:
            try:
                from ..notify_batch import send_video_for_tiktok
                send_video_for_tiktok(mp4, DISPLAY_NAME, topic["titulo"], url)
            except Exception as e:
                print(f"  padel: TT tg fail — {e}")
            try:
                from .. import social_reels
                social_reels.post_ig_reel(mp4, topic["titulo"], url, slug,
                                          hashtags=IG_HASHTAGS, teaser=topic.get("hook", ""),
                                          prefix=YT_PREFIX)
            except Exception as e:
                print(f"  padel: ig fail — {e}")
        return {"status": "ok", "slug": slug, "url": url, "topic_key": topic["key"]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _notify(f"❌ {DISPLAY_NAME} falló: {type(e).__name__}: {str(e)[:200]}", urgent=True)
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        _clear_env()
