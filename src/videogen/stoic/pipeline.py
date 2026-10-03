"""Pipeline Stoic Mind (EN) — estoicismo aplicado a estrés moderno.

Nueva apuesta 02/10 (nicho trending, coste cero, sin riesgo YMYL). Reusa la
infraestructura pesada (service.generate/publish: voz Edge + B-roll Pexels +
imágenes IA + música Freesound + captions + upload), como ai_tools/ambient.

Env runtime:
- SCRIPT_SYSTEM_PROMPT_FILE=stoic_en_system.md
- YT_CHANNEL_PREFIX=YT_STOIC  → creds YT_STOIC_REFRESH_TOKEN/CLIENT_ID/SECRET
- EDGE_VOICE_EN_STOIC=en-US-GuyNeural (voz grave, lenta)

PRE-CABLEADO: mientras no exista el canal YT (YT_STOIC_* secrets), GENERA el vídeo
y OMITE la subida (no contamina WaitWhy, no rompe el run) → se puede revisar calidad.
Entra en producción en cuanto se cree el canal + secrets. Ver [[expansion-canales-09-15]].
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Any

from ..config import ROOT
from . import topics


LEDGER_PATH = ROOT / "output" / "stoic_ledger.json"
COOLDOWN_DAYS = 120
YT_PREFIX = "YT_STOIC"
DISPLAY_NAME = "Stoic Mind"
EDGE_VOICE_EN = "en-US-GuyNeural"
PLATFORM_KEY = "youtube_stoic"


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
    LEDGER_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


SHORTS_PER_DAY = 1  # tope Shorts/día (el catchup dispara 4-5× → esto capa)


def _today_count(longform: bool = False) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    n = 0
    for k, ts in _load_ledger().items():
        if str(k).endswith("_LONG") != longform:
            continue
        if isinstance(ts, str) and ts[:10] == today:
            n += 1
    return n


def _recently_used(key: str) -> bool:
    entry = _load_ledger().get(key)
    if not entry:
        return False
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(entry)) < timedelta(days=COOLDOWN_DAYS)
    except Exception:
        return False


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


# ─────────────────────────────── topics ───────────────────────────────
def _pick_topic() -> dict | None:
    all_t = topics.all_topics()
    fresh = [t for t in all_t if not _recently_used(t["key"])]
    if len(fresh) < 3:
        try:
            topics.refresh_dynamic()
            all_t = topics.all_topics()
            fresh = [t for t in all_t if not _recently_used(t["key"])]
        except Exception as e:
            print(f"  stoic: refresh on-empty fail ({e})")
    if not fresh:
        fresh = all_t
    # Anti-repeat SEMÁNTICO por título contra lo ya publicado (backstop al guardarraíl).
    try:
        from .. import dedup_common
        recents = dedup_common.recent_titles_from_history(PLATFORM_KEY, days=180)
        cand = [t for t in fresh
                if not dedup_common.title_is_repeat(t.get("titulo") or t.get("key", ""), recents)]
        if cand:
            fresh = cand
    except Exception as e:
        print(f"  stoic: dedup título skip ({e})")
    return random.choice(fresh) if fresh else None


def _build_prompt(t: dict) -> str:
    avoid = ""
    try:
        from .. import dedup_common
        block = dedup_common.recent_titles_block(PLATFORM_KEY, days=150, n=25)
        if block:
            avoid = (f" ⛔ DO NOT repeat or resemble these ALREADY-PUBLISHED titles: {block}. "
                     f"Pick a clearly DIFFERENT angle and title.")
    except Exception:
        pass
    return (
        f"[Channel Stoic Mind · faceless EN Shorts · Stoic philosophy for modern stress] "
        f"Modern stressor: {t['stressor']}. "
        f"Stoic lens: {t.get('stoic','the Stoics')} — principle: {t.get('principle','')}. "
        f"Mandatory hook (0-3s), a vivid scene naming the stressor: {t.get('hook','')}. "
        f"Structure: hook → the Stoic reframe (the principle in plain words) → 2-3 concrete "
        f"moves the viewer can use → one sharp memorable closing line (your own words) → "
        f"CTA 'Follow for daily Stoic discipline.'. "
        f"VERACITY: do NOT fabricate or misattribute quotes; teach the principle in your own "
        f"words; no medical/therapy/financial advice. "
        f"Visual keywords should be dark & cinematic: {t.get('visual','marble statue, stormy sky, candle')}. "
        f"Suggested title direction (improve if you can): '{t.get('titulo','')}'."
        + avoid
    )


def _set_env() -> None:
    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = "stoic_en_system.md"
    os.environ["YT_CHANNEL_PREFIX"] = YT_PREFIX
    os.environ.setdefault("EDGE_VOICE_EN_STOIC", EDGE_VOICE_EN)


def _clear_env() -> None:
    os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
    os.environ.pop("YT_CHANNEL_PREFIX", None)


def run_once() -> dict[str, Any]:
    """Genera + (si hay canal) sube 1 Short estoico EN. Sin secrets YT_STOIC_* →
    genera y OMITE subida (pre-cableado, no contamina ni rompe)."""
    from .. import service

    has_creds = bool(os.environ.get(YT_PREFIX + "_REFRESH_TOKEN"))
    allow_test_gen = os.environ.get("STOIC_GENERATE_WITHOUT_CHANNEL", "").lower() in ("1", "true", "yes")
    # Sin canal YT propio Y sin flag de test → NO-OP INSTANTÁNEO: no genera (el vídeo
    # se descartaría → desperdicio de cuota/compute). Se auto-activa en cuanto existan
    # los secrets YT_STOIC_*. Para probar la generación: STOIC_GENERATE_WITHOUT_CHANNEL=1.
    if not has_creds and not allow_test_gen:
        print("  stoic: sin YT_STOIC_* y sin flag de test → no-op (canal pendiente de crear)")
        return {"status": "no_channel"}

    if has_creds and _today_count() >= SHORTS_PER_DAY:
        print(f"  stoic: tope diario de Shorts ({SHORTS_PER_DAY}) alcanzado — skip")
        return {"status": "skip_daily_cap"}

    topic = _pick_topic()
    if not topic:
        return {"status": "no_topic"}

    prompt = _build_prompt(topic)
    print(f"  stoic: topic={topic['key']} · {topic.get('stoic','')} / {topic.get('principle','')}")
    _set_env()
    print(f"  stoic: prefix={YT_PREFIX} · has_refresh={has_creds} · test_gen={allow_test_gen}")

    try:
        slug = service.generate(prompt, ("en",), lambda m: print(f"  {m}"), ai_hero=True)
        title = _load_video_title(slug) or topic.get("titulo", "")

        # Sin canal propio todavía → NO subir (no contaminar WaitWhy). Solo generar.
        if not has_creds:
            _mark_used(topic["key"])
            print(f"  stoic: sin YT_STOIC_* → generado, subida OMITIDA (pre-cableado)")
            _notify(f"🏛️ <b>{DISPLAY_NAME}</b> (pre-cableado) · vídeo generado, sin canal YT aún\n"
                    f"<i>{title[:60]}</i>\nslug: <code>{slug}</code>")
            return {"status": "ok", "slug": slug, "url": "", "topic_key": topic["key"],
                    "yt_status": "skip_no_channel"}

        print(f"  stoic: subiendo a {DISPLAY_NAME}…")
        links = service.publish(slug, ("en",), privacy="public",
                                progress=lambda m: print(f"  {m}"), notify=False)
        _mark_used(topic["key"])
        url = links.get("en", "?")
        _notify(f"✅ <b>{DISPLAY_NAME}</b> · {url}\n<i>{title[:60]}</i>")

        # TikTok (→ Telegram) + IG propio (petición user 03/10). IG usa IG_STOIC_TOKEN
        # (cuenta propia, no contamina @waitwhy_); si no está, skip limpio.
        try:
            from ..config import UPLOADED_DIR, PENDING_DIR
            _mp4 = next((b / slug / "video_en_vertical.mp4" for b in (UPLOADED_DIR, PENDING_DIR)
                         if (b / slug / "video_en_vertical.mp4").exists()), None)
            if _mp4:
                from ..notify_batch import send_video_for_tiktok
                send_video_for_tiktok(str(_mp4), DISPLAY_NAME, title, url)
                from .. import social_reels
                social_reels.post_ig_reel(str(_mp4), title, url, slug, prefix=YT_PREFIX,
                                          hashtags=["stoicism", "philosophy", "mindset",
                                                    "discipline", "motivation", "shorts"])
        except Exception as e:
            print(f"  stoic: ig/tt fail — {e}")

        # Crosspost SOLO a RRSS propias del canal (sin contaminar otras marcas).
        # Bluesky estoico necesita su propio handle (BSKY_STOIC_*); si no está, se omite.
        try:
            if os.environ.get("BSKY_STOIC_HANDLE") and os.environ.get("BSKY_STOIC_APP_PASSWORD"):
                from .. import crosspost_full
                from ..config import UPLOADED_DIR, PENDING_DIR
                dst = next((b / slug for b in (UPLOADED_DIR, PENDING_DIR) if (b / slug).exists()), None)
                if dst:
                    cross = crosspost_full.crosspost_short(
                        dst, title, url, teaser=f"🏛️ {topic.get('principle','Stoic wisdom')}",
                        channel_label="stoic")
                    _notify(f"🏛️ <b>Stoic · RRSS</b> {crosspost_full.summary_line(cross)}")
            else:
                print("  stoic: sin BSKY_STOIC_* → crosspost omitido (no contamino otras marcas)")
        except Exception as e:
            print(f"  stoic crosspost fail: {e}")
        return {"status": "ok", "slug": slug, "url": url, "topic_key": topic["key"]}
    except Exception as e:
        from ..upload_youtube import DedupSkip
        if isinstance(e, DedupSkip):
            print(f"  stoic: skip dedup — {e}")
            _notify(f"⏭️ <b>{DISPLAY_NAME}</b>: salté un duplicado (premisa no-repetir).")
            return {"status": "skip_dedup", "error": str(e), "topic_key": topic["key"]}
        import traceback
        traceback.print_exc()
        _notify(f"❌ {DISPLAY_NAME} falló: {type(e).__name__}: {str(e)[:200]}", urgent=True)
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        _clear_env()


LONG_TARGET_MINUTES = 10
LONG_DAYS = (6,)  # domingo (weekday: lun=0..dom=6) → ~1 long-form/semana


def _build_long_prompt(t: dict) -> str:
    return (
        f"[LONG-FORM · Channel {DISPLAY_NAME} · faceless EN · Stoic philosophy] "
        f"Theme: {t.get('stressor','')} — Stoic lens: {t.get('stoic','the Stoics')} / "
        f"{t.get('principle','')}. "
        f"Expand into a ~{LONG_TARGET_MINUTES} min deep-dive with 4-6 chapters: a strong hook, "
        f"what the Stoics actually taught about this, how it applies to modern life, concrete "
        f"practices, and a closing reflection. Calm, grounded, mentor tone. "
        f"VERACITY: teach the principle in your own words; do NOT fabricate or misattribute "
        f"quotes; non-YMYL. SEO long-form title. Closing CTA: subscribe for daily Stoic discipline."
    )


def run_longform() -> dict[str, Any]:
    """Genera + (si hay canal) sube 1 long-form estoico (~10 min). 1×/semana (lo marca
    el disparo); tope 1/día. Pre-cableado: sin secrets no-op."""
    from .. import service
    has_creds = bool(os.environ.get(YT_PREFIX + "_REFRESH_TOKEN"))
    allow_test = os.environ.get("STOIC_GENERATE_WITHOUT_CHANNEL", "").lower() in ("1", "true", "yes")
    if not has_creds and not allow_test:
        print("  stoic-long: sin YT_STOIC_* → no-op (canal pendiente)")
        return {"status": "no_channel"}
    # Puerta por día: Stoic genera long-form los DOMINGOS (~1×/semana) aunque la
    # cadena de shorts lo invoque 4-5×/día. (test ignora la puerta.)
    if has_creds and datetime.now(timezone.utc).weekday() not in LONG_DAYS:
        print(f"  stoic-long: hoy no es día de long-form ({LONG_DAYS}) — skip")
        return {"status": "skip_not_longform_day"}
    if has_creds and _today_count(longform=True) >= 1:
        print("  stoic-long: ya hay long-form hoy — skip")
        return {"status": "skip_daily_cap"}

    all_t = topics.all_topics()
    fresh = [t for t in all_t if not _recently_used(t["key"] + "_LONG")]
    if not fresh:
        fresh = all_t
    try:
        from .. import dedup_common
        recents = dedup_common.recent_titles_from_history(PLATFORM_KEY, days=180)
        cand = [t for t in fresh if not dedup_common.title_is_repeat(t.get("titulo") or "", recents)]
        if cand:
            fresh = cand
    except Exception:
        pass
    if not fresh:
        return {"status": "no_topic"}
    topic = random.choice(fresh)

    prompt = _build_long_prompt(topic)
    print(f"  stoic-long: topic={topic['key']}")
    _set_env()
    try:
        slug = service.generate_long(prompt, target_minutes=LONG_TARGET_MINUTES,
                                     langs=("en",), progress=lambda m: print(f"  {m}"))
        if not has_creds:
            _mark_used(topic["key"] + "_LONG")
            _notify(f"🏛️ <b>{DISPLAY_NAME} · long-form</b> (pre-cableado) · generado sin canal\n"
                    f"slug <code>{slug}</code>")
            return {"status": "ok", "slug": slug, "url": "", "yt_status": "skip_no_channel", "kind": "long"}
        links = service.publish_long(slug, ("en",), privacy="public",
                                     progress=lambda m: print(f"  {m}"), notify=False)
        _mark_used(topic["key"] + "_LONG")
        url = links.get("en", "?")
        _notify(f"✅ <b>{DISPLAY_NAME} · long-form</b>\n{url}\nslug <code>{slug}</code>")
        return {"status": "ok", "slug": slug, "url": url, "topic_key": topic["key"], "kind": "long"}
    except Exception as e:
        from ..upload_youtube import DedupSkip
        if isinstance(e, DedupSkip):
            print(f"  stoic-long: skip dedup — {e}")
            _notify(f"⏭️ <b>{DISPLAY_NAME} · long-form</b>: salté un duplicado.")
            return {"status": "skip_dedup", "error": str(e), "topic_key": topic["key"]}
        import traceback
        traceback.print_exc()
        _notify(f"❌ {DISPLAY_NAME} long-form falló: {type(e).__name__}: {str(e)[:200]}")
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        _clear_env()
