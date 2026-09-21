"""Pipeline canal TopRanking ES — bar chart races."""
from __future__ import annotations

import json
import os
import random
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from ..config import ROOT
from . import generator, topic_pool

RANKING_LEDGER = ROOT / "output" / "ranking_ledger.json"
COOLDOWN_DAYS = 90


# ── Long-form (Top-N en cuenta atrás narrada) ──────────────────────────────
# Reutiliza el render/upload PROBADO (service.generate_long/publish_long, igual
# que tax/legal/pov) pero con prompt de CUENTA ATRÁS propio y pool de rankings
# reales curados — NO el prompt genérico "explicación en capítulos" (que choca
# con el formato countdown) ni los topics dinámicos "análisis" del refresher.
LONG_COOLDOWN_DAYS = 120


def run_longform() -> dict[str, Any]:
    """Genera + sube 1 long-form (~8 min) Top-N en cuenta atrás al canal YT_RANKING."""
    import os
    import random
    from .. import service
    from . import topic_pool_long
    from ..channel_pipeline import _load_ledger, _mark_used, _recently_used, _notify

    ledger = ROOT / "output" / "ranking_ledger.json"
    pool = topic_pool_long.all_topics()
    fresh = [t for t in pool if not _recently_used(ledger, t["key"] + "_LONG", LONG_COOLDOWN_DAYS)]
    if not fresh:
        fresh = pool
    topic = random.choice(fresh)

    topic_prompt = (
        f"[LONG-FORM · CUENTA ATRÁS · Canal TopRanking ES] "
        f"Tema: {topic['titulo']}. "
        f"FORMATO OBLIGATORIO = Top-N en cuenta atrás del #N al #1 (sigue la estructura "
        f"del system prompt: cold open que adelanta el #1 sin revelarlo → contexto con "
        f"criterio y fuente → cuenta atrás puesto a puesto con su cifra y una curiosidad "
        f"real → clímax en el #1 → cierre con pódium y CTA). "
        f"Gancho central: {topic['hook']}. Criterio/cifra de cada puesto: {topic['cifra_ancla']}. "
        f"TODOS los datos reales y verificables, citando la fuente y el año. "
        f"Title patrón: 'TOP N: {topic['titulo']} · del #N al #1'."
    )

    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = "ranking_system.md"
    os.environ["YT_CHANNEL_PREFIX"] = "YT_RANKING"
    os.environ.setdefault("EDGE_VOICE_ES_RANKING", "es-ES-AlvaroNeural")
    print(f"  ranking-long: topic={topic['key']} · "
          f"has_refresh={bool(os.environ.get('YT_RANKING_REFRESH_TOKEN'))}")
    try:
        slug = service.generate_long(topic_prompt, target_minutes=8, langs=("es",),
                                       progress=lambda m: print(f"  {m}"))
        print("  ranking-long: subiendo a TopRanking ES…")
        links = service.publish_long(slug, ("es",), privacy="public",
                                       progress=lambda m: print(f"  {m}"), notify=False)
        _mark_used(ledger, topic["key"] + "_LONG")
        url = links.get("es", "?")
        _notify(f"✅ <b>TopRanking · long-form</b>\nslug: <code>{slug}</code>\n{url}")
        return {"status": "ok", "slug": slug, "url": url,
                "topic_key": topic["key"], "kind": "long"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _notify(f"❌ TopRanking long-form falló: {type(e).__name__}: {str(e)[:200]}")
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
        os.environ.pop("YT_CHANNEL_PREFIX", None)


def _load_ledger() -> dict[str, str]:
    if not RANKING_LEDGER.exists():
        return {}
    try:
        return json.loads(RANKING_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(key: str) -> None:
    RANKING_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    d = _load_ledger()
    d[key] = datetime.now(timezone.utc).isoformat()
    RANKING_LEDGER.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


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


def _upload_ranking(meta: dict) -> dict | None:
    """Sube al canal TopRanking ES usando YT_RANKING_* creds."""
    from ..upload_youtube import upload_video, set_thumbnail
    prev_prefix = os.environ.get("YT_CHANNEL_PREFIX", "")
    os.environ["YT_CHANNEL_PREFIX"] = "YT_RANKING"
    try:
        vid = upload_video(
            Path(meta["video_path"]),
            title=meta["title"][:100],
            description=meta["description"][:4900],
            tags=meta.get("tags", []),
            category_id="27",  # Education
            is_short=True,
            privacy="public",
        )
        return {"video_id": vid, "url": f"https://youtube.com/shorts/{vid}"}
    except Exception as e:
        print(f"  ranking upload fail: {type(e).__name__}: {e}")
        return None
    finally:
        if prev_prefix:
            os.environ["YT_CHANNEL_PREFIX"] = prev_prefix
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)


def _notify(text: str, urgent: bool = False) -> None:
    """Encola notificación (batched al final del proceso).
    urgent=True → envía inmediatamente (fallos críticos)."""
    from ..notify_batch import add
    add(text, urgent=urgent)


def run_once() -> dict[str, Any]:
    """Genera + sube 1 ranking al canal TopRanking ES."""
    topic = _pick_topic()
    if not topic:
        return {"status": "no_topic"}

    print(f"  ranking: topic={topic['key']}")
    meta = generator.generate_ranking_video(
        topic, generator.RANKING_ROOT,
        duration_seconds=55, vertical=True,
    )
    if not meta:
        _notify(f"❌ Ranking falló generación · {topic['key']}", urgent=True)
        return {"status": "gen_fail", "topic_key": topic["key"]}

    print(f"  ranking: video generado · uploading canal TopRanking ES…")
    up = _upload_ranking(meta)
    if not up:
        _notify(f"⚠️ Ranking {topic['key']} generado pero upload falló",
                 urgent=True)
        return {"status": "upload_fail", "meta": meta}

    _mark_used(topic["key"])

    # Cross-post RRSS
    cross = _crosspost(meta["title"], up["url"], topic, meta=meta)
    cross_summary = " · ".join(f"{k}{'✅' if v else '❌'}" for k, v in cross.items())
    _notify(f"✅ <b>TopRanking ES</b> · {up['url']}\n"
            f"<i>{meta['title'][:60]}</i> · RRSS {cross_summary}")
    # MP4 → Telegram para subir manual a TikTok
    try:
        from ..notify_batch import send_video_for_tiktok
        vp = meta.get("video_path")
        if vp:
            send_video_for_tiktok(vp, "TopRanking ES", meta.get("title", ""), up["url"])
    except Exception as e:
        print(f"  ranking: TT tg video fail — {e}")
    return {"status": "ok", "slug": meta["slug"], "url": up["url"],
            "topic_key": topic["key"], "crosspost": cross}


def _crosspost(title: str, url: str, topic: dict, meta: dict | None = None) -> dict[str, bool]:
    """Cross-post ranking a Bluesky/Mastodon/Threads/Instagram con marca 📊.

    IG lo hace vía crosspost_full — usa el mp4 del slug ranking. Sin mp4 → skip IG.
    """
    from pathlib import Path
    from .. import crosspost_full
    from ..config import UPLOADED_DIR, PENDING_DIR
    teaser = f"📊 Ranking · {topic.get('fuente','')} · dato clave: {topic.get('cifra_ancla','')}"

    # Buscar dst_dir del slug para que IG encuentre el mp4 vertical
    slug = meta.get("slug") if meta else None
    dst_dir: Path | None = None
    if slug:
        for base in (UPLOADED_DIR, PENDING_DIR):
            p = base / slug
            if p.exists():
                dst_dir = p
                break
    if dst_dir is None:
        # Fallback: mp4 sin dst_dir → solo RRSS texto
        return crosspost_full.crosspost_short_from_mp4(
            Path(meta.get("video_path", "")) if meta else Path(""),
            title, url, teaser=teaser, channel_label="ranking", slug=slug,
        )
    return crosspost_full.crosspost_short(dst_dir, title, url,
                                            teaser=teaser, channel_label="ranking")
