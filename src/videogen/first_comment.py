"""Post-a-first-comment strategy — el propio canal comenta el video justo
después de publicar con cifra shock + CTA suscribir + hook engagement.

Por qué funciona:
- El primer comentario "author" aparece destacado aunque no esté pinneado
  (la API de pin de YT NO es pública en 2026 — el user tiene que pinnearlo
  a mano desde YT Studio; enviamos notify Telegram con link directo).
- CTA suscribir claro dentro del comentario → conversión visitante → sub
  (palanca directa para llegar a YPP 500 subs).
- Cifra shock del propio caso al inicio → viewer que aún no vio termina
  viendo (algoritmo detecta comentario denso al inicio = interés real).
- Invita a REPLIES directas: cada reply activa el engagement del video.

Requisitos: token YT con scope `youtube.force-ssl` (ya activo desde 07-24).
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Optional

import requests

from .config import SECRETS_DIR


def _extract_shock_number(text: str) -> Optional[str]:
    """Extrae la primera cifra grande del title/description (M€, muertos, %…)."""
    if not text:
        return None
    patterns = [
        r"(\d[\d.,]*\s*(?:mil\s+)?millones\s*(?:de\s+euros?|€|de\s+pesetas?)?)",
        r"(\d[\d.,]*\s*M€)",
        r"(\d[\d.,]*\s*(?:millones|billones))",
        r"([\d.,]+\s*(?:muertos|víctimas|afectados|españoles|heridos|desaparecidos))",
        r"(\d[\d.,]*€)",
        r"(\d[\d.,]*\s*años?\s*(?:de\s*cárcel|de\s*prisión))",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


_CTA_SUB = [
    "🔔 Suscríbete — mañana caso nuevo, y son casos que nadie más cuenta.",
    "🔔 Sub si quieres el próximo caso enterrado (mañana lo subo).",
    "🔔 Suscríbete — un caso así cada día, verificado y con fuente.",
    "🔔 Sub y no te pierdes el siguiente. Todos con sentencia firme.",
    "🔔 Suscríbete si te enganchan estas historias — mañana otra igual.",
]

_QUESTION_HOOK = [
    "¿Sabías este caso o te acabas de enterar? 👇",
    "¿Cómo se puede tapar algo así? 👇",
    "¿Justicia real o teatro? 👇",
    "¿Qué OTRO caso español enterrado conoces? Lo hago 👇",
    "¿Recordabas los detalles o los descubres hoy? 👇",
]


def _build_shock_comment(video_title: str = "", video_desc: str = "",
                          is_short: bool = True) -> str:
    """Genera comentario con cifra shock (si extraíble) + CTA sub + hook.

    Formato ~180-240 chars (cabe en móvil sin cortarse):
        🚨 CIFRA. Y sigue impune.
        🔔 CTA sub rotativo
        ❓ Hook engagement
    """
    shock_num = _extract_shock_number(f"{video_title} {video_desc}")
    cta = random.choice(_CTA_SUB)
    hook = random.choice(_QUESTION_HOOK)

    if shock_num:
        openers = [
            f"🚨 {shock_num}. Y sigue impune.",
            f"🚨 {shock_num}. Nadie está en la cárcel.",
            f"🚨 {shock_num}. Y casi nadie lo recuerda.",
            f"🚨 {shock_num}. Se enterró el caso.",
        ]
        opener = random.choice(openers)
    else:
        opener = random.choice([
            "🚨 Este caso lo enterraron con éxito.",
            "🚨 Lo peor: sigue impune en 2026.",
            "🚨 Casi nadie lo recuerda ya.",
        ])

    if is_short:
        # Shorts: sin link (YouTube filtra comentarios con enlaces en Shorts).
        return f"{opener}\n\n{cta}\n\n{hook}"
    # Long-form: hay espacio y menos filtrado → añadimos el Telegram si está.
    import os as _os
    _tg = _os.environ.get("TELEGRAM_BROADCAST_CHANNEL", "").strip()
    tg_line = f"\n📲 Casos ampliados + fuentes: t.me/{_tg.lstrip('@')}" if _tg else ""
    return (f"{opener} Los detalles reales, verificados con fuentes públicas, "
            f"están en el vídeo.\n\n{cta}{tg_line}\n\n{hook}")


# Fallback si no hay title (llamada legacy) — más agresivos que los antiguos.
COMMENT_TEMPLATES_LONG = [
    "🚨 ¿Sabías este caso o te acabas de enterar? Suscríbete — mañana caso nuevo, "
    "y son casos que nadie más cuenta. ¿Qué OTRO caso español enterrado conoces? 👇",
    "🚨 Y sigue impune en 2026. Suscríbete si quieres el próximo (mañana lo subo). "
    "¿Cómo se puede tapar algo así? Coméntame 👇",
]

COMMENT_TEMPLATES_SHORT = [
    "🚨 Suscríbete — mañana caso nuevo. ¿Sabías este o te acabas de enterar? 👇",
    "🔔 Sub si quieres el próximo caso enterrado (mañana). ¿Recordabas? 👇",
    "🚨 Y sigue impune. Sub — mañana otro igual. ¿Cómo lo tapan? 👇",
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
        return False
    for t in r.json().get("items", []):
        top = t.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        if top.get("authorChannelId", {}).get("value") == channel_id:
            return True
    return False


def _notify_pin_reminder(video_id: str, is_short: bool, snippet: str) -> None:
    """Envía notify Telegram con link directo para pinnear el comment.
    Pin manual = 1 tap en YT Studio móvil (la API v3 no lo permite)."""
    try:
        from .notify_batch import add
        prefix = "shorts" if is_short else "watch?v="
        url = f"https://youtube.com/{prefix}{video_id}" if is_short else f"https://youtube.com/watch?v={video_id}"
        add(
            f"📌 <b>Pinnea este comentario</b> (1 tap → +30% engagement):\n"
            f"→ {url}\n"
            f"<i>«{snippet[:90]}…»</i>"
        )
    except Exception:
        pass


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
    ids: list[str] = []
    titles: dict[str, str] = {}
    descs: dict[str, str] = {}
    for it in pl.get("items", []):
        vid = it.get("contentDetails", {}).get("videoId")
        pub = it.get("contentDetails", {}).get("videoPublishedAt")
        if vid and pub:
            ids.append(vid)
            snip = it.get("snippet", {}) or {}
            titles[vid] = snip.get("title", "") or ""
            descs[vid] = snip.get("description", "") or ""
    if not ids:
        return {"checked": 0, "posted": 0, "already_had": 0}
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
        text = _build_shock_comment(titles.get(vid, ""), descs.get(vid, ""), is_short=is_short)
        ok = post_first_comment(vid, is_short=is_short, custom_text=text)
        if ok:
            posted += 1
            _notify_pin_reminder(vid, is_short, text)
        else:
            errors += 1
    return {"checked": len(ids), "posted": posted,
            "already_had": already, "errors": errors}


def post_first_comment(video_id: str, is_short: bool = True,
                       custom_text: Optional[str] = None,
                       video_title: str = "",
                       video_desc: str = "") -> bool:
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

    if custom_text:
        text = custom_text
    elif video_title or video_desc:
        text = _build_shock_comment(video_title, video_desc, is_short=is_short)
    else:
        text = random.choice(
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
    err = r.text[:200]
    print(f"  first-comment: ⚠ status={r.status_code} — {err}")
    return False
