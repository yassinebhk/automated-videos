"""Pipeline genérico multi-canal. Cada nicho (tax/legal/ayudas/motor…)
lo instancia con su config: pool, prompt, prefix, handle, emoji audiencia.

Reusa 100% infraestructura WaitWhy vía env overrides:
- SCRIPT_SYSTEM_PROMPT_FILE → prompt system del nicho
- YT_CHANNEL_PREFIX → creds YT_{PREFIX}_* separadas
- KOKORO_VOICE_ES_{SUFFIX} → voz específica del canal (opcional)

Flow común:
1. Elige topic del pool, no usado últimos COOLDOWN_DAYS
2. Construye topic prompt con marca [NICHE] + serie
3. Setea env overrides
4. service.generate() + service.publish() → sube a YT
5. Cross-post RRSS Bluesky/Mastodon/Threads (compartidas)
6. Marca ledger, notifica Telegram
"""
from __future__ import annotations

import json
import os
import random
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable, Any

from .config import ROOT


@dataclass
class ChannelConfig:
    """Configuración de un canal — inmutable, se pasa a run_channel_once."""
    slug: str                       # 'tax', 'legal', 'ayudas', 'motor'
    display_name: str               # 'TaxHack ES'
    handle: str                     # '@TaxHack_es'
    yt_prefix: str                  # 'YT_TAX' (para creds env)
    system_prompt_file: str         # 'tax_system.md' en prompts/
    topic_pool_module: str          # 'videogen.tax.topic_pool'
    ledger_filename: str            # 'tax_ledger.json'
    kokoro_voice_es: str = "em_alex"
    audience_emoji: dict = field(default_factory=lambda: {})  # {'autonomos': '👔', …}
    series_name: str = "Serie"       # 'TaxHack ES', 'TusDerechos ES'
    cooldown_days: int = 90


