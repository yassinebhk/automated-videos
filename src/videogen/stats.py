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


def fetch_youtube_stats() -> list[dict]:
    """Stats por video subido: views, likes, comments. [] si no hay nada."""
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    from .upload_youtube import SCOPES, TOKEN_FILE

    vids = _collect_video_ids()
    if not vids or not TOKEN_FILE.exists():
        return []

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    yt = build("youtube", "v3", credentials=creds)

    id_map = {v[0]: (v[1], v[2]) for v in vids}
    ids = list(id_map.keys())
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
