"""Uploader del video ambient al canal YT independiente.

Usa credenciales SEPARADAS del canal WaitWhy:
- YT_AMBIENT_REFRESH_TOKEN
- YT_AMBIENT_CLIENT_ID
- YT_AMBIENT_CLIENT_SECRET

Si el user quiere reutilizar el mismo OAuth (multi-canal en una cuenta Google),
también accepta el CHANNEL_ID como parámetro para el upload.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _get_yt_client():
    """Construye YT client autenticado con credenciales ambient."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    refresh = os.environ.get("YT_AMBIENT_REFRESH_TOKEN") or os.environ.get("YT_REFRESH_TOKEN")
    client_id = os.environ.get("YT_AMBIENT_CLIENT_ID") or os.environ.get("YT_CLIENT_ID")
    client_secret = os.environ.get("YT_AMBIENT_CLIENT_SECRET") or os.environ.get("YT_CLIENT_SECRET")
    if not (refresh and client_id and client_secret):
        return None

    creds = Credentials(
        token=None,
        refresh_token=refresh,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube.readonly"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_ambient(video_meta: dict[str, Any]) -> dict | None:
    """Sube el video ambient al canal YT_AMBIENT_*.

    Args:
        video_meta: dict con paths + title/description/tags (output de generator).

    Returns:
        dict con video_id + url si OK, None si falla.
    """
    from googleapiclient.http import MediaFileUpload

    yt = _get_yt_client()
    if not yt:
        print("  ambient-uploader: falta YT_AMBIENT_* creds")
        return None

    video_path = Path(video_meta["video_path"])
    if not video_path.exists():
        print(f"  ambient-uploader: video no existe {video_path}")
        return None

    body = {
        "snippet": {
            "title": video_meta["title"][:100],
            "description": video_meta["description"][:4900],
            "tags": video_meta.get("tags", []),
            "categoryId": "10",  # 10 = Music
            "defaultLanguage": "es",
            "defaultAudioLanguage": "es",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), mimetype="video/mp4",
                             resumable=True, chunksize=8 * 1024 * 1024)
    try:
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        vid = resp["id"]
        url = f"https://youtu.be/{vid}"
        print(f"  ambient-uploader: ✅ {vid} · {url}")
        # Persist
        slug = video_meta.get("slug")
        if slug:
            (Path(video_meta["video_path"]).parent / "youtube.json").write_text(
                json.dumps({"video_id": vid, "url": url, "es": url}, indent=2),
                encoding="utf-8",
            )
        return {"video_id": vid, "url": url}
    except Exception as e:
        print(f"  ambient-uploader: ❌ {type(e).__name__}: {e}")
        return None
