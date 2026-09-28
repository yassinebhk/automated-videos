"""Post diario Bluesky "dato + fuente" (2º canal de valor, complementa crosspost).

Por qué:
- Bluesky es la única RRSS que rinde (3-8 replies/día + 3 follows/día orgánicos).
- Los crossposts de vídeo ya se hacen (uno por vídeo). Este es un POST EXTRA
  1×/día, formato distinto: dato citable + fuente pública, sin link al vídeo.
- Feed algorítmico de Bsky premia hilos con datos verificables; los usuarios
  hacen quote/repost si el dato es interesante. Objetivo: reach orgánico sin
  parecer bot promocional.

Anti-spam / anti-baneo:
- 1 post/día (más y Bsky lo detectaría como bot volumen).
- Templates rotativos por ledger (nunca 2× el mismo dato en 30 días).
- Cero mención al canal ni link salvo 1 de cada 5 (proporción baja).
- Solo datos verificables con sentencia/fuente pública (política veracidad).

Cron: piggyback catchup-all-channels 4×/día → primer pase del día publica,
resto skip por cap diario.
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from .config import ROOT

LEDGER = ROOT / "output" / "bsky_daily_fact_ledger.json"
LEDGER_MAX = 200
COOLDOWN_DAYS = 30  # no repetir mismo dato dentro de 30 días

# Datos concretos + fuente. Cada uno se rota; el ledger evita repetición.
# Formato: dato (impactante, cifra), fuente (sentencia/organismo citable).
_FACTS = [
    {"text": "Caso Malaya (Marbella) — trama urbanística de 2.400M€, más de 90 condenados. Sent. TS 508/2021.",
     "hashtags": ["#corrupción", "#trueCrime"]},
    {"text": "Caso Gürtel — 41 años de cárcel para Correa. Sentencia AN 20/2018 (2ª sec. Sala Penal).",
     "hashtags": ["#corrupción", "#Gürtel"]},
    {"text": "Caso Bárcenas — 47M€ ocultos en cuentas suizas. Sentencia TS 507/2020.",
     "hashtags": ["#corrupción", "#casoBárcenas"]},
    {"text": "Caso Erial (Zaplana) — 20,6M€ ocultos en paraísos fiscales. Sent. AN oct. 2024.",
     "hashtags": ["#corrupción", "#Zaplana"]},
    {"text": "Caso KIO (banca) — 300M€ desviados. Sent. AN 3/2000, ratificada TS.",
     "hashtags": ["#corrupción", "#estafas"]},
    {"text": "Caso Nóos (Iñaki Urdangarin) — 5 años 10 meses de cárcel. Sent. AP Baleares feb 2017.",
     "hashtags": ["#corrupción", "#casoNóos"]},
    {"text": "Caso ERE Andalucía — 680M€ mal usados durante ~10 años. Sent. TS 749/2022.",
     "hashtags": ["#corrupción", "#ERE"]},
    {"text": "Caso Púnica — 250 imputados, gasto público inflado en obras. Sumario JCI 6 AN.",
     "hashtags": ["#corrupción", "#Púnica"]},
    {"text": "Caso Palau (Millet) — 34,8M€ desviados de la Fundació Orfeó Català. Sent. AP BCN 2018.",
     "hashtags": ["#corrupción", "#casoPalau"]},
    {"text": "Caso Filesa (financiación PSOE años 90) — 1.100M pta. Sent. TS 1/1997, primera de este tipo.",
     "hashtags": ["#corrupción", "#Filesa"]},
    {"text": "Caso Faisán (chivatazo ETA) — 1º agente condenado a 5 años. Sent. AN 71/2011.",
     "hashtags": ["#trueCrime", "#Faisán"]},
    {"text": "Operación Lezo (Ignacio González) — 30M€ presunto desvío Canal de Isabel II. Sumario 2017.",
     "hashtags": ["#corrupción", "#operaciónLezo"]},
    {"text": "Caso Bankia — 300.000 accionistas afectados, 3.100M€ salida a bolsa. Sent. AN 508/2020.",
     "hashtags": ["#corrupción", "#casoBankia"]},
    {"text": "Caso Koldo (mascarillas) — 20M€ presunto sobrecoste pandemia. Sumario JCI 2 AN 2024.",
     "hashtags": ["#corrupción", "#casoKoldo"]},
    {"text": "Caso Naseiro (1990) — primer gran caso corrupción PP, escuchas anuladas. Sent. TS 1994.",
     "hashtags": ["#corrupción", "#casoNaseiro"]},
]

_CANAL_TAG = "\n\n(Toco casos así en @waitwhy_)"
CANAL_TAG_FREQ = 5  # 1 de cada N incluye tag canal


def _load_ledger() -> dict:
    if not LEDGER.exists():
        return {"posted": [], "last_run": None}
    try:
        d = json.loads(LEDGER.read_text(encoding="utf-8"))
        d.setdefault("posted", [])
        return d
    except Exception:
        return {"posted": [], "last_run": None}


def _save_ledger(data: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    if len(data.get("posted", [])) > LEDGER_MAX:
        data["posted"] = data["posted"][-LEDGER_MAX:]
    LEDGER.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _client():
    from atproto import Client
    handle = os.environ.get("BLUESKY_HANDLE")
    pw = os.environ.get("BLUESKY_APP_PASSWORD")
    if not (handle and pw):
        return None
    c = Client()
    c.login(handle, pw)
    return c


def _already_posted_today(ledger: dict) -> bool:
    today = datetime.now(timezone.utc).date().isoformat()
    for entry in ledger.get("posted", []):
        if entry.get("date") == today:
            return True
    return False


def _pick_fact(ledger: dict) -> Optional[dict]:
    """Escoge dato aleatorio no usado en últimos COOLDOWN_DAYS días."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=COOLDOWN_DAYS)).date().isoformat()
    used = {e["fact_id"] for e in ledger.get("posted", []) if e.get("date", "") >= cutoff}
    pool = [i for i in range(len(_FACTS)) if i not in used]
    if not pool:
        # Todo agotado en 30 días → reseteamos y usamos cualquiera
        pool = list(range(len(_FACTS)))
    idx = random.choice(pool)
    return {"idx": idx, **_FACTS[idx]}


