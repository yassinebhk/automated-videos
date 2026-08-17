"""Stats de YouTube vía Data API (part=statistics). Requiere scope readonly."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import UPLOADED_DIR


def _collect_video_ids() -> list[tuple[str, str, str]]:
    """Devuelve [(video_id, slug, lang)] de todos los videos subidos
    (Shorts en youtube.json + long-forms en youtube_long.json)."""
    out = []
    if not UPLOADED_DIR.exists():
        return out
    for d in UPLOADED_DIR.iterdir():
        # Shorts (URL contiene /shorts/)
        yt = d / "youtube.json"
        if yt.exists():
            try:
                data = json.loads(yt.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            ids = data.get("_ids", {})
            for lang in ("es", "en"):
                vid = ids.get(lang)
                if not vid and lang in data:
                    m = re.search(r"shorts/([\w-]+)", data[lang])
                    vid = m.group(1) if m else None
                if vid:
                    out.append((vid, d.name, lang))
        # Long-forms (URL tipo youtu.be/<id> o youtube.com/watch?v=<id>)
        ytl = d / "youtube_long.json"
        if ytl.exists():
            try:
                data = json.loads(ytl.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            ids = data.get("_ids", {})
            for lang in ("es", "en"):
                vid = ids.get(lang)
                if not vid and lang in data:
                    m = re.search(r"(?:youtu\.be/|v=)([\w-]+)", data[lang])
                    vid = m.group(1) if m else None
                if vid:
                    out.append((vid, d.name, lang))
    return out


def fetch_channel_stats() -> dict | None:
    """Stats del canal: suscriptores, views totales, nº de videos."""
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    from .upload_youtube import SCOPES, TOKEN_FILE

    if not TOKEN_FILE.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    yt = build("youtube", "v3", credentials=creds)
    resp = yt.channels().list(part="statistics,snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        return None
    it = items[0]
    st = it.get("statistics", {})
    return {
        "title": it["snippet"]["title"],
        "subscribers": int(st.get("subscriberCount", 0)),
        "hidden_subs": st.get("hiddenSubscriberCount", False),
        "views": int(st.get("viewCount", 0)),
        "videos": int(st.get("videoCount", 0)),
    }


def fetch_recent_titles(n: int = 20, days: int | None = None) -> list[str]:
    """Devuelve los títulos de los últimos N videos subidos al canal.

    Usado por el dedup del autogen para saber qué casos ya se han cubierto
    (Mario Conde, Gescartera, Fórum Filatélico…) y evitar repetirlos.

    Si `days` está dado, solo devuelve los publicados en los últimos N días.
    Esto es importante porque tras 100+ videos publicados, el dedup absoluto
    bloquea TODOS los casos conocidos (bug 08-12: no salió nada por días).
    Con days=90 permite revisitar un caso con nuevo ángulo 3 meses después.
    """
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    from .upload_youtube import SCOPES, TOKEN_FILE

    if not TOKEN_FILE.exists():
        return []
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    yt = build("youtube", "v3", credentials=creds)
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    items = ch.get("items", [])
    if not items:
        return []
    upl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    resp = yt.playlistItems().list(part="snippet", playlistId=upl,
                                   maxResults=min(n, 50)).execute()
    items_yt = resp.get("items", [])
    if days is not None:
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        out = []
        for it in items_yt:
            sn = it.get("snippet", {})
            title = sn.get("title")
            pub = sn.get("publishedAt")
            if not (title and pub):
                continue
            try:
                pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except Exception:
                continue
            if pub_dt >= cutoff:
                out.append(title)
        return out
    return [it["snippet"]["title"] for it in items_yt
            if it.get("snippet", {}).get("title")]


def fetch_youtube_stats() -> list[dict]:
    """Stats por video subido: views, likes, comments. [] si no hay nada.

    Fix bug 08-17: antes leía IDs de output/uploaded/*/youtube.json (filesystem
    local). En GH Actions ese dir está vacío tras cada run efímero → los
    snapshots per-video del daily-summary quedaban vacíos → panels 2 y 3 de
    los charts salían en blanco. Ahora fetch la uploads playlist del canal
    vía YT API (fuente de verdad persistente).
    """
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    from .upload_youtube import SCOPES, TOKEN_FILE

    if not TOKEN_FILE.exists():
        return []
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    yt = build("youtube", "v3", credentials=creds)

    # 1) Obtener uploads playlist
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    items = ch.get("items", [])
    if not items:
        return []
    upl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # 2) IDs de los últimos 50 videos + fallback filesystem para slug/lang
    fs_map = {v[0]: (v[1], v[2]) for v in _collect_video_ids()}
    pl = yt.playlistItems().list(part="contentDetails", playlistId=upl,
                                  maxResults=50).execute()
    ids = [it["contentDetails"]["videoId"] for it in pl.get("items", [])]
    if not ids:
        return []

    id_map = {vid: fs_map.get(vid, ("", "")) for vid in ids}
    results = []
    # La API admite hasta 50 ids por llamada
    for i in range(0, len(ids), 50):
        batch = ids[i : i + 50]
        resp = yt.videos().list(part="statistics,snippet", id=",".join(batch)).execute()
        for item in resp.get("items", []):
            st = item.get("statistics", {})
            slug, lang = id_map.get(item["id"], ("", ""))
            results.append({
                "id": item["id"],
                "slug": slug,
                "lang": lang,
                "title": item["snippet"]["title"],
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
                "url": f"https://youtube.com/shorts/{item['id']}",
            })
    results.sort(key=lambda x: x["views"], reverse=True)
    return results


# Horas óptimas de publicación (heurística, hora local del creador).
OPTIMAL_TIMES = {
    "youtube": "12:00–15:00 y 19:00–22:00 (entre semana)",
    "tiktok": "06:00–10:00 y 19:00–23:00 (picos martes y jueves)",
}
