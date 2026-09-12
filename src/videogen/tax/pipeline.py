"""Pipeline Fiscalidad España — Short 1×/día.

Reusa 100% infraestructura WaitWhy vía env overrides:
- SCRIPT_SYSTEM_PROMPT_FILE=tax_system.md → cambia el prompt de guion
- YT_CHANNEL_PREFIX=YT_TAX → usa creds YT_TAX_REFRESH_TOKEN etc

Flow:
1. Elige topic del pool tax, no usado últimos 90 días
2. Construye topic completo con marca "[TAX]" + serie
3. Setea env overrides
4. Llama service.generate() del pipeline WaitWhy
5. Marca ledger, notifica Telegram
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


# Config compartida con channel_pipeline (para long-form)
CONFIG = ChannelConfig(
    slug="tax",
    display_name="TaxHack ES",
    handle="@TaxHack_es",
    yt_prefix="YT_TAX",
    system_prompt_file="tax_system.md",
    topic_pool_module="videogen.tax.topic_pool",
    ledger_filename="tax_ledger.json",
    topic_pool_long_module="videogen.tax.topic_pool_long",
    kokoro_voice_es="em_alex",
    edge_voice_es="es-ES-XimenaNeural",
    audience_emoji={"autonomos": "👔", "particulares": "🧑",
                     "empresas": "🏢", "_": "💶"},
    series_name="TaxHack ES",
    cooldown_days=90,
)

TAX_LEDGER = ROOT / "output" / "tax_ledger.json"
COOLDOWN_DAYS = 90


def _load_ledger() -> dict[str, str]:
    if not TAX_LEDGER.exists():
        return {}
    try:
        return json.loads(TAX_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(key: str) -> None:
    TAX_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    data = _load_ledger()
    data[key] = datetime.now(timezone.utc).isoformat()
    TAX_LEDGER.write_text(json.dumps(data, indent=2, ensure_ascii=False),
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
    """Rota entre audiencias (autonomos/particulares/empresas) para variedad."""
    all_t = topic_pool.all_topics()
    fresh = [t for t in all_t if not _recently_used(t["key"])]
    if not fresh:
        fresh = all_t  # todos usados → recicla
    # Balance por audiencia
    by_aud: dict[str, list[dict]] = {}
    for t in fresh:
        by_aud.setdefault(t.get("audiencia", "misc"), []).append(t)
    # Elige audiencia menos representada últimamente (round-robin simple)
    audiencia_choice = random.choice(list(by_aud.keys()))
    return random.choice(by_aud[audiencia_choice])


def _next_episode_num() -> int:
    """Cuenta episodios ya publicados via ledger."""
    return len(_load_ledger()) + 1


def _build_topic_prompt(t: dict) -> str:
    """Compone el topic completo que se pasa a service.generate()."""
    ep = _next_episode_num()
    return (
        f"[Episodio #{ep} · Canal TaxHack ES · audiencia={t['audiencia']} · "
        f"categoria={t['categoria']}] "
        f"Tema: {t['titulo']}. "
        f"Hook obligatorio: {t['hook']}. "
        f"Cifra ancla que DEBE aparecer: {t['cifra_ancla']}. "
        f"El title DEBE seguir el patrón '[Beneficio concreto] · [Cifra] · #{ep}'. "
        f"El thumbnail_text DEBE mostrar CIFRA en línea 1 y VERBO ACCIÓN "
        f"(AHORRA/DEDUCE/RECUPERA/EXENTO) en línea 2. "
        f"CIERRE OBLIGATORIO: 'Consulta con tu asesor. Sígueme para más trucos legales.'"
    )


def run_longform():
    return run_channel_longform_once(CONFIG)


def run_once() -> dict[str, Any]:
    """Genera + sube 1 short fiscal al canal TaxHack."""
    from .. import service

    topic = _pick_topic()
    if not topic:
        return {"status": "no_topic"}

    topic_prompt = _build_topic_prompt(topic)
    print(f"  tax: topic={topic['key']} audiencia={topic['audiencia']}")

    # Env overrides: prompt fiscal + canal YT separado + voz más profesional
    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = "tax_system.md"
    os.environ["YT_CHANNEL_PREFIX"] = "YT_TAX"
    # Voz Kokoro más asertiva/masculina profesional para nicho fiscal
    # (em_alex es default WaitWhy — mantenemos por ahora; user puede override
    # via secret KOKORO_VOICE_ES_TAX si quiere otra).
    if not os.environ.get("KOKORO_VOICE_ES_TAX"):
        os.environ["KOKORO_VOICE_ES_TAX"] = "em_alex"  # default sano
    # Diagnóstico: confirma que los secrets YT_TAX_* llegaron al proceso
    print(f"  tax: YT_CHANNEL_PREFIX=YT_TAX · "
          f"has_refresh={bool(os.environ.get('YT_TAX_REFRESH_TOKEN'))} · "
          f"has_client_id={bool(os.environ.get('YT_TAX_CLIENT_ID'))} · "
          f"has_client_secret={bool(os.environ.get('YT_TAX_CLIENT_SECRET'))}")

    # Sin notif previa (reduce ruido). Solo notifica al terminar.
    try:
        slug = service.generate(topic_prompt, ("es",), lambda m: print(f"  {m}"),
                                 ai_hero=True)
        print(f"  tax: video generado local, subiendo al canal TaxHack ES…")
        # service.publish sube a YT — usa YT_CHANNEL_PREFIX=YT_TAX del env
        # para elegir creds del canal correcto vía upload_youtube._get_credentials.
        links = service.publish(slug, ("es",), privacy="public",
                                 progress=lambda m: print(f"  {m}"), notify=False)
        _mark_used(topic["key"])
        url = links.get("es", "?")

        # Cross-post RRSS con caption fiscal (distinguido de true crime WaitWhy)
        crosspost_result = _crosspost_tax(slug, url, topic)
        cross_summary = " · ".join(f"{k}{'✅' if v else '❌'}" for k, v in crosspost_result.items())

        _notify(f"✅ <b>TaxHack ES</b> · {url}\n"
                f"<i>{topic.get('titulo','')[:60]}</i> · RRSS {cross_summary}")
        _send_tt_video_tax(slug, topic.get("titulo", ""), url)
        return {"status": "ok", "slug": slug, "url": url,
                "topic_key": topic["key"], "crosspost": crosspost_result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _notify(f"❌ Tax short falló: {type(e).__name__}: {str(e)[:200]}",
                 urgent=True)
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        # Limpia env para no contaminar procesos concurrentes en mismo runner
        os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
        os.environ.pop("YT_CHANNEL_PREFIX", None)


def _load_video_title(slug: str) -> str | None:
    """Lee el título real del video subido desde output/uploaded/{slug}/scripts.json"""
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


def _crosspost_tax(slug: str, url: str, topic: dict) -> dict[str, bool]:
    """Cross-post del short fiscal a Bluesky/Mastodon/Threads/IG.

    Caption con marca 💶 clara para distinguir del contenido true crime
    de WaitWhy (compartimos cuentas — decisión user 11/09/26).
    Horario tax = 10:15 CEST vs WaitWhy 08:15 CEST → 2h separación.
    """
    result: dict[str, bool] = {}
    title = _load_video_title(slug) or topic.get("titulo", "")
    if not title or not url or url == "?":
        return result

    # Teaser fiscal para clarificar audiencia
    audiencia_emoji = {"autonomos": "👔", "particulares": "🧑",
                        "empresas": "🏢"}.get(topic.get("audiencia", ""), "💶")
    teaser = f"{audiencia_emoji} Truco fiscal para {topic.get('audiencia','')} — {topic.get('cifra_ancla', '')}"

    # Bluesky
    try:
        from .. import bluesky_poster
        r = bluesky_poster.post_short_to_bluesky(title, url, teaser=teaser)
        result["🦋"] = bool(r)
    except Exception as e:
        print(f"  tax bluesky fail: {e}")
        result["🦋"] = False

    # Mastodon
    try:
        from .. import mastodon_poster
        r = mastodon_poster.post_short_to_mastodon(title, url, teaser=teaser)
        result["🐘"] = bool(r)
    except Exception as e:
        print(f"  tax mastodon fail: {e}")
        result["🐘"] = False

    # Instagram Reels
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
        print(f"  tax ig fail: {e}")
        result["📸"] = False

    # Threads
    try:
        from .. import threads_poster
        r = threads_poster.post_short_to_threads(title, url, teaser=teaser)
        result["🧵"] = bool(r)
    except Exception as e:
        print(f"  tax threads fail: {e}")
        result["🧵"] = False

    return result


def _notify(text: str, urgent: bool = False) -> None:
    """Encola notificación (batched al final del proceso).
    urgent=True → envía inmediatamente (fallos críticos)."""
    from ..notify_batch import add
    add(text, urgent=urgent)


def _send_tt_video_tax(slug: str, title: str, url: str) -> None:
    """MP4 vertical → Telegram para subida manual a TikTok."""
    try:
        from ..config import UPLOADED_DIR, PENDING_DIR
        from ..notify_batch import send_video_for_tiktok
        for base in (UPLOADED_DIR, PENDING_DIR):
            p = base / slug / "video_es_vertical.mp4"
            if p.exists():
                send_video_for_tiktok(p, "TaxHack ES", title, url)
                return
    except Exception as e:
        print(f"  tax: TT tg video fail — {e}")
