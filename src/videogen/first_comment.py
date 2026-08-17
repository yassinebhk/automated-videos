"""Post-a-first-comment strategy — el propio canal comenta el video justo
después de publicar con un hook polarizante.

Por qué funciona:
- El primer comentario "author" aparece destacado en muchos casos aunque no
  esté pinneado (la API de pin de YT no es pública en 2026).
- Da CONTEXTO adicional que la descripción no permite (más agresivo, más
  emocional) sin arriesgar el título.
- Invita a REPLIES directas: cada reply activa el engagement del video en el
  algo de YT.
- Los datos del canal muestran ratio 0.03 comentarios/video — un solo
  comment del creador con hook puede empujar a 0.5-1 por video (10-30×).

Requisitos: token YT con scope `youtube.force-ssl` (ya activo desde 07-24).
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

import requests

from .config import SECRETS_DIR


# Templates de comentarios — variados para no parecer bot. Cada uno con un
# ángulo polarizante distinto que fuerza al viewer a comentar.
COMMENT_TEMPLATES_LONG = [
    "🚨 Pregunta seria: ¿este caso te lo enseñaron en el instituto o te acabas "
    "de enterar? Comenta si sabías del caso o no — quiero ver cuánta gente "
    "ha vivido en la ignorancia de esto.",

    "¿Justicia real o teatro? El culpable pasea libre mientras las víctimas "
    "murieron esperando. Etiqueta a quien aún crea que en España se paga por "
    "robar.",

    "Lo peor no es lo que hicieron. Lo peor es que sigue pasando y nadie lo "
    "cuenta. ¿Qué OTRO caso español enterrado por la justicia conoces? "
    "Escríbelo abajo — hago el video.",

    "Coméntame: ¿esto es corrupción, incompetencia o directamente pacto de "
    "silencio? Yo tengo mi teoría pero quiero leer la vuestra.",

    "¿Sabías este caso o te lo acabo de descubrir? Los que se enteran hoy: "
    "responded «nuevo». Los que ya sabían: contad qué recordabais.",
]

COMMENT_TEMPLATES_SHORT = [
    "¿Justicia o teatro? Coméntame.",
    "¿Sabías este caso o te lo acabo de descubrir? 👇",
    "Etiqueta al que aún defiende a este señor.",
    "¿Otro caso español enterrado que conozcas? Escríbelo — hago el video.",
    "Comenta «robo» o «fraude» según tú lo llames.",
]


def _get_access_token() -> Optional[str]:
    tok_path = SECRETS_DIR / "youtube_token.json"
    if not tok_path.exists():
        return None
    tok = json.loads(tok_path.read_text())
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": tok["client_id"], "client_secret": tok["client_secret"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token",
    }, timeout=15).json()
    return r.get("access_token")


def _get_channel_id(access_token: str) -> Optional[str]:
    """Devuelve el channelId del user autenticado (necesario para commentThreads)."""
    H = {"Authorization": f"Bearer {access_token}"}
    r = requests.get("https://www.googleapis.com/youtube/v3/channels",
                     params={"part": "id", "mine": "true"},
                     headers=H, timeout=15).json()
    items = r.get("items", [])
    return items[0]["id"] if items else None


def _has_channel_comment(access_token: str, video_id: str, channel_id: str) -> bool:
    """True si el canal ya comentó en este video (evita duplicar)."""
    H = {"Authorization": f"Bearer {access_token}"}
    r = requests.get("https://www.googleapis.com/youtube/v3/commentThreads",
                     params={"part": "snippet", "videoId": video_id,
                             "maxResults": 20, "textFormat": "plainText"},
                     headers=H, timeout=15)
    if r.status_code != 200:
        return False  # asume no comentado, mejor duplicar que perder
    for t in r.json().get("items", []):
        top = t.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        if top.get("authorChannelId", {}).get("value") == channel_id:
            return True
    return False


def catchup_pending_first_comments(max_videos: int = 20) -> dict:
    """Recorre los últimos videos PÚBLICOS del canal y postea first-comment
    en los que aún no lo tengan.

    Fix bug 08-17: los videos se suben scheduled/private a las 21:00 UTC. El
    first-comment en el upload inmediato falla 403 porque el video aún está
    privado. Este catchup se ejecuta cada 2h y publica el first-comment
    después de que YT haga público el video.

    Devuelve dict con contadores.
    """
    tok = _get_access_token()
    if not tok:
        return {"error": "no token"}
    channel_id = _get_channel_id(tok)
    if not channel_id:
        return {"error": "no channel_id"}
    H = {"Authorization": f"Bearer {tok}"}
    ch = requests.get("https://www.googleapis.com/youtube/v3/channels",
                      params={"part": "contentDetails", "mine": "true"},
                      headers=H, timeout=15).json()
    items = ch.get("items", [])
    if not items:
        return {"error": "no channel"}
    upl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = requests.get("https://www.googleapis.com/youtube/v3/playlistItems",
                      params={"part": "contentDetails,snippet", "playlistId": upl,
                              "maxResults": min(max_videos, 50)},
                      headers=H, timeout=15).json()
    ids = []
    for it in pl.get("items", []):
        vid = it.get("contentDetails", {}).get("videoId")
        pub = it.get("contentDetails", {}).get("videoPublishedAt")
        if vid and pub:  # solo los ya publicados (no scheduled)
            ids.append(vid)
    if not ids:
        return {"checked": 0, "posted": 0, "already_had": 0}
    # Fetch status + contentDetails para saber duración
    vres = requests.get("https://www.googleapis.com/youtube/v3/videos",
                        params={"part": "status,contentDetails", "id": ",".join(ids)},
                        headers=H, timeout=15).json()
    posted = already = errors = 0
    import re as _re
    for v in vres.get("items", []):
        vid = v["id"]
        ps = v.get("status", {}).get("privacyStatus")
        if ps != "public":
            continue
        dur = v.get("contentDetails", {}).get("duration", "PT0S")
        m = _re.match(r'PT(?:(\d+)M)?(?:(\d+)S)?', dur)
        secs = (int(m.group(1) or 0)*60 + int(m.group(2) or 0)) if m else 0
        is_short = secs <= 62
        if _has_channel_comment(tok, vid, channel_id):
            already += 1
            continue
        ok = post_first_comment(vid, is_short=is_short)
        if ok:
            posted += 1
        else:
            errors += 1
    return {"checked": len(ids), "posted": posted,
            "already_had": already, "errors": errors}


def post_first_comment(video_id: str, is_short: bool = True,
                       custom_text: Optional[str] = None) -> bool:
    """Publica un comentario como el canal en un video. Devuelve True si OK.

    Falla silencioso si:
    - No hay token con scope force-ssl
    - Los comentarios están deshabilitados en el video
    - El video aún no acepta comentarios (recién programado)
    """
    tok = _get_access_token()
    if not tok:
        print("  first-comment: sin token YT, salto")
        return False
    channel_id = _get_channel_id(tok)
    if not channel_id:
        print("  first-comment: no pude obtener channelId, salto")
        return False

    text = custom_text or random.choice(
        COMMENT_TEMPLATES_LONG if not is_short else COMMENT_TEMPLATES_SHORT
    )
    H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    body = {
        "snippet": {
            "videoId": video_id,
            "channelId": channel_id,
            "topLevelComment": {
                "snippet": {"textOriginal": text}
            },
        }
    }
    r = requests.post("https://www.googleapis.com/youtube/v3/commentThreads",
                      params={"part": "snippet"}, headers=H, json=body, timeout=20)
    if r.status_code == 200:
        cid = r.json().get("id", "?")
        print(f"  first-comment: ✅ posted {cid} → «{text[:60]}…»")
        return True
    # Los errores típicos: 403 si comments disabled, 400 si video aún no accesible
    err = r.text[:200]
    print(f"  first-comment: ⚠ status={r.status_code} — {err}")
    return False
