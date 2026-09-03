"""Re-promoción de top-YT videos en Bluesky + Mastodon + Threads con hooks
frescos generados por Gemini. Corre 2× al día en horas distintas del autogen
para saturar el feed sin quemar contenido nuevo.

Estrategia:
- Coge los top-N videos de YT de los últimos 14 días (>100 views + <30 días).
- Rota entre ellos para que no salga siempre el mismo.
- Genera hook nuevo (no reutiliza el título) para variedad.
- Postea a las 3 redes con el mismo hook + link YT.
- Ledger `output/social_boost_log.json` evita repostear el mismo video en la
  misma red en <5 días.
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .config import ROOT

BOOST_LOG = ROOT / "output" / "social_boost_log.json"
STATS_HISTORY = ROOT / "output" / "stats_history.jsonl"
MIN_VIEWS = 100
LOOKBACK_DAYS = 30
COOLDOWN_DAYS = 5


def _load_ledger() -> dict[str, dict[str, str]]:
    """{ video_id: { platform: iso_timestamp } }"""
    if not BOOST_LOG.exists():
        return {}
    try:
        return json.loads(BOOST_LOG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_ledger(data: dict[str, dict[str, str]]) -> None:
    BOOST_LOG.parent.mkdir(parents=True, exist_ok=True)
    BOOST_LOG.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                          encoding="utf-8")


def _mark_boosted(video_id: str, platform: str) -> None:
    ledger = _load_ledger()
    ts = datetime.now(timezone.utc).isoformat()
    ledger.setdefault(video_id, {})[platform] = ts
    _save_ledger(ledger)


def _recently_boosted(video_id: str, platform: str) -> bool:
    ledger = _load_ledger()
    entry = (ledger.get(video_id) or {}).get(platform)
    if not entry:
        return False
    try:
        ts = datetime.fromisoformat(entry)
    except Exception:
        return False
    return (datetime.now(timezone.utc) - ts) < timedelta(days=COOLDOWN_DAYS)


def _load_top_videos() -> list[dict[str, Any]]:
    """Top YT videos de últimos 30 días con >100 views. Uses stats_history."""
    if not STATS_HISTORY.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp()
    latest: dict[str, dict] = {}
    for line in STATS_HISTORY.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("platform") != "youtube" or r.get("kind") != "video":
            continue
        vid = r.get("video_id") or ""
        if not vid:
            continue
        ts = int(r.get("ts") or 0)
        if ts < cutoff:
            continue
        prev = latest.get(vid)
        if not prev or ts > int(prev.get("ts") or 0):
            latest[vid] = r
    def _is_true_crime(title: str) -> bool:
        low = (title or "").lower()
        return ("caso " in low or "· #" in low or " · #" in low
                or "estafa" in low or "fraude" in low or "corrupción" in low)
    top = [r for r in latest.values()
           if int(r.get("views") or 0) >= MIN_VIEWS
           and _is_true_crime(r.get("title") or "")]
    top.sort(key=lambda r: -int(r.get("views") or 0))
    return top


def _pick_video_for_platform(platform: str) -> dict | None:
    """Elige un video candidato para `platform` que no esté en cooldown."""
    top = _load_top_videos()
    fresh = [v for v in top if not _recently_boosted(v["video_id"], platform)]
    if not fresh:
        return None
    # Weighted random: top más views tienen más probabilidad, pero variedad
    weights = [max(1, int(v.get("views") or 0)) for v in fresh[:15]]
    return random.choices(fresh[:15], weights=weights, k=1)[0]


HOOK_ANGLES = [
    "dato-bomba",         # "300 millones desaparecieron en 3 años. Nadie fue a prisión."
    "cita-sentencia",     # "El TS lo llamó 'saqueo sistemático'. Terminaron con..."
    "paradoja-tiempo",    # "En 1993 lo condenaron. En 2019 ya estaba libre. En 2024..."
    "comparacion-cifra",  # "Con lo robado se pagaban 12 hospitales."
    "personaje-inesperado", # "El cabecilla no era un mafioso. Era un ministro."
    "pregunta-provocadora", # "¿Cuánto tiempo cabría alguien preso por robar 300M€ en España? Menos de lo que crees."
    "arranque-frio",      # "Julio, 1993. Una llamada. Todo se cae."
    "consecuencia-hoy",   # "Ese caso todavía marca la ley de..."
]


def _hook_for(video: dict) -> str:
    """Hook via Gemini con ángulo aleatorio. Fallback estático si falla."""
    title = video.get("title") or ""
    yt_url = f"https://youtu.be/{video.get('video_id')}"
    angle = random.choice(HOOK_ANGLES)
    fallback_hooks = [
        f"Caso real, sentencia firme, cifras que no cuadran.\n\n{title}\n\n{yt_url}",
        f"Robaron millones y ni siquiera es lo más brutal del caso.\n\n{title}\n\n{yt_url}",
        f"Esto no lo contaron en las noticias así.\n\n{title}\n\n{yt_url}",
        f"Corrupción española que sigue marcando la ley.\n\n{title}\n\n{yt_url}",
    ]
    try:
        from google import genai
        from google.genai import types
        from .config import gemini_key
        key = gemini_key()
        if not key:
            return random.choice(fallback_hooks)
        client = genai.Client(api_key=key)
        prompt = (
            f"Escribe UN post corto (150-250 chars) para redes sobre este video de un caso español real.\n\n"
            f"ÁNGULO OBLIGATORIO: {angle}\n"
            f"- dato-bomba: arranca con una cifra brutal + consecuencia mínima\n"
            f"- cita-sentencia: cita textual imaginada del juez o del sumario\n"
            f"- paradoja-tiempo: fechas que chocan (X pasó tal año, en 20XX ya estaba libre)\n"
            f"- comparacion-cifra: con esa cantidad se podrían pagar N hospitales/salarios/pisos\n"
            f"- personaje-inesperado: no era un mafioso, era un [ministro/banquero/empresario]\n"
            f"- pregunta-provocadora: pregunta directa que rompa el scroll\n"
            f"- arranque-frio: [fecha]. [detalle mínimo]. Todo cambia.\n"
            f"- consecuencia-hoy: cómo ese caso todavía afecta hoy\n\n"
            f"REGLAS:\n"
            f"- PROHIBIDO empezar con '¿Sabías...?', 'Todos hemos...', '¿Recuerdas...?'\n"
            f"- PROHIBIDO usar 'brutal', 'increíble', 'te va a impactar', 'no te lo vas a creer'\n"
            f"- Tono directo, seco, español periodístico\n"
            f"- Sin emojis salvo 1 al final máximo (opcional)\n"
            f"- Termina con el link\n\n"
            f"Título del video: {title}\n"
            f"Link: {yt_url}\n\n"
            f"Devuelve SOLO el post, sin comillas ni encabezado."
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=1.2, max_output_tokens=250),
        )
        text = (resp.text or "").strip().strip('"')
        # Rechaza si empieza con clichés
        lower = text.lower()
        if any(lower.startswith(bad) for bad in ("¿sabías", "sabías", "¿recuerdas", "todos hemos", "increíble")):
            print(f"  boost: hook rechazado por cliché — fallback")
            return random.choice(fallback_hooks)
        if 30 < len(text) < 400 and yt_url in text:
            return text
        if 30 < len(text) < 350:
            return f"{text}\n\n{yt_url}"
    except Exception as e:
        print(f"  boost: Gemini fail ({type(e).__name__}: {e}) — fallback estático")
    return random.choice(fallback_hooks)


def boost_once() -> dict[str, Any]:
    """Postea a las 3 redes un video top-YT reciente con hook fresco.

    Devuelve dict con status por plataforma.
    """
    result = {}
    for platform in ("bluesky", "mastodon", "threads"):
        video = _pick_video_for_platform(platform)
        if not video:
            result[platform] = {"status": "no_candidate"}
            continue
        hook = _hook_for(video)
        posted = _post_platform(platform, hook)
        result[platform] = {
            "video_id": video.get("video_id"),
            "title": (video.get("title") or "")[:60],
            "posted": posted,
        }
        if posted:
            _mark_boosted(video["video_id"], platform)
    return result


def _post_platform(platform: str, text: str) -> bool:
    try:
        if platform == "bluesky":
            handle = os.environ.get("BLUESKY_HANDLE")
            pwd = os.environ.get("BLUESKY_APP_PASSWORD")
            if not (handle and pwd):
                return False
            from atproto import Client
            c = Client()
            c.login(handle, pwd)
            c.send_post(text=text[:300])
            return True
        if platform == "mastodon":
            import requests as _req
            instance = os.environ.get("MASTODON_INSTANCE", "https://mastodon.social").rstrip("/")
            token = os.environ.get("MASTODON_ACCESS_TOKEN")
            if not token:
                return False
            r = _req.post(f"{instance}/api/v1/statuses",
                          headers={"Authorization": f"Bearer {token}"},
                          data={"status": text[:500], "visibility": "public"},
                          timeout=30)
            return r.status_code < 300
        if platform == "threads":
            import requests as _req
            tok = os.environ.get("THREADS_TOKEN")
            uid = os.environ.get("THREADS_USER_ID")
            if not (tok and uid):
                return False
            base = "https://graph.threads.net/v1.0"
            c = _req.post(f"{base}/{uid}/threads",
                          params={"media_type": "TEXT", "text": text[:500],
                                  "access_token": tok},
                          timeout=30).json()
            if "id" not in c:
                return False
            import time as _t
            _t.sleep(30)  # Threads necesita procesamiento
            p = _req.post(f"{base}/{uid}/threads_publish",
                          params={"creation_id": c["id"], "access_token": tok},
                          timeout=30).json()
            return "id" in p
    except Exception as e:
        print(f"  boost {platform}: {type(e).__name__}: {e}")
    return False
