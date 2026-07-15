"""Upload a YouTube vía Data API v3."""
from __future__ import annotations

from pathlib import Path

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

from .config import SECRETS_DIR

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
CLIENT_SECRET = SECRETS_DIR / "youtube_client_secret.json"
TOKEN_FILE = SECRETS_DIR / "youtube_token.json"


def _get_credentials() -> Credentials:
    creds: Credentials | None = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET.exists():
                raise RuntimeError(
                    f"Falta {CLIENT_SECRET}. Descárgalo del Google Cloud Console "
                    "(OAuth client de tipo Desktop App, scope YouTube Data API v3)."
                )
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = "27",  # 27 = Education
    privacy: str = "public",
    made_for_kids: bool = False,
    is_short: bool = True,
    publish_at: str | None = None,
) -> str:
    """Sube el video. Devuelve el video_id de YouTube.

    Para que YouTube lo trate como Short: el archivo debe ser vertical (9:16)
    y <60s. Añadimos #Shorts al título/descripción como señal extra.

    publish_at: si se pasa (RFC3339, ej. "2026-05-28T20:00:00Z"), el video se
    sube PRIVADO y YouTube lo hace público automáticamente a esa hora
    (publicación programada). Ignora `privacy` en ese caso.
    """
    creds = _get_credentials()
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    if is_short and "#shorts" not in description.lower():
        description = f"{description}\n\n#Shorts"

    status = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": made_for_kids,
    }
    if publish_at:
        # YouTube exige que el video esté privado para programar su publicación.
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": category_id,
        },
        "status": status,
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  YT upload: {pct}%")
    return response["id"]
