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
from . import topic_pool

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


def run_once() -> dict[str, Any]:
    """Genera + sube 1 short fiscal al canal TaxHack."""
    from .. import service

    topic = _pick_topic()
    if not topic:
        return {"status": "no_topic"}

    topic_prompt = _build_topic_prompt(topic)
    print(f"  tax: topic={topic['key']} audiencia={topic['audiencia']}")

    # Env overrides: prompt fiscal + canal YT separado
    os.environ["SCRIPT_SYSTEM_PROMPT_FILE"] = "tax_system.md"
    os.environ["YT_CHANNEL_PREFIX"] = "YT_TAX"

    _notify(f"💶 <b>Tax short arrancando</b>\n<i>{topic['titulo'][:80]}</i>")

    try:
        slug = service.generate(topic_prompt, ("es",), lambda m: print(f"  {m}"),
                                 ai_hero=True)
        _mark_used(topic["key"])
        _notify(f"✅ <b>Tax short publicado</b>\nslug: <code>{slug}</code>")
        return {"status": "ok", "slug": slug, "topic_key": topic["key"]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _notify(f"❌ Tax short falló: {type(e).__name__}: {str(e)[:200]}")
        return {"status": "gen_fail", "error": str(e), "topic_key": topic["key"]}
    finally:
        # Limpia env para no contaminar procesos concurrentes en mismo runner
        os.environ.pop("SCRIPT_SYSTEM_PROMPT_FILE", None)
        os.environ.pop("YT_CHANNEL_PREFIX", None)


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
