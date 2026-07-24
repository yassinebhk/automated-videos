"""Growth loop de Mastodon — follows + boosts + favourites moderados.

Mismo patrón que bluesky_growth.py pero contra la API de Mastodon:
- Follow por hashtag (busca posts con el tag, sigue autores activos)
- Follow-back a nuevos seguidores
- Favourite (like) a posts recientes con hashtags on-topic
- Reblog (repost) a posts con tracción (>=5 favourites)

Requiere token con scopes: read:accounts, read:search, write:follows,
write:favourites, write:statuses (el reblog es un status).
"""
from __future__ import annotations

import os
import random
from typing import Any


# Hashtags/keywords para buscar posts y autores activos
HASHTAGS = [
    "TrueCrime", "España", "Historia", "Corrupción", "Estafa",
    "Franquismo", "GuerraCivil", "Transición", "Bárcenas", "Gürtel",
    "PoliticaES", "PSOE", "PP", "Podemos", "Periodismo",
]

# Cuentas semilla de partida (ES media/periodismo). El follow inicial busca
# también por hashtag para descubrir cuentas activas del nicho.
SEED_HANDLES = [
    "elpais@mastodon.social",
    "eldiario@mastodon.social",
    "cadenaser@mastodon.social",
]

MAX_FOLLOWS_PER_RUN = 15
MAX_FAVOURITES_PER_RUN = 20
MAX_REBLOGS_PER_RUN = 3


def _api(method: str, path: str, token: str, instance: str, **kwargs) -> Any:
    """HTTP helper contra la API Mastodon."""
    import requests
    url = f"{instance.rstrip('/')}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.request(method, url, headers=headers, timeout=15, **kwargs)
    r.raise_for_status()
    return r.json() if r.text else None


def _me(token: str, instance: str) -> dict:
    return _api("GET", "/api/v1/accounts/verify_credentials", token, instance)


def _search_posts_by_tag(tag: str, token: str, instance: str, limit: int = 20) -> list[dict]:
    """Busca posts recientes con el hashtag."""
    try:
        return _api("GET", f"/api/v1/timelines/tag/{tag}", token, instance,
                    params={"limit": limit})
    except Exception:
        return []


def _my_follows(token: str, instance: str) -> set[str]:
    """IDs de cuentas que sigo (paginación no; con 100 basta para el filtro)."""
    try:
        me = _me(token, instance)
        follows = _api("GET", f"/api/v1/accounts/{me['id']}/following",
                       token, instance, params={"limit": 80})
        return {a["id"] for a in follows}
    except Exception:
        return set()


def _follow(account_id: str, token: str, instance: str) -> bool:
    try:
        _api("POST", f"/api/v1/accounts/{account_id}/follow", token, instance)
        return True
    except Exception as e:
        print(f"    fail follow {account_id}: {e}")
        return False


def _favourite(status_id: str, token: str, instance: str) -> bool:
    try:
        _api("POST", f"/api/v1/statuses/{status_id}/favourite", token, instance)
        return True
    except Exception:
        return False


def _reblog(status_id: str, token: str, instance: str) -> bool:
    try:
        _api("POST", f"/api/v1/statuses/{status_id}/reblog", token, instance)
        return True
    except Exception:
        return False


def run_growth_loop(dry_run: bool = False) -> dict[str, Any]:
    instance = os.environ.get("MASTODON_INSTANCE", "https://mastodon.social").rstrip("/")
    token = os.environ.get("MASTODON_ACCESS_TOKEN")
    if not token:
        return {"error": "no token"}

    print(f"🐘 mastodon-growth loop (instance={instance}, dry={dry_run})")

    try:
        me = _me(token, instance)
        print(f"  me: @{me['username']} · {me.get('followers_count',0)} followers")
    except Exception as e:
        return {"error": f"auth fail: {e}. Token puede no tener scope 'read:accounts'."}

    already_following = _my_follows(token, instance)
    print(f"  currently following: {len(already_following)}")

    followed = []
    favourited = []
    reblogged = []

    # Fase 1: FOLLOW por hashtag — busca posts, sigue a autores activos
    random.shuffle(HASHTAGS)
    for tag in HASHTAGS:
        if len(followed) >= MAX_FOLLOWS_PER_RUN:
            break
        posts = _search_posts_by_tag(tag, token, instance, limit=15)
        for post in posts:
            acc = post.get("account", {})
            aid = acc.get("id")
            if not aid or aid in already_following or aid == me["id"]:
                continue
            # Filtro: cuenta con >= 10 followers (evita bots dormidos)
            if (acc.get("followers_count") or 0) < 10:
                continue
            if dry_run:
                print(f"  DRY follow @{acc.get('acct')} "
                      f"({acc.get('followers_count')} followers)")
                followed.append(acc.get("acct"))
            elif _follow(aid, token, instance):
                followed.append(acc.get("acct"))
                print(f"  followed @{acc.get('acct')}")
            already_following.add(aid)
            if len(followed) >= MAX_FOLLOWS_PER_RUN:
                break

    # Fase 2: FAVOURITE + REBLOG por hashtag
    random.shuffle(HASHTAGS)
    for tag in HASHTAGS:
        if len(favourited) >= MAX_FAVOURITES_PER_RUN and len(reblogged) >= MAX_REBLOGS_PER_RUN:
            break
        posts = _search_posts_by_tag(tag, token, instance, limit=15)
        random.shuffle(posts)
        for post in posts:
            sid = post.get("id")
            if not sid:
                continue
            if len(favourited) < MAX_FAVOURITES_PER_RUN:
                if dry_run:
                    print(f"  DRY favourite {sid}"); favourited.append(sid)
                elif _favourite(sid, token, instance):
                    favourited.append(sid)
            fav_count = post.get("favourites_count") or 0
            if len(reblogged) < MAX_REBLOGS_PER_RUN and fav_count >= 3:
                if dry_run:
                    print(f"  DRY reblog {sid} ({fav_count} favs)"); reblogged.append(sid)
                elif _reblog(sid, token, instance):
                    reblogged.append(sid)

    print(f"🐘 growth done: +{len(followed)} follows, "
          f"{len(favourited)} favourites, {len(reblogged)} reblogs")
    return {
        "followed": followed, "follow_count": len(followed),
        "favourited_count": len(favourited),
        "reblogged_count": len(reblogged),
    }
