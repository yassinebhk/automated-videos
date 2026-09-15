"""Pipeline AI Tools Weekly EN — Short 1×/día + long-form semanal (~8 min).

Autocontenido (como ambient): reusa la infraestructura pesada de WaitWhy vía
service.generate/publish/generate_long/publish_long, pero orquesta en inglés y
NO cross-postea a las RRSS ES (marca distinta). Solo YT + MP4→Telegram para TikTok.

Env overrides seteados en runtime:
- SCRIPT_SYSTEM_PROMPT_FILE=ai_tools_en_system.md
- YT_CHANNEL_PREFIX=YT_AITOOLS  → creds YT_AITOOLS_REFRESH_TOKEN/CLIENT_ID/SECRET
- EDGE_VOICE_EN_AITOOLS=en-US-GuyNeural

Si faltan los secrets YT_AITOOLS_*, la subida falla y se notifica (no rompe
otros canales — proceso aislado).
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Any

from ..config import ROOT
from . import topic_pool, topic_refresher


LEDGER_PATH = ROOT / "output" / "aitools_ledger.json"
COOLDOWN_DAYS = 90

YT_PREFIX = "YT_AITOOLS"
DISPLAY_NAME = "AI Tools Weekly"
EDGE_VOICE_EN = "en-US-GuyNeural"  # voz tech con autoridad (research)


# ─────────────────────────────── ledger ───────────────────────────────
def _load_ledger() -> dict[str, str]:
    if not LEDGER_PATH.exists():
        return {}
    try:
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(key: str) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = _load_ledger()
    data[key] = datetime.now(timezone.utc).isoformat()
    LEDGER_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                           encoding="utf-8")


def _recently_used(key: str) -> bool:
    entry = _load_ledger().get(key)
    if not entry:
        return False
    try:
        ts = datetime.fromisoformat(entry)
    except Exception:
        return False
    return (datetime.now(timezone.utc) - ts) < timedelta(days=COOLDOWN_DAYS)


def _next_episode_num() -> int:
    return len(_load_ledger()) + 1


# ─────────────────────────────── topics ───────────────────────────────
def _pick_topic(kind: str = "short") -> dict | None:
    """Elige topic no usado en cooldown. Rota por categoria para variedad
    (anti-repetition). Mergea pool estático + dinámico (refresh quincenal)."""
    static_pool = topic_pool.all_topics()
    try:
        all_t = topic_refresher.get_all_topics_merged(static_pool, kind=kind)
    except Exception as e:
        print(f"  aitools-{kind}: dynamic topics fail ({e}), usando estáticos")
        all_t = static_pool

    def _key(t: dict) -> str:
        return t["key"] + ("_LONG" if kind == "long" else "")

    fresh = [t for t in all_t if not _recently_used(_key(t))]
    if not fresh:
        fresh = all_t
    # Balance por categoria (variedad de tipos de herramienta)
    by_cat: dict[str, list[dict]] = {}
    for t in fresh:
        by_cat.setdefault(t.get("categoria", "misc"), []).append(t)
    cat_choice = random.choice(list(by_cat.keys()))
    return random.choice(by_cat[cat_choice])


def _build_short_prompt(t: dict) -> str:
    ep = _next_episode_num()
    tools = t.get("tools") or []
    tools_line = ""
    if tools:
        tools_line = (
            f"Use EXACTLY these 5 real tools (do not invent or swap): "
            f"{', '.join(tools)}. "
        )
    return (
        f"[Episode #{ep} · Channel AI Tools Weekly · audience={t.get('audiencia','')} · "
        f"category={t.get('categoria','')}] "
        f"Topic: {t['titulo']}. "
        f"Mandatory hook (0-3s): {t.get('hook','')}. "
        f"{tools_line}"
        f"For EACH of the 5 tools give: name + one concrete real use + why it stands out "
        f"(one line each). Only real, verifiable facts — if unsure about a price/feature, "
        f"say 'free tier available' instead of a number. Anchor phrase to say: "
        f"{t.get('cifra_ancla','')}. "
        f"The title MUST follow the pattern 'Top 5 AI tools for [X] · #{ep}'. "
        f"thumbnail_text MUST show 'TOP 5' on line 1 and the category/use on line 2. "
        f"MANDATORY closing CTA: 'Follow for the best AI tools every day.'"
    )


def _build_long_prompt(t: dict) -> str:
    tools = t.get("tools") or []
    tools_line = f"Cover at least these real tools: {', '.join(tools)}. " if tools else ""
    return (
        f"[LONG-FORM · Channel AI Tools Weekly · audience={t.get('audiencia','')} · "
        f"category={t.get('categoria','')}] "
        f"Topic: {t['titulo']}. Expand into a ~8 minute deep-dive with 3-5 chapters: "
        f"the problem + the best AI tools for it + a real step-by-step workflow + "
        f"pitfalls to avoid + a practical recommendation. "
        f"{tools_line}"
        f"Central hook: {t.get('hook','')}. Key takeaway: {t.get('cifra_ancla','')}. "
        f"Only real, verifiable tools and facts — no invented pricing/features. "
        f"Title format: '[Topic] — The Complete Guide (2026)'. "
        f"Mandatory closing: 'Subscribe for a new AI deep-dive every week.'"
    )


# ─────────────────────────────── env / voz ────────────────────────────
def _set_channel_env() -> None:
    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = "ai_tools_en_system.md"
    os.environ["YT_CHANNEL_PREFIX"] = YT_PREFIX
    # Voz EN tech (default global ya es GuyNeural, pero lo fijamos explícito
    # por canal para robustez si el default cambia).
    os.environ.setdefault("EDGE_VOICE_EN_AITOOLS", EDGE_VOICE_EN)


def _clear_channel_env() -> None:
    os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
    os.environ.pop("YT_CHANNEL_PREFIX", None)


def _notify(text: str, urgent: bool = False) -> None:
    from ..notify_batch import add
    add(text, urgent=urgent)


def _load_video_title(slug: str) -> str | None:
    from ..config import PENDING_DIR, UPLOADED_DIR
    for base in (UPLOADED_DIR, PENDING_DIR):
        p = base / slug / "scripts.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return (data.get("en") or {}).get("title")
            except Exception:
                pass
    return None


def _send_tt_video(slug: str, title: str, url: str) -> None:
    """MP4 vertical EN → Telegram para subida manual a TikTok (@interest_stuff)."""
    try:
        from ..config import UPLOADED_DIR, PENDING_DIR
        from ..notify_batch import send_video_for_tiktok
        for base in (UPLOADED_DIR, PENDING_DIR):
            p = base / slug / "video_en_vertical.mp4"
            if p.exists():
                send_video_for_tiktok(p, DISPLAY_NAME, title, url)
                return
    except Exception as e:
        print(f"  aitools: TT tg video fail — {e}")


# ─────────────────────────────── runners ──────────────────────────────
def run_once() -> dict[str, Any]:
    """Genera + sube 1 Short EN al canal AI Tools Weekly."""
    from .. import service

    topic = _pick_topic(kind="short")
    if not topic:
        return {"status": "no_topic"}

    topic_prompt = _build_short_prompt(topic)
    print(f"  aitools: topic={topic['key']} categoria={topic.get('categoria','')}")
    _set_channel_env()
    print(f"  aitools: prefix={YT_PREFIX} · "
          f"has_refresh={bool(os.environ.get(YT_PREFIX + '_REFRESH_TOKEN'))} · "
          f"has_client_id={bool(os.environ.get(YT_PREFIX + '_CLIENT_ID'))} · "
          f"has_client_secret={bool(os.environ.get(YT_PREFIX + '_CLIENT_SECRET'))}")

    try:
        slug = service.generate(topic_prompt, ("en",),
                                 lambda m: print(f"  {m}"), ai_hero=True)
        print(f"  aitools: video EN generado, subiendo a {DISPLAY_NAME}…")
        links = service.publish(slug, ("en",), privacy="public",
                                 progress=lambda m: print(f"  {m}"), notify=False)
        _mark_used(topic["key"])
        url = links.get("en", "?")
        _notify(f"✅ <b>{DISPLAY_NAME}</b> · {url}\n"
                f"<i>{topic.get('titulo','')[:60]}</i>")
        _send_tt_video(slug, _load_video_title(slug) or topic.get("titulo", ""), url)
        # Crosspost RRSS unificado (BS + MA + TH + IG @waitwhy_)
        try:
            from ..config import UPLOADED_DIR, PENDING_DIR
            from .. import crosspost_full
            dst_dir = None
            for base in (UPLOADED_DIR, PENDING_DIR):
                p = base / slug
                if p.exists():
                    dst_dir = p
                    break
            if dst_dir:
                title = _load_video_title(slug) or topic.get("titulo", "")
                teaser = f"🤖 AI tool · {topic.get('categoria','')}"
                cross = crosspost_full.crosspost_short(
                    dst_dir, title, url, teaser=teaser,
                    channel_label="aitools",
                )
                _notify(f"🤖 <b>AI Tools · RRSS</b> {crosspost_full.summary_line(cross)}")
        except Exception as e:
            print(f"  aitools crosspost fail: {e}")
        return {"status": "ok", "slug": slug, "url": url, "topic_key": topic["key"]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _notify(f"❌ {DISPLAY_NAME} short falló: {type(e).__name__}: {str(e)[:200]}",
                urgent=True)
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        _clear_channel_env()


def run_longform(target_minutes: int = 8) -> dict[str, Any]:
    """Genera + sube 1 long-form EN (~8 min, 16:9) al canal AI Tools Weekly."""
    from .. import service

    topic = _pick_topic(kind="long")
    if not topic:
        return {"status": "no_topic"}

    topic_prompt = _build_long_prompt(topic)
    print(f"  aitools-long: topic={topic['key']}")
    _set_channel_env()
    print(f"  aitools-long: prefix={YT_PREFIX} · "
          f"has_refresh={bool(os.environ.get(YT_PREFIX + '_REFRESH_TOKEN'))}")

    try:
        slug = service.generate_long(topic_prompt, target_minutes=target_minutes,
                                     langs=("en",), progress=lambda m: print(f"  {m}"))
        print(f"  aitools-long: subiendo a {DISPLAY_NAME}…")
        links = service.publish_long(slug, ("en",), privacy="public",
                                     progress=lambda m: print(f"  {m}"), notify=False)
        _mark_used(topic["key"] + "_LONG")
        url = links.get("en", "?")
        _notify(f"✅ <b>{DISPLAY_NAME} · long-form</b>\n"
                f"slug: <code>{slug}</code>\n{url}")
        return {"status": "ok", "slug": slug, "url": url,
                "topic_key": topic["key"], "kind": "long"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _notify(f"❌ {DISPLAY_NAME} long-form falló: {type(e).__name__}: {str(e)[:200]}")
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        _clear_channel_env()
