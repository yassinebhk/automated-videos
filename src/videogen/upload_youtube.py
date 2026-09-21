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

import os as _os_scopes

# Scopes básicos — TODOS los refresh_tokens actuales están autorizados con estos.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    # `youtube.force-ssl` es superset de upload + readonly y permite DELETE
    # de videos propios (necesario para limpiar zombies duplicados y otras
    # operaciones de mantenimiento del canal desde el pipeline).
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Analytics scope OPT-IN: incluye watch-time/views 90d (para YPP progress real).
# Requiere REAUTH de todos los canales (commit aefc60d lo añadió como default y
# rompió los 9 tokens con invalid_scope 21/09). Ahora es opt-in vía env var:
#   YT_ANALYTICS_SCOPE=1 → incluye scope (necesita reauth después)
#   default (0/vacío) → scope OMITIDO, tokens actuales funcionan
if _os_scopes.environ.get("YT_ANALYTICS_SCOPE", "").strip() in ("1", "true", "yes"):
    SCOPES.append("https://www.googleapis.com/auth/yt-analytics.readonly")
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
        # Modo multi-canal: el REFRESH_TOKEN DEBE ser el del canal (define la cuenta YT).
        # ⚠️ 18/09: NO caer a YT_REFRESH_TOKEN si falta. Ese fallback estaba subiendo
        # contenido de canales sin creds (rankings-en en inglés, pádel…) al canal
        # PRINCIPAL WaitWhy (true crime ES) → identidad rota + 0-30 views en lo reciente.
        # client_id/secret SÍ pueden compartir el OAuth app (es el refresh_token quien
        # determina el canal). Sin refresh propio → OMITIR upload (no contaminar).
        refresh = os.environ.get(f"{prefix}_REFRESH_TOKEN")
        client_id = os.environ.get(f"{prefix}_CLIENT_ID") or os.environ.get("YT_CLIENT_ID")
        client_secret = os.environ.get(f"{prefix}_CLIENT_SECRET") or os.environ.get("YT_CLIENT_SECRET")
        if not refresh:
            raise RuntimeError(
                f"YT upload OMITIDO: canal '{prefix}' sin {prefix}_REFRESH_TOKEN. "
                f"No subo al canal principal WaitWhy para no contaminarlo. "
                f"Crea el canal + secrets, o enruta a un canal host con credenciales."
            )
        if refresh and client_id and client_secret:
            creds = Credentials(
                token=None,
                refresh_token=refresh,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                # ⚠️ NUNCA pasar scopes en el REFRESH. Google, en un refresh_token
                # grant, si mandas `scope` exige que sea SUBSET de lo concedido; pedir
                # un scope que el token no tiene (p.ej. yt-analytics.readonly antes de
                # reautorizar) → invalid_scope → refresh KO → subida rota. Con scopes=None
                # no se manda `scope` y Google devuelve los concedidos (incluye analytics
                # SOLO si el token ya lo tenía → activación graceful). Bug 21/09 aefc60d.
                scopes=None,
            )
            creds.refresh(Request())
            return creds
        print(f"  YT: prefix={prefix} sin creds completas, fallback a token file")
    creds: Credentials | None = None
    if TOKEN_FILE.exists():
        # scopes=None → usa los scopes guardados en el propio token file (siempre
        # subset de lo concedido) → el refresh no puede dar invalid_scope.
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), None)
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
    # Inyecta afiliados Amazon ES por nicho (si AMAZON_AFFILIATE_TAG está
    # configurado). No-op sin tag. Monetización pre-YPP.
    try:
        from .affiliate import enrich_description
        import os as _os
        yt_prefix = _os.environ.get("YT_CHANNEL_PREFIX", "")
        description = enrich_description(description, yt_prefix=yt_prefix)
    except Exception as _e:
        print(f"  affiliate injection skip: {_e}")

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
