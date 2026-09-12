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
    # `youtube.force-ssl` es superset de upload + readonly y permite DELETE
    # de videos propios (necesario para limpiar zombies duplicados y otras
    # operaciones de mantenimiento del canal desde el pipeline).
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
CLIENT_SECRET = SECRETS_DIR / "youtube_client_secret.json"
TOKEN_FILE = SECRETS_DIR / "youtube_token.json"


def _channel_prefix() -> str:
    """Prefijo del canal actual — permite tener múltiples canales YT
    en el mismo pipeline. Set via env YT_CHANNEL_PREFIX (ej. 'YT_TAX').
    Default = '' → usa YT_REFRESH_TOKEN estándar (WaitWhy)."""
    import os
    return os.environ.get("YT_CHANNEL_PREFIX", "").strip()


def _get_credentials() -> Credentials:
    import os
    prefix = _channel_prefix()
    if prefix:
        # Modo multi-canal: creds desde env con prefijo (ej. YT_TAX_REFRESH_TOKEN)
        refresh = os.environ.get(f"{prefix}_REFRESH_TOKEN") or os.environ.get("YT_REFRESH_TOKEN")
        client_id = os.environ.get(f"{prefix}_CLIENT_ID") or os.environ.get("YT_CLIENT_ID")
        client_secret = os.environ.get(f"{prefix}_CLIENT_SECRET") or os.environ.get("YT_CLIENT_SECRET")
        if refresh and client_id and client_secret:
            creds = Credentials(
                token=None,
                refresh_token=refresh,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=SCOPES,
            )
            creds.refresh(Request())
            return creds
        print(f"  YT: prefix={prefix} sin creds completas, fallback a token file")
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


AI_DISCLAIMER_ES = (
    "\n\n— — —\n"
    "🤖 Contenido creado con asistencia de IA (voz sintética + imágenes generativas). "
    "Todos los datos son verificables con fuentes públicas. "
    "Este vídeo no sustituye asesoramiento profesional."
)


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
    contains_synthetic_media: bool = True,
) -> str:
    """Sube el video. Devuelve el video_id de YouTube.

    Para que YouTube lo trate como Short: el archivo debe ser vertical (9:16)
    y <60s. Añadimos #Shorts al título/descripción como señal extra.

    publish_at: si se pasa (RFC3339, ej. "2026-05-28T20:00:00Z"), el video se
    sube PRIVADO y YouTube lo hace público automáticamente a esa hora
    (publicación programada). Ignora `privacy` en ese caso.

    contains_synthetic_media: setea status.containsSyntheticMedia (API v3 oct
    2024) — cumplimiento YT AI disclosure + EU AI Act Art. 50 (vigor 2 ago 2026,
    multa hasta €15M). Default True porque TODO nuestro contenido usa TTS
    sintético + imágenes IA generativas.
    """
    creds = _get_credentials()
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    if is_short and "#shorts" not in description.lower():
        description = f"{description}\n\n#Shorts"
    if contains_synthetic_media and "creado con asistencia de ia" not in description.lower():
        description = f"{description}{AI_DISCLAIMER_ES}"

    status = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": made_for_kids,
        "containsSyntheticMedia": contains_synthetic_media,
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


def set_thumbnail(video_id: str, thumbnail_path: Path) -> bool:
    """Sube un thumbnail custom (1280x720 PNG/JPG, <2MB) al video_id.
    Requiere que la cuenta esté verificada (limite 10 uploads/día sin verificar).
    """
    if not thumbnail_path.exists():
        print(f"  YT thumbnail: no existe {thumbnail_path}")
        return False
    try:
        creds = _get_credentials()
        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
        media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg", resumable=False)
        youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
        print(f"  YT thumbnail: ✅ set on {video_id}")
        return True
    except Exception as e:
        # Canal sin verificación SMS → 403 forbidden (limit YT 2 verifs/año/número).
        # No es error crítico: YT usa frame automático como thumbnail. Log silencioso.
        err = str(e)
        if "403" in err or "forbidden" in err.lower():
            print(f"  YT thumbnail: skip (canal sin SMS verify — frame automático)")
        else:
            print(f"  YT thumbnail: ❌ {type(e).__name__}: {err[:150]}")
        return False
