"""Growth loop de Bluesky — engagement moderado para dar visibilidad a la cuenta.

Estrategia (sostenible, evita spam-detection):
- Follow inicial a cuentas relevantes españolas de true crime / historia /
  política / periodismo de investigación (una vez).
- Follow orgánico cada run: follow-back a quien te haya seguido nuevo.
- Like moderado: 15-25 likes/día a posts con hashtags on-topic. Rate limit
  Bluesky ~5000 likes/día — no vamos a rozarlo.
- Repost estratégico: 2-3 reposts/día de contenido true crime / historia.
- NO comentarios automáticos (spammy, moderación humana los detecta).

Se ejecuta como `videogen bluesky-growth` (nuevo comando CLI) — cron dedicado
diario a 10:00 CEST.
"""
from __future__ import annotations

import os
import random
from datetime import datetime, timezone, timedelta
from typing import Any


# Cuentas semilla para el follow inicial. Se buscan por handle o por keyword.
# Mezcla: true crime, historia España, periodismo investigación, política.
SEED_KEYWORDS = [
    # Búsqueda por keyword en posts recientes → obtiene cuentas activas
    "true crime españa", "estafas españa", "crimen historia españa",
    "bárcenas", "gürtel", "corrupción españa", "franquismo",
    "documentos tv", "equipo investigación", "el país historia",
    "guerra civil española", "transición española",
    "podemos", "vox", "psoe", "pp corrupción",
]

# Hashtags a monitorear para likes/reposts
FOLLOW_HASHTAGS = [
    "truecrime", "trueCrimeEspaña", "españa", "historia", "corrupción",
    "estafas", "documentales", "periodismo", "política",
]

MAX_FOLLOWS_PER_RUN = 15
MAX_LIKES_PER_RUN = 20
MAX_REPOSTS_PER_RUN = 3


def _client():
    """Devuelve un Client Bluesky autenticado, o None si faltan creds."""
    from atproto import Client
    handle = os.environ.get("BLUESKY_HANDLE")
    password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not (handle and password):
        return None
    c = Client()
    c.login(handle, password)
    return c


def follow_seed_accounts(dry_run: bool = False) -> dict[str, Any]:
    """Búsqueda inicial + follow de cuentas relevantes por keyword.

    Ejecutar una vez para arrancar. Follow to MAX_FOLLOWS_PER_RUN cuentas.
    """
    c = _client()
    if not c:
        return {"error": "no creds"}

    already = set()
    try:
        # Fetch mis follows actuales
        follows = c.get_follows(c.me.did, limit=100)
        already = {f.did for f in follows.follows}
    except Exception as e:
        print(f"  bsky-growth: get_follows fail {e}")

    followed = []
    for kw in SEED_KEYWORDS:
        if len(followed) >= MAX_FOLLOWS_PER_RUN:
            break
        try:
            # Buscar cuentas cuya bio/nombre contenga el kw
            res = c.app.bsky.actor.search_actors({"q": kw, "limit": 8})
            for actor in (res.actors or []):
                if actor.did in already or actor.did == c.me.did:
                    continue
                # Filtro anti-cuentas dormidas: mínimo 30 followers si el
                # objeto lo expone (ProfileView no siempre; ProfileViewDetailed sí)
                followers = getattr(actor, "followers_count", None)
                if followers is not None and followers < 30:
                    continue
                if dry_run:
                    print(f"  bsky-growth DRY: follow @{actor.handle} "
                          f"({actor.followers_count} followers)")
                else:
                    try:
                        c.follow(actor.did)
                        followed.append(actor.handle)
                        print(f"  bsky-growth: followed @{actor.handle}")
                    except Exception as e:
                        print(f"  bsky-growth: fail follow @{actor.handle}: {e}")
                already.add(actor.did)
                if len(followed) >= MAX_FOLLOWS_PER_RUN:
                    break
        except Exception as e:
            print(f"  bsky-growth: search '{kw}' fail: {e}")
    return {"followed": followed, "count": len(followed)}


def follow_back_new_followers(dry_run: bool = False) -> dict[str, Any]:
    """Follow-back a cuentas que te han seguido pero tú no sigues."""
    c = _client()
    if not c:
        return {"error": "no creds"}
    try:
        followers = c.get_followers(c.me.did, limit=100).followers
        my_follows = {f.did for f in c.get_follows(c.me.did, limit=100).follows}
        pending = [f for f in followers if f.did not in my_follows]
        followed_back = []
        for actor in pending[:MAX_FOLLOWS_PER_RUN]:
            if dry_run:
                print(f"  bsky-growth DRY: follow-back @{actor.handle}")
            else:
                try:
                    c.follow(actor.did)
                    followed_back.append(actor.handle)
                    print(f"  bsky-growth: followed-back @{actor.handle}")
                except Exception as e:
                    print(f"  bsky-growth: fail followback: {e}")
        return {"followed_back": followed_back, "count": len(followed_back)}
    except Exception as e:
        return {"error": str(e)}


def like_and_repost_hashtags(dry_run: bool = False) -> dict[str, Any]:
    """Busca posts recientes con hashtags on-topic y los like/repost moderado."""
    c = _client()
    if not c:
        return {"error": "no creds"}
    likes, reposts = 0, 0
    liked_posts = []
    reposted_posts = []
    random.shuffle(FOLLOW_HASHTAGS)
    for tag in FOLLOW_HASHTAGS:
        if likes >= MAX_LIKES_PER_RUN and reposts >= MAX_REPOSTS_PER_RUN:
            break
        try:
            res = c.app.bsky.feed.search_posts({"q": f"#{tag}", "limit": 15,
                                                 "sort": "latest"})
            posts = res.posts or []
            random.shuffle(posts)
            for post in posts:
                if likes < MAX_LIKES_PER_RUN:
                    if dry_run:
                        print(f"  bsky-growth DRY: like {post.uri[-20:]}")
                    else:
                        try:
                            c.like(post.uri, post.cid)
                            liked_posts.append(post.uri)
                            likes += 1
                        except Exception:
                            pass
                # Repost solo si el post tiene ya cierta tracción (≥5 likes)
                if reposts < MAX_REPOSTS_PER_RUN and (post.like_count or 0) >= 5:
                    if dry_run:
                        print(f"  bsky-growth DRY: repost {post.uri[-20:]}")
                    else:
                        try:
                            c.repost(post.uri, post.cid)
                            reposted_posts.append(post.uri)
                            reposts += 1
                        except Exception:
                            pass
                if likes >= MAX_LIKES_PER_RUN and reposts >= MAX_REPOSTS_PER_RUN:
                    break
        except Exception as e:
            print(f"  bsky-growth: search #{tag} fail: {e}")
    print(f"  bsky-growth: {likes} likes · {reposts} reposts")
    return {"likes": likes, "reposts": reposts}


def run_growth_loop(dry_run: bool = False) -> dict[str, Any]:
    """Ejecuta el ciclo completo: follow seeds (una vez si aún hay cupo) +
    follow-back + engagement."""
    print(f"🦋 bluesky-growth loop iniciado (dry_run={dry_run})")
    result = {}
    result["seeds"] = follow_seed_accounts(dry_run=dry_run)
    result["followbacks"] = follow_back_new_followers(dry_run=dry_run)
    result["engagement"] = like_and_repost_hashtags(dry_run=dry_run)
    print(f"🦋 bluesky-growth loop terminado: {result}")
    return result
