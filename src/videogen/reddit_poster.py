"""Auto-poster de Reddit — tráfico externo español gratis y sin App Review.

Reddit permite publicar programáticamente con `praw` usando OAuth "script"
(no requiere revisión de Reddit, solo crear una app en /prefs/apps → obtener
client_id + client_secret + tener usuario y contraseña).

Estrategia:
- Después de cada upload YT del pipeline, si Reddit está configurado, se
  postea automáticamente en 1 subreddit rotatorio (evita shadowban por
  frecuencia).
- Rota subreddits siguiendo la última fecha de post por subreddit (guardada
  en `output/reddit_history.json`) — un mismo subreddit no se toca en <5 días.
- Título y cuerpo generados por el LLM a partir del title/case del vídeo,
  siguiendo templates específicos por subreddit para minimizar señal de
  self-promo.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Subreddits ordenados por fit del nicho true crime español + tráfico esperado.
# La app se auto-limita a 1 post/subreddit cada 5+ días (rate-limit propio, no
# de Reddit) para no dar señal de spam y evitar shadowban.
SUBREDDITS = [
    # (name, style, min_days_between_posts)
    ("podemos",           "provocador",  6),   # ~180k, muy fit con casos políticos
    ("HistoriaDeEspaña", "historico",   5),   # ~80k, ideal para casos históricos
    ("es",                "neutro",      7),   # ~250k, general
    ("PoliticaEsp",       "provocador",  6),   # ~50k, casos políticos
    # r/spain lo dejamos fuera por defecto — mods muy estrictos con self-promo;
    # el usuario puede añadirlo manual si lo desea.
]

HISTORY_FILE = Path(__file__).parent.parent.parent / "output" / "reddit_history.json"


def _load_history() -> dict[str, str]:
    """Carga historial {subreddit: last_post_iso_datetime}."""
    if not HISTORY_FILE.exists():
        return {}
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_history(h: dict[str, str]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(h, indent=2, ensure_ascii=False),
                            encoding="utf-8")


def _choose_subreddit(history: dict[str, str]) -> tuple[str, str] | None:
    """Devuelve (subreddit, style) siguiendo el rate-limit interno. None si
    todos los subreddits están en cooldown."""
    now = datetime.now(timezone.utc)
    candidates = []
    for name, style, min_days in SUBREDDITS:
        last_iso = history.get(name)
        if last_iso:
            try:
                last = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
                if now - last < timedelta(days=min_days):
                    continue  # cooldown activo
            except Exception:
                pass
        candidates.append((name, style))
    if not candidates:
        return None
    # Elige el subreddit con MÁS tiempo desde el último post (o nunca)
    def _age_days(name: str) -> float:
        last_iso = history.get(name)
        if not last_iso:
            return 999.0
        try:
            last = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
            return (now - last).total_seconds() / 86400
        except Exception:
            return 999.0
    candidates.sort(key=lambda c: -_age_days(c[0]))
    return candidates[0]


# --------------------------------------------------------------------------- #
# Templates de post (título + cuerpo) por estilo de subreddit
# --------------------------------------------------------------------------- #

def _templates(style: str, video_title: str, video_url: str,
               case_name: str, key_number: str) -> tuple[str, str]:
    """Devuelve (title, body) markdown para el post de Reddit."""
    # Templates diseñados para MINIMIZAR señal de self-promo:
    # - Título en formato pregunta o dato viral (no "mira mi vídeo")
    # - Cuerpo en 1º persona, curioso, no promocional
    # - URL en el cuerpo, no en el título (mejor para el algoritmo Reddit)
    if style == "provocador":
        title = f"¿Sabíais que {case_name}? Me lo encontré hoy y me quedé loco"
        body = (
            f"Estaba buscando información sobre estafas históricas en España "
            f"y me topé con este resumen del caso. Me sorprendió mucho la "
            f"cifra: **{key_number}**.\n\n"
            f"Lo dejo por si a alguien más le interesa: {video_url}\n\n"
            f"¿Conocíais los detalles? ¿Justicia real o teatro?"
        )
    elif style == "historico":
        title = f"{case_name} — el caso que sacudió España, resumido en 60s"
        body = (
            f"Encontré este resumen visual del caso. Me pareció útil por "
            f"la brevedad y porque incluye la cifra concreta ({key_number}) "
            f"que muchas veces no se mencionan.\n\n"
            f"{video_url}\n\n"
            f"¿Alguien tiene más contexto sobre las consecuencias legales?"
        )
    else:  # neutro
        title = f"¿Conocíais el caso {case_name}?"
        body = (
            f"Me estoy dando cuenta de lo poco que conocemos las estafas "
            f"históricas españolas. Este resumen de 60s explica la mecánica "
            f"del caso — cifra clave: {key_number}.\n\n"
            f"{video_url}"
        )
    return title, body


def _extract_case_and_number(video_title: str) -> tuple[str, str]:
    """Extrae (case_name, key_number) del título del vídeo.

    Ejemplo: "Estafas Españolas #47: Bárcenas ocultó 40M€"
      → ("Bárcenas", "40M€")
    """
    # Case = todo lo que viene después de "#N: " y antes de la cifra
    title = video_title
    m = re.search(r"#\d+:\s*(.+)", title)
    if m:
        title = m.group(1)
    # Número = primera cifra grande (€, millones, %) del título
    num_m = re.search(r"(\d[\d.,]*\s*(?:millones|M€|€|billones|mil)?)",
                      title, flags=re.IGNORECASE)
    key_number = num_m.group(1).strip() if num_m else "cifras brutales"
    # Case name = primera palabra en mayúscula relevante
    case_m = re.match(r"([A-ZÁÉÍÓÚÑ][^:,.]{3,40})", title)
    case_name = case_m.group(1).strip() if case_m else title[:40]
    return case_name, key_number


def post_short_to_reddit(video_title: str, video_url: str,
                         dry_run: bool = False) -> dict[str, Any] | None:
    """Postea el Short en el próximo subreddit disponible. Devuelve dict con
    detalles del post o None si no se pudo/no toca."""
    import os
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    username = os.environ.get("REDDIT_USERNAME")
    password = os.environ.get("REDDIT_PASSWORD")
    user_agent = os.environ.get("REDDIT_USER_AGENT",
                                f"videogen:v1.0 (by /u/{username or 'anon'})")

    if not all([client_id, client_secret, username, password]):
        print("  reddit: skip — faltan credenciales (REDDIT_*)")
        return None

    history = _load_history()
    picked = _choose_subreddit(history)
    if not picked:
        print("  reddit: todos los subreddits en cooldown, skip")
        return None
    subreddit_name, style = picked

    case_name, key_number = _extract_case_and_number(video_title)
    title, body = _templates(style, video_title, video_url, case_name, key_number)

    if dry_run:
        print(f"  reddit DRY-RUN — r/{subreddit_name} ({style})")
        print(f"    Title: {title}")
        print(f"    Body:  {body[:120]}…")
        return {"dry_run": True, "subreddit": subreddit_name,
                "title": title, "body": body}

    try:
        import praw
    except ImportError:
        print("  reddit: praw no instalado, skip")
        return None

    reddit = praw.Reddit(
        client_id=client_id, client_secret=client_secret,
        username=username, password=password, user_agent=user_agent,
    )
    try:
        submission = reddit.subreddit(subreddit_name).submit(
            title=title[:300], selftext=body[:40000],
        )
        history[subreddit_name] = datetime.now(timezone.utc).isoformat()
        _save_history(history)
        print(f"  reddit: ✅ posted r/{subreddit_name} → {submission.url}")
        return {
            "subreddit": subreddit_name, "url": submission.url,
            "title": title, "id": submission.id,
        }
    except Exception as e:
        print(f"  reddit: ❌ post falló ({type(e).__name__}: {e})")
        return None
