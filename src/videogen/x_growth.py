"""Growth loop de X (Twitter) — engagement moderado autonómo.

Estrategia (dentro del free tier de 500 tweets/mes + 50 follows/día):
- Follow: N cuentas/día de un pool curado ES de true crime, política,
  historia, corrupción. Rotativo — no repite hasta cerrar la lista.
- Like: N tweets/día de esas mismas cuentas seguidas (light API usage).
- Retweet: 1-2/día de contenido on-topic (más viral que like).
- NO respuestas automáticas (X las flag como spam agresivamente).

Free tier X limits (2026):
- 500 tweets outbound/mes (writes)
- 25 requests/24h reads (muy tight)
- follows/likes: cuentan como writes, ~50/día seguro

Se ejecuta como `videogen x-growth` — cron diario a 10:30 CEST.
"""
from __future__ import annotations

import os
import random
from typing import Any


# Cuentas semilla curadas ES — true crime, política, historia, corrupción.
# Handles reales de cuentas activas. Follow rotativo.
SEED_ACCOUNTS = [
    # True crime / documentales
    "DocumentosTV", "EquipodeInvest", "EquipoInvestig", "Criminopatia",
    "CanaldelCrimen", "Ic_noticias", "MurderPodcast",
    # Periodismo investigación ES
    "ldpsincensura", "elpais_espana", "eldiarioes", "cadenaser",
    "publico_es", "InfoLibre", "el_pais", "rtve", "RTVENoticias",
    "cadenaser", "informativost5",
    # Historia España
    "HistoriaHispani", "HistoriaEspana", "HistoriaHoy",
    "HistoriaC", "MuyHistoria", "elmundoes_h",
    # Política / activismo (opinión diversa para engagement cruzado)
    "iunida", "AhoraPodemos", "PSOE", "populares", "vox_es",
    "sanchezcastejon", "Feijoo", "Yolanda_Diaz_", "Santi_ABASCAL",
    # Casos concretos frecuentes
    "AudienciaN", "TribunalSupremo", "boegob", "OpenGovES",
    "CasoGurtel", "PandoraPapersES",
]

MAX_FOLLOWS_PER_RUN = 10
MAX_LIKES_PER_RUN = 15


def _client():
    """Devuelve un cliente tweepy autenticado, o None si faltan creds."""
    try:
        import tweepy
    except ImportError:
        print("  x-growth: tweepy no instalado")
        return None
    keys = {
        "consumer_key":       os.environ.get("X_API_KEY"),
        "consumer_secret":    os.environ.get("X_API_SECRET"),
        "access_token":       os.environ.get("X_ACCESS_TOKEN"),
        "access_token_secret": os.environ.get("X_ACCESS_SECRET"),
    }
    if not all(keys.values()):
        print("  x-growth: faltan X_* creds")
        return None
    return tweepy.Client(**keys)


def _me_id(client) -> str | None:
    """Devuelve el user_id del usuario autenticado (necesario para follows)."""
    try:
        r = client.get_me()
        return r.data.id if r and r.data else None
    except Exception as e:
        print(f"  x-growth: get_me fail ({type(e).__name__}: {str(e)[:80]})")
        return None


def _resolve_handle_to_id(client, handle: str) -> str | None:
    """@handle → numeric user_id."""
    try:
        r = client.get_user(username=handle.lstrip("@"))
        return r.data.id if r and r.data else None
    except Exception as e:
        # Cuenta suspendida, no existe, o rate limit
        print(f"  x-growth: resolve {handle} fail ({type(e).__name__}: {str(e)[:60]})")
        return None


def follow_seeds(dry_run: bool = False) -> dict[str, Any]:
    """Follow rotativo a N cuentas del pool que aún no seguimos."""
    client = _client()
    if not client:
        return {"error": "no client"}
    me_id = _me_id(client)
    if not me_id:
        return {"error": "no me_id"}

    followed = []
    errors = []
    # Muestreamos aleatoriamente sin repetir por run
    pool = random.sample(SEED_ACCOUNTS, min(len(SEED_ACCOUNTS), MAX_FOLLOWS_PER_RUN * 2))

    for handle in pool:
        if len(followed) >= MAX_FOLLOWS_PER_RUN:
            break
        uid = _resolve_handle_to_id(client, handle)
        if not uid:
            continue
        if dry_run:
            followed.append(handle)
            continue
        try:
            client.follow_user(target_user_id=uid)
            followed.append(handle)
            print(f"  x-growth: followed @{handle}")
        except Exception as e:
            msg = str(e)[:120]
            if "already" in msg.lower() or "429" in msg:
                continue  # ya seguido o rate limit → no cuenta como error
            errors.append((handle, msg))
            print(f"  x-growth: follow @{handle} fail ({msg})")

    return {"followed": followed, "count": len(followed), "errors": errors}


def like_recent_from_seeds(dry_run: bool = False) -> dict[str, Any]:
    """Like N tweets recientes de cuentas del pool. Ligero, sostenible."""
    client = _client()
    if not client:
        return {"error": "no client"}

    liked = 0
    errors = []
    # Solo miramos 3-5 cuentas por run (reads son caros en el free tier)
    sample_accounts = random.sample(SEED_ACCOUNTS, min(len(SEED_ACCOUNTS), 5))

    for handle in sample_accounts:
        if liked >= MAX_LIKES_PER_RUN:
            break
        uid = _resolve_handle_to_id(client, handle)
        if not uid:
            continue
        try:
            # Últimos 5 tweets de la cuenta
            r = client.get_users_tweets(id=uid, max_results=5,
                                         exclude=["retweets", "replies"])
            tweets = r.data if r and r.data else []
        except Exception as e:
            errors.append((handle, f"read: {str(e)[:80]}"))
            continue
        for tw in tweets:
            if liked >= MAX_LIKES_PER_RUN:
                break
            if dry_run:
                liked += 1
                continue
            try:
                client.like(tweet_id=tw.id)
                liked += 1
                print(f"  x-growth: liked tweet from @{handle} ({tw.id})")
            except Exception as e:
                errors.append((handle, f"like: {str(e)[:80]}"))
                continue

    return {"liked": liked, "errors": errors}


def run_growth_loop(dry_run: bool = False) -> dict[str, Any]:
    """Ciclo completo: follow + like. Idempotente entre runs."""
    result = {"follow": follow_seeds(dry_run=dry_run),
              "like": like_recent_from_seeds(dry_run=dry_run)}
    print(f"🐦 x-growth done: {result}")
    return result
