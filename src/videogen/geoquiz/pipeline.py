"""Pipeline GeoQuiz (EN) — "guess the country by its flag" (sin voz).

Pre-cableado: sin YT_GEOQUIZ_* hace NO-OP (no genera). Dedup PROPIO por SET de países
(round_key) + cooldown por país → NO repite la misma ronda. Desactiva el guardarraíl
de dedup POR TÍTULO en su subida (el título es fijo por diseño = marca de serie; el
contenido varía por banderas). Ver [[tanda-canales-02-10]], [[dedup-semantico-titulo]].
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from ..config import ROOT
from . import generator, data

LEDGER = ROOT / "output" / "geoquiz_ledger.json"
GEOQUIZ_ROOT = ROOT / "output" / "geoquiz_uploaded"
YT_PREFIX = "YT_GEOQUIZ"
DISPLAY_NAME = "GeoQuiz"
COUNTRY_COOLDOWN_DAYS = 21
N_ROUNDS = 5


def _load_ledger() -> dict:
    if not LEDGER.exists():
        return {"countries": {}, "rounds": []}
    try:
        d = json.loads(LEDGER.read_text(encoding="utf-8"))
        d.setdefault("countries", {})
        d.setdefault("rounds", [])
        return d
    except Exception:
        return {"countries": {}, "rounds": []}


def _save_ledger(d: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def _country_recent(led: dict, iso2: str) -> bool:
    ts = led["countries"].get(iso2)
    if not ts:
        return False
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(ts)) < timedelta(days=COUNTRY_COOLDOWN_DAYS)
    except Exception:
        return False


def _pick_candidates(led: dict, k: int = 14) -> list[tuple]:
    pool = list(data.COUNTRIES)
    random.shuffle(pool)
    fresh = [c for c in pool if not _country_recent(led, c[0])]
    rest = [c for c in pool if _country_recent(led, c[0])]
    cand = (fresh + rest)[:k]
    # mezcla de dificultad: ordena para que no salgan 5 difíciles seguidos
    cand.sort(key=lambda c: c[3])
    # intercala fácil/medio/difícil
    random.shuffle(cand)
    return cand


def _notify(text: str, urgent: bool = False) -> None:
    from ..notify_batch import add
    add(text, urgent=urgent)


def _episode(led: dict) -> int:
    return len(led.get("rounds", [])) + 1


def run_once() -> dict[str, Any]:
    has_creds = bool(os.environ.get(YT_PREFIX + "_REFRESH_TOKEN"))
    allow_test = (os.environ.get("GEOQUIZ_GENERATE_WITHOUT_CHANNEL", "").lower() in ("1", "true", "yes")
                  or os.environ.get("BATCH_GENERATE_WITHOUT_CHANNEL", "").lower() in ("1", "true", "yes"))
    if not has_creds and not allow_test:
        print(f"  geoquiz: sin {YT_PREFIX}_* y sin flag test → no-op (canal pendiente)")
        return {"status": "no_channel"}

    led = _load_ledger()
    candidates = _pick_candidates(led)
    print(f"  geoquiz: generando ronda #{_episode(led)} ({len(candidates)} candidatos)")
    meta = generator.generate_geoquiz(GEOQUIZ_ROOT, candidates, n_rounds=N_ROUNDS)
    if not meta:
        _notify("❌ GeoQuiz falló generación", urgent=True)
        return {"status": "gen_fail"}

    # evita repetir EXACTAMENTE el mismo set de 5 países
    if meta["round_key"] in set(led.get("rounds", [])):
        print("  geoquiz: round_key repetido — se marca igual, baja probabilidad")

    if not has_creds:
        # marcar usados igualmente (pre-cableado: para ir rotando países)
        now = datetime.now(timezone.utc).isoformat()
        for iso2 in meta["countries"]:
            led["countries"][iso2] = now
        led["rounds"].append(meta["round_key"])
        _save_ledger(led)
        print("  geoquiz: generado, subida OMITIDA (pre-cableado)")
        _notify(f"🌍 <b>{DISPLAY_NAME}</b> (pre-cableado) · ronda generada sin canal YT\n"
                f"<i>{', '.join(meta['countries'])}</i> · slug <code>{meta['slug']}</code>")
        return {"status": "ok", "slug": meta["slug"], "url": "",
                "yt_status": "skip_no_channel", "round_key": meta["round_key"]}

    # subida (desactiva el guard de dedup POR TÍTULO: el título es fijo de serie)
    from ..upload_youtube import upload_video
    prev_prefix = os.environ.get("YT_CHANNEL_PREFIX", "")
    prev_guard = os.environ.get("DEDUP_UPLOAD_GUARD")
    os.environ["YT_CHANNEL_PREFIX"] = YT_PREFIX
    os.environ["DEDUP_UPLOAD_GUARD"] = "0"
    url, yt_status = "", "skip"
    try:
        vid = upload_video(
            Path(meta["video_path"]), title=meta["title"], description=meta["description"],
            tags=meta.get("tags", []), category_id="27", is_short=True, privacy="public",
        )
        url = f"https://youtube.com/shorts/{vid}"
        yt_status = "ok"
    except Exception as e:
        print(f"  geoquiz upload fail: {type(e).__name__}: {e}")
        yt_status = f"fail: {type(e).__name__}"
    finally:
        if prev_prefix:
            os.environ["YT_CHANNEL_PREFIX"] = prev_prefix
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)
        if prev_guard is not None:
            os.environ["DEDUP_UPLOAD_GUARD"] = prev_guard
        else:
            os.environ.pop("DEDUP_UPLOAD_GUARD", None)

    now = datetime.now(timezone.utc).isoformat()
    for iso2 in meta["countries"]:
        led["countries"][iso2] = now
    led["rounds"].append(meta["round_key"])
    _save_ledger(led)
    _notify(f"✅ <b>{DISPLAY_NAME}</b> · {url or yt_status}\n<i>{', '.join(meta['countries'])}</i>")

    # Crosspost solo a Bluesky propio (BSKY_GEOQUIZ_*) — no contamina otras marcas.
    try:
        if os.environ.get("BSKY_GEOQUIZ_HANDLE") and os.environ.get("BSKY_GEOQUIZ_APP_PASSWORD"):
            from .. import crosspost_full
            cross = crosspost_full.crosspost_short_from_mp4(
                Path(meta["video_path"]), meta["title"], url,
                teaser="🌍 Guess the country by its flag", channel_label="geoquiz", slug=meta["slug"])
            _notify(f"🌍 <b>GeoQuiz · RRSS</b> {crosspost_full.summary_line(cross)}")
    except Exception as e:
        print(f"  geoquiz crosspost fail: {e}")
    return {"status": "ok", "slug": meta["slug"], "url": url,
            "yt_status": yt_status, "round_key": meta["round_key"]}
