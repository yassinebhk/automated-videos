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
    edge_voice_es: str = "es-ES-AlvaroNeural"  # Edge TTS neural (default masculino ES)
    audience_emoji: dict = field(default_factory=lambda: {})  # {'autonomos': '👔', …}
    series_name: str = "Serie"       # 'TaxHack ES', 'TusDerechos ES'
    cooldown_days: int = 90
    # Pool long-form específico (opcional). Si no está, long usa el short pool.
    topic_pool_long_module: str = ""  # ej 'videogen.tax.topic_pool_long'
    # Canal HOST fallback si el propio yt_prefix no tiene _REFRESH_TOKEN
    # configurado. Ej: criminopatia → "" (WaitWhy default), trabajos → "YT_LEGAL".
    # Sin fallback (""), el pipeline skip YT y sigue con IG+TT como antes.
    host_yt_prefix_fallback: str = ""


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


def _pick_topic(cfg: ChannelConfig, kind: str = "short") -> dict | None:
    """Elige topic del pool no usado en cooldown. Rota por audiencia.
    Mergea pool estático + topics dinámicos (auto-refresh según tendencias).

    kind='short' → topic_pool_module (30 topics + dyn)
    kind='long'  → topic_pool_long_module si existe (10 topics + dyn),
                   fallback al short pool.
    """
    import importlib
    if kind == "long" and cfg.topic_pool_long_module:
        pool_module = cfg.topic_pool_long_module
    else:
        pool_module = cfg.topic_pool_module
    mod = importlib.import_module(pool_module)
    static_pool = mod.all_topics()
    # Merge con topics dinámicos (auto-refresh según tendencias)
    try:
        from . import topic_refresher
        all_t = topic_refresher.get_all_topics_merged(static_pool, cfg.slug, kind=kind)
    except Exception as e:
        print(f"  {cfg.slug}-{kind}: dynamic topics fail ({e}), usando estáticos")
        all_t = static_pool
    ledger_path = ROOT / "output" / cfg.ledger_filename
    # Ledger key para long usa sufijo _LONG (evita solapar con short)
    def _key(t):
        return t["key"] + ("_LONG" if kind == "long" else "")
    fresh = [t for t in all_t if not _recently_used(ledger_path, _key(t), cfg.cooldown_days)]
    if not fresh:
        fresh = all_t
    # Anti-repeat SEMÁNTICO: descarta topics cuyo `titulo` se parezca a algo YA
    # publicado (no solo por key). Cubre el hueco que dejaba repetir el mismo
    # tema con otra key o generado por el refresher dinámico.
    try:
        from . import dedup_common
        pk = dedup_common.platform_key_for_prefix(cfg.yt_prefix)
        recents = dedup_common.recent_titles_from_history(pk, days=max(cfg.cooldown_days, 120))
        if recents:
            fresh2 = [t for t in fresh
                      if not dedup_common.title_is_repeat(t.get("titulo") or t.get("key", ""), recents)]
            dropped = len(fresh) - len(fresh2)
            if fresh2:
                if dropped:
                    print(f"  {cfg.slug}-{kind}: anti-repeat descartó {dropped} topics ya cubiertos")
                fresh = fresh2
    except Exception as e:
        print(f"  {cfg.slug}-{kind}: dedup título skip ({e})")
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


def _avoid_block(cfg: ChannelConfig, n: int = 25) -> str:
    """Bloque 'NO repitas' con títulos ya publicados del canal (anti-repeat)."""
    try:
        from . import dedup_common
        pk = dedup_common.platform_key_for_prefix(cfg.yt_prefix)
        block = dedup_common.recent_titles_block(pk, days=150, n=n)
        if block:
            return (f" ⛔ PROHIBIDO repetir o parecerse a estos temas YA PUBLICADOS "
                    f"en el canal: {block}. Elige un ÁNGULO y TÍTULO claramente DISTINTO; "
                    f"si el tema roza uno de esos, cámbialo por otro.")
    except Exception:
        pass
    return ""


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
        + _avoid_block(cfg)
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
    """Cross-post RRSS con marca del nicho (emoji audiencia + cifra).

    url puede ser vacía si el canal aún no tiene YT (subimos solo a IG
    que no requiere URL, y skip BS/MA/TH que sí la necesitan)."""
    result: dict[str, bool] = {}
    title = _load_video_title(slug) or topic.get("titulo", "")
    if not title:
        return result

    aud = topic.get("audiencia", "")
    emoji = cfg.audience_emoji.get(aud, "📺")
    teaser = f"{emoji} {cfg.display_name} · {aud} · {topic.get('cifra_ancla', '')}"

    # BS/MA/TH SÍ requieren URL — skip si vacía
    if url and url != "?":
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

    # Instagram Reels — SOLO whitelist true crime ES (fix 21/09 tras
    # deep research: cuenta @waitwhy_ perdía -40-80% reach por mezcla).
    from .crosspost_full import _ig_allowed
    if not _ig_allowed(cfg.slug):
        print(f"  {cfg.slug} ig: SKIP (no en whitelist true crime ES)")
        result["📸"] = False
    else:
        try:
            from .config import UPLOADED_DIR, PENDING_DIR
            from . import instagram_poster
            mp4 = None
            for base in (UPLOADED_DIR, PENDING_DIR):
                p = base / slug / "video_es_vertical.mp4"
                if p.exists():
                    mp4 = p
                    break
            if mp4:
                r = instagram_poster.post_reel_to_instagram(
                    title, url, mp4, slug, teaser=teaser,
                )
                result["📸"] = bool(r)
            else:
                print(f"  {cfg.slug} ig: no mp4 encontrado para {slug}")
                result["📸"] = False
        except Exception as e:
            print(f"  {cfg.slug} ig fail: {e}")
            result["📸"] = False

    return result


