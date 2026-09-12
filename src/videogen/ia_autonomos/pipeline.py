"""Pipeline IA Autónomos ES — Short 1×/día.

Reusa 100% infraestructura via ChannelConfig + env overrides:
- SCRIPT_SYSTEM_PROMPT_FILE=ia_autonomos_system.md
- YT_CHANNEL_PREFIX=YT_IA

Requiere GH Secrets (crear en cuando el canal YT esté listo):
- YT_IA_REFRESH_TOKEN
- YT_IA_CLIENT_ID
- YT_IA_CLIENT_SECRET

Si secrets faltan, el pipeline aborta silenciosamente con log.
"""
from __future__ import annotations

import json
import os
import random
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from ..config import ROOT
from ..channel_pipeline import ChannelConfig, run_channel_longform_once
from . import topic_pool


CONFIG = ChannelConfig(
    slug="ia_autonomos",
    display_name="IA Autónomos ES",
    handle="@IAAutonomos_es",
    yt_prefix="YT_IA",
    system_prompt_file="ia_autonomos_system.md",
    topic_pool_module="videogen.ia_autonomos.topic_pool",
    ledger_filename="ia_autonomos_ledger.json",
    kokoro_voice_es="em_alex",
    edge_voice_es="es-ES-ArnauNeural",
    audience_emoji={"autonomos": "🤖", "pymes": "🏢", "_": "🧠"},
    series_name="IA Autónomos ES",
    cooldown_days=90,
)

LEDGER_PATH = ROOT / "output" / "ia_autonomos_ledger.json"
COOLDOWN_DAYS = 90


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


def _pick_topic() -> dict | None:
    all_t = topic_pool.all_topics()
    fresh = [t for t in all_t if not _recently_used(t["key"])]
    if not fresh:
        fresh = all_t
    return random.choice(fresh)


def _next_episode_num() -> int:
    return len(_load_ledger()) + 1


def _build_topic_prompt(t: dict) -> str:
    ep = _next_episode_num()
    return (
        f"[Episodio #{ep} · Canal IA Autónomos ES · audiencia={t['audiencia']} · "
        f"categoria={t['categoria']}] "
        f"Tema: {t['titulo']}. "
        f"Hook obligatorio: {t['hook']}. "
        f"Cifra ancla que DEBE aparecer: {t['cifra_ancla']}. "
        f"El title DEBE seguir el patrón '[Acción concreta] con IA gratis · [Cifra] · #{ep}'. "
        f"El thumbnail_text DEBE mostrar CIFRA en línea 1 y VERBO ACCIÓN "
        f"(AUTOMATIZA/GENERA/AHORRA/DEDUCE) en línea 2. "
        f"CIERRE OBLIGATORIO: 'Guarda este vídeo. Sígueme para más herramientas IA gratis.'"
    )


def _notify(text: str) -> None:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data=json.dumps({"chat_id": int(chat), "text": text,
                                "parse_mode": "HTML"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass


def run_longform():
    return run_channel_longform_once(CONFIG)


def run_once() -> dict[str, Any]:
    """Genera + sube 1 short IA-autónomos al canal YT_IA."""
    from .. import service

    # Guardia: si faltan secrets del canal YT_IA, aborta con nota clara
    if not os.environ.get("YT_IA_REFRESH_TOKEN"):
        _notify("⚠️ <b>IA Autónomos ES</b> · pipeline pausado — "
                 "faltan secrets YT_IA_REFRESH_TOKEN/CLIENT_ID/CLIENT_SECRET. "
                 "Crear canal YT y añadir secrets en GH repo settings.")
        return {"status": "no_secrets"}

    topic = _pick_topic()
    if not topic:
        return {"status": "no_topic"}

    topic_prompt = _build_topic_prompt(topic)
    print(f"  ia_autonomos: topic={topic['key']} audiencia={topic['audiencia']}")

    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = "ia_autonomos_system.md"
    os.environ["YT_CHANNEL_PREFIX"] = "YT_IA"

    try:
        slug = service.generate(topic_prompt, ("es",), lambda m: print(f"  {m}"),
                                    ai_hero=True)
        print(f"  ia_autonomos: video local ok, subiendo al canal…")
        links = service.publish(slug, ("es",), privacy="public",
                                    progress=lambda m: print(f"  {m}"), notify=False)
        _mark_used(topic["key"])
        url = links.get("es", "?")

        cross = _crosspost(slug, url, topic)
        cross_summary = " · ".join(f"{k}{'✅' if v else '❌'}"
                                       for k, v in cross.items())
        _notify(f"✅ <b>IA Autónomos ES</b> · {url}\n"
                 f"<i>{topic.get('titulo','')[:60]}</i> · RRSS {cross_summary}")
        return {"status": "ok", "slug": slug, "url": url,
                 "topic_key": topic["key"], "crosspost": cross}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _notify(f"❌ IA Autónomos short falló: {type(e).__name__}: {str(e)[:200]}")
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
        os.environ.pop("YT_CHANNEL_PREFIX", None)


def _load_video_title(slug: str) -> str | None:
    from ..config import PENDING_DIR, UPLOADED_DIR
    for base in (UPLOADED_DIR, PENDING_DIR):
        p = base / slug / "scripts.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return (data.get("es") or {}).get("title")
            except Exception:
                pass
    return None


def _crosspost(slug: str, url: str, topic: dict) -> dict[str, bool]:
    result: dict[str, bool] = {}
    title = _load_video_title(slug) or topic.get("titulo", "")
    if not title or not url or url == "?":
        return result
    teaser = f"🤖 IA gratis para {topic.get('audiencia','')} — {topic.get('cifra_ancla','')}"

    try:
        from .. import bluesky_poster
        r = bluesky_poster.post_short_to_bluesky(title, url, teaser=teaser)
        result["🦋"] = bool(r)
    except Exception as e:
        print(f"  ia_autonomos bluesky fail: {e}")
        result["🦋"] = False

    try:
        from .. import mastodon_poster
        r = mastodon_poster.post_short_to_mastodon(title, url, teaser=teaser)
        result["🐘"] = bool(r)
    except Exception as e:
        print(f"  ia_autonomos mastodon fail: {e}")
        result["🐘"] = False

    try:
        from ..config import UPLOADED_DIR, PENDING_DIR
        from .. import instagram_poster
        mp4 = None
        for base in (UPLOADED_DIR, PENDING_DIR):
            p = base / slug / "video_es_vertical.mp4"
            if p.exists():
                mp4 = p
                break
        if mp4:
            r = instagram_poster.post_reel_to_instagram(title, url, mp4, slug, teaser=teaser)
            result["📸"] = bool(r)
        else:
            result["📸"] = False
    except Exception as e:
        print(f"  ia_autonomos ig fail: {e}")
        result["📸"] = False

    try:
        from .. import threads_poster
        r = threads_poster.post_short_to_threads(title, url, teaser=teaser)
        result["🧵"] = bool(r)
    except Exception as e:
        print(f"  ia_autonomos threads fail: {e}")
        result["🧵"] = False

    return result