def _load_ledger(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(path: Path, key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _load_ledger(path)
    data[key] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                     encoding="utf-8")


def _recently_used(path: Path, key: str, days: int) -> bool:
    entry = _load_ledger(path).get(key)
    if not entry:
        return False
    try:
        ts = datetime.fromisoformat(entry)
    except Exception:
        return False
    return (datetime.now(timezone.utc) - ts) < timedelta(days=days)


def _pick_topic(cfg: ChannelConfig) -> dict | None:
    """Elige topic del pool no usado en cooldown. Rota por audiencia."""
    import importlib
    mod = importlib.import_module(cfg.topic_pool_module)
    all_t = mod.all_topics()
    ledger_path = ROOT / "output" / cfg.ledger_filename
    fresh = [t for t in all_t if not _recently_used(ledger_path, t["key"], cfg.cooldown_days)]
    if not fresh:
        fresh = all_t
    # Balance por audiencia si el pool tiene esa clave
    if any("audiencia" in t for t in fresh):
        by_aud: dict[str, list[dict]] = {}
        for t in fresh:
            by_aud.setdefault(t.get("audiencia", "misc"), []).append(t)
        aud_choice = random.choice(list(by_aud.keys()))
        return random.choice(by_aud[aud_choice])
    return random.choice(fresh)


def _next_episode_num(cfg: ChannelConfig) -> int:
    return len(_load_ledger(ROOT / "output" / cfg.ledger_filename)) + 1


def _build_topic_prompt(cfg: ChannelConfig, t: dict) -> str:
    ep = _next_episode_num(cfg)
    aud = t.get("audiencia", "")
    cat = t.get("categoria", "")
    hook = t.get("hook", "")
    cifra = t.get("cifra_ancla", "")
    return (
        f"[Episodio #{ep} · Canal {cfg.display_name} · audiencia={aud} · categoria={cat}] "
        f"Tema: {t['titulo']}. "
        f"Hook obligatorio: {hook}. "
        f"Cifra ancla que DEBE aparecer: {cifra}. "
        f"El title DEBE seguir el patrón '[N] [Beneficio concreto] · [Cifra] · #{ep}' (TOP N lista). "
        f"El thumbnail_text DEBE mostrar N grande + CIFRA. "
        f"CIERRE: 'Consulta con un profesional tu caso. Sígueme para más.'"
    )


def _load_video_title(slug: str) -> str | None:
    from .config import PENDING_DIR, UPLOADED_DIR
    for base in (UPLOADED_DIR, PENDING_DIR):
        p = base / slug / "scripts.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return (data.get("es") or {}).get("title")
            except Exception:
                pass
    return None


def _crosspost(cfg: ChannelConfig, slug: str, url: str, topic: dict) -> dict[str, bool]:
    """Cross-post RRSS con marca del nicho (emoji audiencia + cifra)."""
    result: dict[str, bool] = {}
    title = _load_video_title(slug) or topic.get("titulo", "")
    if not title or not url or url == "?":
        return result

    aud = topic.get("audiencia", "")
    emoji = cfg.audience_emoji.get(aud, "📺")
    teaser = f"{emoji} {cfg.display_name} · {aud} · {topic.get('cifra_ancla', '')}"

    for name, poster_mod, icon in [
        ("bluesky", "videogen.bluesky_poster", "🦋"),
        ("mastodon", "videogen.mastodon_poster", "🐘"),
        ("threads", "videogen.threads_poster", "🧵"),
    ]:
        try:
            import importlib
            mod = importlib.import_module(poster_mod)
            fn = getattr(mod, f"post_short_to_{name}")
            r = fn(title, url, teaser=teaser)
            result[icon] = bool(r)
        except Exception as e:
            print(f"  {cfg.slug} {name} fail: {e}")
            result[icon] = False
    return result


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


def _build_longform_topic_prompt(cfg: ChannelConfig, t: dict) -> str:
    """Topic para long-form (~7 min). Amplía scope: 1 tema profundo con
    subcasos/ejemplos, no lista superficial. Se acompaña de mismo prompt
    del nicho (via SCRIPT_SYSTEM_PROMPT_FILE)."""
    aud = t.get("audiencia", "")
    cat = t.get("categoria", "")
    hook = t.get("hook", "")
    cifra = t.get("cifra_ancla", "")
    return (
        f"[LONG-FORM · Canal {cfg.display_name} · audiencia={aud} · categoria={cat}] "
        f"Tema: {t['titulo']}. Amplía a explicación profunda ~7 min con 3-5 capítulos: "
        f"contexto histórico + normativa vigente + casos reales + implicaciones prácticas + "
        f"conclusión con recomendaciones. "
        f"Hook central: {hook}. Cifra clave: {cifra}. "
        f"El title formato: '[Tema completo] EXPLICADO en 7 minutos · [dato clave]'. "
        f"Cierre obligatorio: 'Consulta con un profesional tu caso. Sígueme para más.'"
    )


def run_channel_longform_once(cfg: ChannelConfig, target_minutes: int = 7) -> dict[str, Any]:
    """Genera + sube 1 LONG-FORM (~7 min, 16:9) del canal `cfg`.

    NO cross-postea a RRSS (long-forms funcionan mejor por playlist YT
    + descripción SEO que por teaser social — decisión de diseño).
    """
    from . import service

    topic = _pick_topic(cfg)
    if not topic:
        return {"status": "no_topic"}

    topic_prompt = _build_longform_topic_prompt(cfg, topic)
    print(f"  {cfg.slug}-long: topic={topic['key']}")
    print(f"  {cfg.slug}-long: prefix={cfg.yt_prefix} · "
          f"has_refresh={bool(os.environ.get(cfg.yt_prefix + '_REFRESH_TOKEN'))}")

    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = cfg.system_prompt_file
    os.environ["YT_CHANNEL_PREFIX"] = cfg.yt_prefix
    voice_env = f"KOKORO_VOICE_ES_{cfg.yt_prefix[3:]}"
    if not os.environ.get(voice_env):
        os.environ[voice_env] = cfg.kokoro_voice_es

    _notify(f"{cfg.audience_emoji.get('_', '💼')} <b>{cfg.display_name} · long-form arrancando</b>\n"
            f"<i>{topic['titulo'][:80]}</i>")

    try:
        slug = service.generate_long(topic_prompt, target_minutes=target_minutes,
                                       langs=("es",),
                                       progress=lambda m: print(f"  {m}"))
        print(f"  {cfg.slug}-long: subiendo al canal {cfg.display_name}…")
        links = service.publish_long(slug, ("es",), privacy="public",
                                       progress=lambda m: print(f"  {m}"), notify=False)
        _mark_used(ROOT / "output" / cfg.ledger_filename, topic["key"] + "_LONG")
        url = links.get("es", "?")
        _notify(f"✅ <b>{cfg.display_name} · long-form</b>\n"
                f"slug: <code>{slug}</code>\n{url}")
        return {"status": "ok", "slug": slug, "url": url,
                "topic_key": topic["key"], "kind": "long"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _notify(f"❌ {cfg.display_name} long-form falló: {type(e).__name__}: {str(e)[:200]}")
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
        os.environ.pop("YT_CHANNEL_PREFIX", None)


def run_channel_once(cfg: ChannelConfig) -> dict[str, Any]:
    """Genera + sube + crosspostea 1 short del canal `cfg`."""
    from . import service

    topic = _pick_topic(cfg)
    if not topic:
        return {"status": "no_topic"}

    topic_prompt = _build_topic_prompt(cfg, topic)
    print(f"  {cfg.slug}: topic={topic['key']} audiencia={topic.get('audiencia','')}")
    print(f"  {cfg.slug}: prefix={cfg.yt_prefix} · voice_key=KOKORO_VOICE_ES_{cfg.yt_prefix[3:]} · "
          f"has_refresh={bool(os.environ.get(cfg.yt_prefix + '_REFRESH_TOKEN'))}")

    # Env overrides per-channel
    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = cfg.system_prompt_file
    os.environ["YT_CHANNEL_PREFIX"] = cfg.yt_prefix
    voice_env = f"KOKORO_VOICE_ES_{cfg.yt_prefix[3:]}"  # YT_TAX → TAX
    if not os.environ.get(voice_env):
        os.environ[voice_env] = cfg.kokoro_voice_es

    _notify(f"{cfg.audience_emoji.get('_', '💼')} <b>{cfg.display_name} arrancando</b>\n"
            f"<i>{topic['titulo'][:80]}</i>")

    try:
        slug = service.generate(topic_prompt, ("es",),
                                 lambda m: print(f"  {m}"), ai_hero=True)
        print(f"  {cfg.slug}: subiendo al canal {cfg.display_name}…")
        links = service.publish(slug, ("es",), privacy="public",
                                 progress=lambda m: print(f"  {m}"), notify=False)
        _mark_used(ROOT / "output" / cfg.ledger_filename, topic["key"])
        url = links.get("es", "?")
        cross = _crosspost(cfg, slug, url, topic)
        cross_summary = " · ".join(f"{k}{'✅' if v else '❌'}" for k, v in cross.items())
        _notify(f"✅ <b>{cfg.display_name}</b>\nslug: <code>{slug}</code>\n"
                f"{url}\n\nRRSS: {cross_summary}")
        return {"status": "ok", "slug": slug, "url": url,
                "topic_key": topic["key"], "crosspost": cross}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _notify(f"❌ {cfg.display_name} falló: {type(e).__name__}: {str(e)[:200]}")
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        # Limpia env para no contaminar procesos concurrentes
        os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
        os.environ.pop("YT_CHANNEL_PREFIX", None)