def _notify(text: str, urgent: bool = False) -> None:
    """Encola notificación (batched al final del proceso).
    urgent=True → envía inmediatamente (fallos críticos)."""
    from .notify_batch import add
    add(text, urgent=urgent)


def _send_tt_video(cfg: ChannelConfig, slug: str, title: str, url: str) -> None:
    """Envía MP4 vertical del Short a Telegram → descarga manual → TikTok.

    Workaround: subir a draft TT vía API sigue sin funcionar por review
    de Sandbox → mandamos el MP4 y el user lo sube manual en 30s."""
    try:
        from .config import UPLOADED_DIR, PENDING_DIR
        from .notify_batch import send_video_for_tiktok
        mp4 = None
        for base in (UPLOADED_DIR, PENDING_DIR):
            p = base / slug / "video_es_vertical.mp4"
            if p.exists():
                mp4 = p
                break
        if mp4:
            send_video_for_tiktok(mp4, cfg.display_name, title, url)
    except Exception as e:
        print(f"  {cfg.slug}: TT tg video fail — {e}")


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
        + _avoid_block(cfg)
    )


def run_channel_longform_once(cfg: ChannelConfig, target_minutes: int = 7) -> dict[str, Any]:
    """Genera + sube 1 LONG-FORM (~7 min, 16:9) del canal `cfg`.

    NO cross-postea a RRSS (long-forms funcionan mejor por playlist YT
    + descripción SEO que por teaser social — decisión de diseño).
    """
    from . import service

    topic = _pick_topic(cfg, kind="long")
    if not topic:
        return {"status": "no_topic"}

    topic_prompt = _build_longform_topic_prompt(cfg, topic)
    print(f"  {cfg.slug}-long: topic={topic['key']}")
    print(f"  {cfg.slug}-long: prefix={cfg.yt_prefix} · "
          f"has_refresh={bool(os.environ.get(cfg.yt_prefix + '_REFRESH_TOKEN'))}")

    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = cfg.system_prompt_file
    os.environ["YT_CHANNEL_PREFIX"] = cfg.yt_prefix
    kk_env = f"KOKORO_VOICE_ES_{cfg.yt_prefix[3:]}"
    if not os.environ.get(kk_env):
        os.environ[kk_env] = cfg.kokoro_voice_es
    edge_env = f"EDGE_VOICE_ES_{cfg.yt_prefix[3:]}"
    if not os.environ.get(edge_env):
        os.environ[edge_env] = cfg.edge_voice_es

    # Sin notif previa (reduce ruido). Solo notifica al terminar.
    try:
        slug = service.generate_long(topic_prompt, target_minutes=target_minutes,
                                       langs=("es",),
                                       progress=lambda m: print(f"  {m}"))
        print(f"  {cfg.slug}-long: subiendo al canal {cfg.display_name}…")
        links = service.publish_long(slug, ("es",), privacy="public",
                                       progress=lambda m: print(f"  {m}"), notify=False)
        # Ledger key con sufijo _LONG para NO colisionar con dedup shorts
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
    """Genera + sube + crosspostea 1 short del canal `cfg`.

    14/09/26: prioridad SCRIPT CACHE (script_cache.pop_cached_script).
    Si hay uno pre-generado a las 03:37 UTC, se usa (0 llamadas LLM).
    Si no, cae a generación en tiempo real como safety net.
    """
    from . import service
    from . import script_cache

    # Prioridad 1: script pre-cacheado (evita rate limit LLM en runtime)
    cached = script_cache.pop_cached_script(cfg.yt_prefix)
    if cached:
        cached_topic_key, cached_scripts = cached
        # Reconstruye "topic" dict desde el key para _mark_used + notif
        import importlib
        pool_mod = importlib.import_module(cfg.topic_pool_module)
        topic = None
        for t in pool_mod.all_topics():
            if t.get("key") == cached_topic_key:
                topic = t
                break
        if not topic:
            topic = {"key": cached_topic_key, "titulo": cached_topic_key.replace("_", " "),
                     "audiencia": "general"}
        topic_prompt = _build_topic_prompt(cfg, topic)
        print(f"  {cfg.slug}: 🍱 CACHE HIT topic={cached_topic_key} (skip LLM)")
    else:
        topic = _pick_topic(cfg)
        if not topic:
            return {"status": "no_topic"}
        topic_prompt = _build_topic_prompt(cfg, topic)
        cached_scripts = None
        print(f"  {cfg.slug}: cache vacío → generación runtime")
    print(f"  {cfg.slug}: topic={topic['key']} audiencia={topic.get('audiencia','')}")
    print(f"  {cfg.slug}: prefix={cfg.yt_prefix} · voice_key=KOKORO_VOICE_ES_{cfg.yt_prefix[3:]} · "
          f"has_refresh={bool(os.environ.get(cfg.yt_prefix + '_REFRESH_TOKEN'))}")

    # Env overrides per-channel
    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = cfg.system_prompt_file
    os.environ["YT_CHANNEL_PREFIX"] = cfg.yt_prefix
    kk_env = f"KOKORO_VOICE_ES_{cfg.yt_prefix[3:]}"
    if not os.environ.get(kk_env):
        os.environ[kk_env] = cfg.kokoro_voice_es
    edge_env = f"EDGE_VOICE_ES_{cfg.yt_prefix[3:]}"
    if not os.environ.get(edge_env):
        os.environ[edge_env] = cfg.edge_voice_es

    # Sin notif "arrancando" — reduce ruido Telegram. Solo notifica al terminar
    # (éxito o error). Toda la actividad se consolida en daily summary.

    try:
        slug = service.generate(topic_prompt, ("es",),
                                 lambda m: print(f"  {m}"), ai_hero=True,
                                 precached_scripts=cached_scripts)
        # YT-upload con fallback host: si no hay secret YT_{prefix}_REFRESH_TOKEN,
        # usa host_yt_prefix_fallback (canal afín donde subir mientras se crea
        # el canal propio). Sin fallback → skip YT y sigue con IG+TT.
        has_own = bool(os.environ.get(cfg.yt_prefix + "_REFRESH_TOKEN"))
        host_prefix = cfg.yt_prefix if has_own else cfg.host_yt_prefix_fallback
        # host_prefix == "" es válido → creds default (WaitWhy)
        if not has_own and host_prefix == "":
            has_host_creds = bool(os.environ.get("YT_REFRESH_TOKEN"))
        elif not has_own:
            has_host_creds = bool(os.environ.get(host_prefix + "_REFRESH_TOKEN"))
        else:
            has_host_creds = True

        url = ""
        yt_status = "skip_no_creds"
        if has_host_creds:
            try:
                host_note = "" if has_own else f" (host: {host_prefix or 'WaitWhy default'})"
                print(f"  {cfg.slug}: subiendo al canal {cfg.display_name}{host_note}…")
                # Sobreescribir env prefix para que upload use el host
                _prev_prefix = os.environ.get("YT_CHANNEL_PREFIX", "")
                os.environ["YT_CHANNEL_PREFIX"] = host_prefix
                try:
                    links = service.publish(slug, ("es",), privacy="public",
                                             progress=lambda m: print(f"  {m}"), notify=False)
                    url = links.get("es", "?")
                    yt_status = "ok" if has_own else f"ok-host-{host_prefix or 'YT_WAITWHY'}"
                finally:
                    if _prev_prefix:
                        os.environ["YT_CHANNEL_PREFIX"] = _prev_prefix
                    else:
                        os.environ.pop("YT_CHANNEL_PREFIX", None)
            except Exception as e:
                print(f"  {cfg.slug}: YT upload falló ({type(e).__name__}): sigue con IG+TT")
                yt_status = f"fail: {type(e).__name__}"
        else:
            print(f"  {cfg.slug}: sin YT creds (propias ni host) → skip YT, sube directo a IG+TT")

        _mark_used(ROOT / "output" / cfg.ledger_filename, topic["key"])
        cross = _crosspost(cfg, slug, url, topic)
        cross_summary = " · ".join(f"{k}{'✅' if v else '❌'}" for k, v in cross.items())
        yt_line = f"YT: {url}" if url and url != "?" else f"YT {yt_status}"
        _notify(f"✅ <b>{cfg.display_name}</b> · {yt_line}\n"
                f"<i>{topic.get('titulo','')[:60]}</i> · RRSS {cross_summary}")
        # Envía MP4 vertical a Telegram para descarga manual → TikTok
        _send_tt_video(cfg, slug, topic.get("titulo", ""), url)
        return {"status": "ok", "slug": slug, "url": url,
                "topic_key": topic["key"], "crosspost": cross, "yt_status": yt_status}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _notify(f"❌ {cfg.display_name} falló: {type(e).__name__}: {str(e)[:200]}",
                 urgent=True)
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        # Limpia env para no contaminar procesos concurrentes
        os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
        os.environ.pop("YT_CHANNEL_PREFIX", None)