def _compose(fact: dict, include_tag: bool) -> str:
    tags = " ".join(fact.get("hashtags") or [])
    body = fact["text"]
    tail = _CANAL_TAG if include_tag else ""
    txt = f"{body}\n\n{tags}{tail}".strip()
    return txt[:290]  # margen bajo el límite Bsky (300)


def run_bsky_daily_fact(dry_run: bool = False) -> dict:
    ledger = _load_ledger()
    ledger["last_run"] = datetime.now(timezone.utc).isoformat()
    if not dry_run:
        try:
            _save_ledger(ledger)
        except Exception as e:
            print(f"  bsky-fact: save early ledger fail {e}")

    try:
        return _run_impl(dry_run, ledger)
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": f"crash: {type(e).__name__}: {str(e)[:200]}",
                "last_run": ledger["last_run"]}


def _run_impl(dry_run: bool, ledger: dict) -> dict:
    if _already_posted_today(ledger):
        return {"skipped": "already posted today", "last_run": ledger["last_run"]}

    fact = _pick_fact(ledger)
    if not fact:
        return {"error": "no facts left", "last_run": ledger["last_run"]}

    include_tag = (random.randint(1, CANAL_TAG_FREQ) == 1)
    text = _compose(fact, include_tag)

    if dry_run:
        print(f"  bsky-fact DRY → «{text}»")
        return {"dry_run": True, "text": text, "fact_id": fact["idx"]}

    c = _client()
    if not c:
        return {"error": "no BLUESKY_HANDLE/BLUESKY_APP_PASSWORD",
                "last_run": ledger["last_run"]}
    try:
        c.send_post(text)
    except Exception as e:
        return {"error": f"post fail: {e}", "last_run": ledger["last_run"]}

    today = datetime.now(timezone.utc).date().isoformat()
    ledger["posted"].append({
        "date": today, "fact_id": fact["idx"], "with_tag": include_tag,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    _save_ledger(ledger)

    try:
        from . import notify_batch
        notify_batch.add(
            f"🦋 <b>Bsky fact diario</b>: «{fact['text'][:80]}...» "
            f"(canal tag: {'sí' if include_tag else 'no'})"
        )
    except Exception:
        pass

    return {"posted": True, "fact_id": fact["idx"], "with_tag": include_tag,
            "text": text}
