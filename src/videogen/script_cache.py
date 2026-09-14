"""Pre-cache de scripts generados con LLM — evita rate limits en runtime.

Estrategia: en horas de baja demanda global (03:37 UTC), genera scripts
para todos los canales configurados y los guarda en disk. Cuando el
cron de publicación dispara, coge un script del cache en vez de llamar
a Gemini/OpenRouter/Groq.

Ventajas:
  - 0 llamadas LLM en runtime → cero riesgo 429 durante publicación
  - Cuota LLM concentrada en 1 hora del día cuando Gemini está fresco
  - Fallback: si cache vacío, cae a generación en tiempo real (safety net)

Estructura disk:
  output/script_cache/{yt_prefix}/{topic_key}__{timestamp}.json  ← pending
  output/script_cache/{yt_prefix}/_used/                          ← consumido

Los scripts consumidos se archivan (no se borran) para debug/re-uso.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT
from .models import GeneratedScripts

CACHE_ROOT = ROOT / "output" / "script_cache"


def _cache_dir(yt_prefix: str) -> Path:
    """Dir por canal. WaitWhy (sin prefix) usa '_main'."""
    slug = yt_prefix or "_main"
    d = CACHE_ROOT / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_script(yt_prefix: str, topic_key: str, scripts: GeneratedScripts) -> Path:
    """Guarda un script generado en el cache del canal."""
    d = _cache_dir(yt_prefix)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    p = d / f"{topic_key}__{ts}.json"
    p.write_text(scripts.model_dump_json(indent=2), encoding="utf-8")
    return p


def pop_cached_script(yt_prefix: str) -> tuple[str, GeneratedScripts] | None:
    """Coge el script MÁS ANTIGUO del cache (FIFO) y lo marca como usado.

    Devuelve (topic_key, scripts) o None si cache vacío.
    """
    d = _cache_dir(yt_prefix)
    pending = sorted(
        [p for p in d.glob("*.json") if not p.name.startswith("_")],
        key=lambda x: x.stat().st_mtime,
    )
    if not pending:
        return None
    chosen = pending[0]
    try:
        raw = json.loads(chosen.read_text(encoding="utf-8"))
        scripts = GeneratedScripts.model_validate(raw)
    except Exception as e:
        print(f"  cache: script corrupto {chosen.name}: {e}, borrando")
        chosen.unlink(missing_ok=True)
        return None
    topic_key = chosen.stem.split("__")[0]

    # Mueve a _used/ para archivo (no borrado, para debug)
    used_dir = d / "_used"
    used_dir.mkdir(exist_ok=True)
    try:
        chosen.rename(used_dir / chosen.name)
    except Exception:
        chosen.unlink(missing_ok=True)

    print(f"  cache: ✅ script cacheado consumido — {topic_key}")
    return topic_key, scripts


def cache_stats() -> dict[str, int]:
    """{yt_prefix: count_pending}"""
    stats = {}
    if not CACHE_ROOT.exists():
        return stats
    for d in CACHE_ROOT.iterdir():
        if d.is_dir():
            n = sum(1 for p in d.glob("*.json") if not p.name.startswith("_"))
            stats[d.name] = n
    return stats


def precache_scripts_for_channel(cfg: Any, n: int = 3) -> dict[str, Any]:
    """Genera hasta N scripts nuevos para el canal `cfg` y los cachea.
    Reusa el flujo `script.generate_scripts` con topic pickeado del pool
    respetando cooldown. NO sube nada — solo genera y guarda.
    """
    import importlib
    from . import script as script_mod
    from .channel_pipeline import _pick_topic, _build_topic_prompt

    generated: list[str] = []
    failures: list[str] = []
    for i in range(n):
        try:
            topic = _pick_topic(cfg)
            if not topic:
                failures.append("no_topic")
                break
            topic_prompt = _build_topic_prompt(cfg, topic)
            # Setup env override for script.generate_scripts to use canal prompt
            import os
            prev_sys = os.environ.get("SCRIPT_SYSTEM_PROMPT_FILE", "")
            os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = cfg.system_prompt_file
            try:
                scripts = script_mod.generate_scripts(topic_prompt)
            finally:
                if prev_sys:
                    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = prev_sys
                else:
                    os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
            p = cache_script(cfg.yt_prefix, topic["key"], scripts)
            generated.append(f"{topic['key']} → {p.name}")
            print(f"  [{cfg.slug}] cache #{i+1}/{n}: {topic['key']}")
        except Exception as e:
            failures.append(f"{type(e).__name__}: {str(e)[:80]}")
            print(f"  [{cfg.slug}] cache #{i+1} fail: {e}")

    return {"channel": cfg.slug, "generated": generated,
             "failures": failures}


def precache_all(n_per_channel: int = 3) -> dict[str, Any]:
    """Pre-cache scripts para TODOS los canales blue-ocean.

    Corre en cron 03:37 UTC. Genera N scripts para cada canal.
    En cada channel_pipeline.run_channel_once, primero intenta cache.
    """
    from .notify_batch import add
    from .tax.pipeline import CONFIG as TAX_CFG
    from .legal.pipeline import CONFIG as LEGAL_CFG
    from .ayudas.pipeline import CONFIG as AYUDAS_CFG
    from .motor.pipeline import CONFIG as MOTOR_CFG
    from .pov.pipeline import CONFIG as POV_CFG
    from .ia_autonomos.pipeline import CONFIG as IA_CFG

    all_cfgs = [TAX_CFG, LEGAL_CFG, AYUDAS_CFG, MOTOR_CFG, POV_CFG, IA_CFG]
    summary = []
    for cfg in all_cfgs:
        r = precache_scripts_for_channel(cfg, n=n_per_channel)
        summary.append(r)

    lines = ["🍱 <b>Pre-cache scripts diario</b>"]
    for r in summary:
        gen = len(r["generated"])
        fail = len(r["failures"])
        icon = "✅" if gen > 0 else "⚠️"
        lines.append(f"  {icon} {r['channel']}: {gen} generados · {fail} fallos")
    stats = cache_stats()
    total = sum(stats.values())
    lines.append(f"\n📦 Cache total: {total} scripts listos")
    add("\n".join(lines))

    return {"summary": summary, "cache_stats": stats}
