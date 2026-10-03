"""Factory genérico para canales NARRADOS pre-cableados (tanda 02/10).

Reusa la infra pesada (service.generate/publish: voz Edge + Pexels + imágenes IA +
música + captions + upload) igual que ai_tools/stoic, pero parametrizado por un
SimpleChannelConfig → un canal nuevo = 1 config + 1 system prompt, sin duplicar
código ni tocar el channel_pipeline ES vivo (evita contaminar sus RRSS).

Reglas heredadas:
- SIN secrets YT_<PREFIX>_* → NO-OP instantáneo (no genera, no gasta); se AUTO-ACTIVA
  al crear el canal. Flag <PREFIX>_GENERATE_WITHOUT_CHANNEL=1 para testear generación.
- Dedup semántico por título (backstop al guardarraíl de subida) + DedupSkip→skip_dedup.
- Crosspost SOLO a RRSS propias del canal (BSKY_<SUFIJO>_*) → no contamina otras marcas.
- Veracidad + no-YMYL viven en el system prompt de cada canal.

Ver [[stoic-mind-nuevo-canal]], [[dedup-semantico-titulo]], [[veracidad-obligatoria]].
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from .config import ROOT


@dataclass
class SimpleChannelConfig:
    slug: str                      # 'misterios'
    prefix: str                    # 'YT_MISTERIOS'
    display_name: str              # 'Enigmas sin Resolver'
    platform_key: str              # 'youtube_misterios'
    lang: str                      # 'es' | 'en'
    system_prompt_file: str        # system prompt compartido o propio en prompts/
    seed: list[dict]               # topics semilla
    theme_desc: str                # descripción para el refresher Gemini
    veracity_rules: str            # reglas duras para el refresher
    tone: str = ""                 # registro/tono específico del canal (inyectado en el prompt)
    to_tiktok: bool = False        # enviar el Short a Telegram para subir a TikTok
    to_ig: bool = False            # subir Reel a IG propio (IG_<SUFIJO>_TOKEN; skip si no está)
    ig_hashtags: list = field(default_factory=list)
    category_id: str = "27"        # YouTube category (27=Education, 24=Entertainment)
    cooldown_days: int = 120
    emoji: str = "🎬"
    cross_teaser: str = ""         # prefijo del teaser de crosspost
    max_dynamic: int = 200
    refresh_interval_days: int = 7

    @property
    def ledger_path(self):
        return ROOT / "output" / f"{self.slug}_ledger.json"

    @property
    def dynamic_path(self):
        return ROOT / "output" / f"dynamic_topics_{self.slug}.json"


# ───────────────────────────── ledger ─────────────────────────────
def _load_ledger(cfg: SimpleChannelConfig) -> dict[str, str]:
    if not cfg.ledger_path.exists():
        return {}
    try:
        return json.loads(cfg.ledger_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(cfg: SimpleChannelConfig, key: str) -> None:
    cfg.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    d = _load_ledger(cfg)
    d[key] = datetime.now(timezone.utc).isoformat()
    cfg.ledger_path.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def _recently_used(cfg: SimpleChannelConfig, key: str) -> bool:
    entry = _load_ledger(cfg).get(key)
    if not entry:
        return False
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(entry)) < timedelta(days=cfg.cooldown_days)
    except Exception:
        return False


# ───────────────────────────── topics (seed + dinámicos) ─────────────────────────────
def _load_dynamic(cfg: SimpleChannelConfig) -> dict:
    if not cfg.dynamic_path.exists():
        return {"generated_at": None, "topics": []}
    try:
        return json.loads(cfg.dynamic_path.read_text(encoding="utf-8"))
    except Exception:
        return {"generated_at": None, "topics": []}


def _save_dynamic(cfg: SimpleChannelConfig, data: dict) -> None:
    cfg.dynamic_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.dynamic_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _refresh_due(cfg: SimpleChannelConfig) -> bool:
    gen = _load_dynamic(cfg).get("generated_at")
    if not gen:
        return True
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(gen)) > timedelta(days=cfg.refresh_interval_days)
    except Exception:
        return True


def refresh_dynamic(cfg: SimpleChannelConfig, n: int = 12) -> list[dict] | None:
    """Pide a Gemini N ideas NUEVAS para el tema del canal y ACUMULA (dedup key+título).
    Esquema genérico: key/titulo/hook/angle/visual. Veracidad la fija cfg.veracity_rules."""
    existing = list(cfg.seed) + _load_dynamic(cfg).get("topics", [])
    existing_keys = {t.get("key") for t in existing}
    existing_titles = [" ".join((t.get("titulo") or "").split()) for t in existing if t.get("titulo")]
    avoid = "\n".join(f"- {t[:70]}" for t in existing_titles[:80])
    try:
        from google import genai
        from google.genai import types
        from .config import gemini_key
        key = gemini_key()
        if not key:
            return None
        client = genai.Client(api_key=key)
        schema = {
            "type": "object",
            "properties": {"topics": {"type": "array", "items": {"type": "object", "properties": {
                "key": {"type": "string"}, "titulo": {"type": "string"},
                "hook": {"type": "string"}, "angle": {"type": "string"},
                "visual": {"type": "string"},
            }, "required": ["key", "titulo", "hook", "angle", "visual"]}}},
            "required": ["topics"],
        }
        lang_name = "Spanish" if cfg.lang == "es" else "English"
        prompt = (
            f"Generate {n} NEW faceless YouTube Shorts ideas in {lang_name} for this channel: "
            f"{cfg.theme_desc}\n\n"
            f"STRICT RULES:\n{cfg.veracity_rules}\n"
            f"- No YMYL (no medical/therapy/financial advice, no politics).\n"
            f"- Fresh and specific. Do NOT repeat or resemble these existing titles:\n{avoid}\n\n"
            f"For each: key (snake_case, unique), titulo ({lang_name} SEO title with a curiosity gap), "
            f"hook (a vivid 1-sentence cold-open for 0-3s), angle (the specific verifiable content point "
            f"to cover), visual (3-4 cinematic scene keywords for stock/AI images)."
        )
        resp = client.models.generate_content(
            model="gemini-3.5-flash-lite", contents=prompt,
            config=types.GenerateContentConfig(temperature=1.0, max_output_tokens=6000,
                                               response_mime_type="application/json", response_schema=schema),
        )
        got = json.loads((resp.text or "").strip()).get("topics", [])
        try:
            from . import dedup_common
            _isrep = lambda t: dedup_common.title_is_repeat(  # noqa: E731
                " ".join((t.get("titulo") or "").split()), existing_titles)
        except Exception:
            _isrep = lambda t: False  # noqa: E731
        fresh: list[dict] = []
        seen = set(existing_keys)
        for t in got:
            k = (t.get("key") or "").strip()
            if not k or k in seen or not t.get("titulo") or not t.get("angle"):
                continue
            if _isrep(t):
                continue
            seen.add(k)
            fresh.append(t)
        if not fresh:
            print(f"  {cfg.slug} topics: 0 ideas nuevas válidas")
            return None
        acc = (_load_dynamic(cfg).get("topics", []) + fresh)[-cfg.max_dynamic:]
        _save_dynamic(cfg, {"generated_at": datetime.now(timezone.utc).isoformat(), "topics": acc})
        print(f"  {cfg.slug} topics: ✅ +{len(fresh)} (pool dinámico={len(acc)})")
        return fresh
    except Exception as e:
        print(f"  {cfg.slug} topics refresh fail: {type(e).__name__}: {e}")
        return None


def all_topics(cfg: SimpleChannelConfig) -> list[dict]:
    if _refresh_due(cfg):
        refresh_dynamic(cfg)
    seen = {t["key"] for t in cfg.seed}
    dyn = [t for t in _load_dynamic(cfg).get("topics", []) if t.get("key") and t["key"] not in seen]
    return list(cfg.seed) + dyn


def _pick_topic(cfg: SimpleChannelConfig) -> dict | None:
    all_t = all_topics(cfg)
    fresh = [t for t in all_t if not _recently_used(cfg, t["key"])]
    if len(fresh) < 3:
        try:
            refresh_dynamic(cfg)
            all_t = all_topics(cfg)
            fresh = [t for t in all_t if not _recently_used(cfg, t["key"])]
        except Exception as e:
            print(f"  {cfg.slug}: refresh on-empty fail ({e})")
    if not fresh:
        fresh = all_t
    try:
        from . import dedup_common
        recents = dedup_common.recent_titles_from_history(cfg.platform_key, days=180)
        cand = [t for t in fresh
                if not dedup_common.title_is_repeat(t.get("titulo") or t.get("key", ""), recents)]
        if cand:
            fresh = cand
    except Exception as e:
        print(f"  {cfg.slug}: dedup título skip ({e})")
    return random.choice(fresh) if fresh else None


def _build_prompt(cfg: SimpleChannelConfig, t: dict) -> str:
    avoid = ""
    try:
        from . import dedup_common
        block = dedup_common.recent_titles_block(cfg.platform_key, days=150, n=25)
        if block:
            avoid = f" Do NOT repeat/resemble already-published titles: {block}."
    except Exception:
        pass
    tone = f" Tone/register: {cfg.tone}." if cfg.tone else ""
    return (
        f"[Channel {cfg.display_name} · faceless {cfg.lang} Shorts]{tone} "
        f"Topic: {t.get('titulo','')}. "
        f"Mandatory cold-open hook (0-3s): {t.get('hook','')}. "
        f"Cover (verifiable, cite the source on screen): {t.get('angle','')}. "
        f"Structure: hook → payoff → one memorable closing line → CTA. "
        f"VERACITY: only verifiable facts + a citable source; no fabrication; non-YMYL. "
        f"Visual keywords: {t.get('visual','cinematic, atmospheric')}. "
        f"Title direction (improve if you can): '{t.get('titulo','')}'."
        + avoid
    )


def _notify(text: str, urgent: bool = False) -> None:
    from .notify_batch import add
    add(text, urgent=urgent)


def _load_video_title(slug: str, lang: str) -> str | None:
    from .config import PENDING_DIR, UPLOADED_DIR
    for base in (UPLOADED_DIR, PENDING_DIR):
        p = base / slug / "scripts.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return (data.get(lang) or {}).get("title")
            except Exception:
                pass
    return None


def run_once(cfg: SimpleChannelConfig) -> dict[str, Any]:
    """Genera + (si hay canal) sube 1 Short. Sin secrets → no-op (pre-cableado)."""
    from . import service

    has_creds = bool(os.environ.get(cfg.prefix + "_REFRESH_TOKEN"))
    allow_test = (os.environ.get(f"{cfg.prefix}_GENERATE_WITHOUT_CHANNEL", "").lower() in ("1", "true", "yes")
                  or os.environ.get("BATCH_GENERATE_WITHOUT_CHANNEL", "").lower() in ("1", "true", "yes"))
    if not has_creds and not allow_test:
        print(f"  {cfg.slug}: sin {cfg.prefix}_* y sin flag test → no-op (canal pendiente)")
        return {"status": "no_channel"}

    topic = _pick_topic(cfg)
    if not topic:
        return {"status": "no_topic"}

    prompt = _build_prompt(cfg, topic)
    print(f"  {cfg.slug}: topic={topic['key']}")
    prev_sp = os.environ.get("SCRIPT_SYSTEM_PROMPT_FILE")
    prev_px = os.environ.get("YT_CHANNEL_PREFIX")
    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = cfg.system_prompt_file
    os.environ["YT_CHANNEL_PREFIX"] = cfg.prefix
    try:
        slug = service.generate(prompt, (cfg.lang,), lambda m: print(f"  {m}"), ai_hero=True)
        title = _load_video_title(slug, cfg.lang) or topic.get("titulo", "")

        if not has_creds:
            _mark_used(cfg, topic["key"])
            print(f"  {cfg.slug}: generado, subida OMITIDA (pre-cableado)")
            _notify(f"{cfg.emoji} <b>{cfg.display_name}</b> (pre-cableado) · generado sin canal YT\n"
                    f"<i>{title[:60]}</i> · slug <code>{slug}</code>")
            return {"status": "ok", "slug": slug, "url": "", "topic_key": topic["key"],
                    "yt_status": "skip_no_channel"}

        links = service.publish(slug, (cfg.lang,), privacy="public",
                                progress=lambda m: print(f"  {m}"), notify=False)
        _mark_used(cfg, topic["key"])
        url = links.get(cfg.lang, "?")
        _notify(f"✅ <b>{cfg.display_name}</b> · {url}\n<i>{title[:60]}</i>")

        # TikTok (→ Telegram) + IG propio, solo si el canal los tiene activados (cfg).
        # IG usa IG_<SUFIJO>_TOKEN propio (no contamina otras marcas); skip si no está.
        if cfg.to_tiktok or cfg.to_ig:
            try:
                from .config import UPLOADED_DIR, PENDING_DIR
                _name = f"video_{cfg.lang}_vertical.mp4"
                _mp4 = next((b / slug / _name for b in (UPLOADED_DIR, PENDING_DIR)
                             if (b / slug / _name).exists()), None)
                if _mp4:
                    if cfg.to_tiktok:
                        from .notify_batch import send_video_for_tiktok
                        send_video_for_tiktok(str(_mp4), cfg.display_name, title, url)
                    if cfg.to_ig:
                        from . import social_reels
                        social_reels.post_ig_reel(str(_mp4), title, url, slug, prefix=cfg.prefix,
                                                  hashtags=cfg.ig_hashtags or None)
            except Exception as e:
                print(f"  {cfg.slug}: ig/tt fail — {e}")

        # Crosspost SOLO a Bluesky propio del canal (no contaminar otras marcas).
        try:
            suf = cfg.prefix.replace("YT_", "")
            if os.environ.get(f"BSKY_{suf}_HANDLE") and os.environ.get(f"BSKY_{suf}_APP_PASSWORD"):
                from . import crosspost_full
                from .config import UPLOADED_DIR, PENDING_DIR
                dst = next((b / slug for b in (UPLOADED_DIR, PENDING_DIR) if (b / slug).exists()), None)
                if dst:
                    cross = crosspost_full.crosspost_short(
                        dst, title, url, teaser=cfg.cross_teaser or f"{cfg.emoji} {cfg.display_name}",
                        channel_label=cfg.slug)
                    _notify(f"{cfg.emoji} <b>{cfg.display_name} · RRSS</b> {crosspost_full.summary_line(cross)}")
        except Exception as e:
            print(f"  {cfg.slug} crosspost fail: {e}")
        return {"status": "ok", "slug": slug, "url": url, "topic_key": topic["key"]}
    except Exception as e:
        from .upload_youtube import DedupSkip
        if isinstance(e, DedupSkip):
            print(f"  {cfg.slug}: skip dedup — {e}")
            _notify(f"⏭️ <b>{cfg.display_name}</b>: salté un duplicado (premisa no-repetir).")
            return {"status": "skip_dedup", "error": str(e), "topic_key": topic["key"]}
        import traceback
        traceback.print_exc()
        _notify(f"❌ {cfg.display_name} falló: {type(e).__name__}: {str(e)[:200]}", urgent=True)
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        if prev_sp is not None:
            os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = prev_sp
        else:
            os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
        if prev_px is not None:
            os.environ["YT_CHANNEL_PREFIX"] = prev_px
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)
