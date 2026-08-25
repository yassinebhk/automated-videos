"""Auto-poster de TikTok via Content Posting API v2 (FILE_UPLOAD chunked).

Por qué TikTok: la red donde el algoritmo empuja más contenido nuevo sin
followers previos. Shorts verticales 9:16 (mismos que YT) funcionan directo.

Por qué FILE_UPLOAD y no PULL_FROM_URL:
- PULL_FROM_URL requiere que el dominio del vídeo esté verificado en el
  app dashboard, y jsDelivr no es nuestro dominio → imposible.
- FILE_UPLOAD envía los bytes del mp4 directamente vía HTTP PUT chunked
  a un upload_url temporal que TikTok emite en el init. Sin dependencia
  de hosting público.

Modos:
- **Direct** (video.publish aprobado tras review): publica al feed inmediatamente.
- **Draft** (solo video.upload): video llega a bandeja de borradores del user,
  publica manualmente 3 taps desde app TikTok móvil.

Auto-detección: intenta direct primero, si TikTok responde con scope error
cae a inbox. Se puede forzar con env TIKTOK_MODE=direct|draft.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

import requests


TT_API = "https://open.tiktokapis.com/v2"
# TikTok Content Posting API: chunk_size DEBE estar entre 5MB y 64MB, y el
# total_chunk_count debe cumplir la aritmética ceil(video_size/chunk_size).
# El ÚLTIMO chunk puede ser menor que chunk_size. Pero chunk_size NUNCA
# puede ser menor de 5MB, incluso para uploads de un solo chunk.
TT_MIN_CHUNK = 5 * 1024 * 1024
TT_MAX_CHUNK = 64 * 1024 * 1024
CHUNK_SIZE = 10 * 1024 * 1024


def _refresh_access_token() -> Optional[str]:
    """Refresca el access_token. Access tokens duran 24h; refresh 365d."""
    refresh_token = os.environ.get("TIKTOK_REFRESH_TOKEN")
    client_key = os.environ.get("TIKTOK_CLIENT_KEY")
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET")
    if not (refresh_token and client_key and client_secret):
        return None
    try:
        r = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=20,
        )
        d = r.json()
        if r.status_code != 200 or "access_token" not in d:
            print(f"  tt: refresh fail — {str(d)[:200]}")
            return None
        return d["access_token"]
    except Exception as e:
        print(f"  tt: refresh exception — {type(e).__name__}: {e}")
        return None


def _init_upload(access_token: str, video_size: int, endpoint: str,
                 post_info: Optional[dict] = None) -> Optional[dict]:
    """Inicia FILE_UPLOAD chunked. Devuelve dict con upload_url + publish_id.

    Reglas TikTok API observadas empíricamente (dificultan lo que dicen los
    docs): TikTok exige chunk_size ≤ video_size EN el init. Es decir NO
    puedes declarar chunk_size 10MB si video pesa 3MB. Fórmula usada:
    - Si video < 5MB: chunk_size = video_size + total_chunk_count = 1
    - Si video >= 5MB: chunk_size = min(video_size, CHUNK_SIZE) +
      total_chunk_count = ceil(video_size / chunk_size)
    """
    if video_size < TT_MIN_CHUNK:
        chunk_size = video_size
        total_chunks = 1
    else:
        chunk_size = min(video_size, CHUNK_SIZE)
        total_chunks = (video_size + chunk_size - 1) // chunk_size
    print(f"  tt: init video={video_size}B chunk={chunk_size}B count={total_chunks}")

    body: dict[str, Any] = {
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunks,
        },
    }
    if post_info:
        body["post_info"] = post_info

    r = requests.post(
        f"{TT_API}{endpoint}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json=body, timeout=60,
    )
    try:
        d = r.json()
    except Exception:
        print(f"  tt: init respuesta no-JSON {r.status_code} — {r.text[:200]}")
        return None
    err = (d.get("error") or {})
    err_code = (err.get("code") or "").lower()
    err_msg = err.get("message") or ""
    if r.status_code != 200 or err_code not in ("", "ok"):
        print(f"  tt: init fail {r.status_code} — code={err_code} msg={err_msg[:200]}")
        return {"error_code": err_code, "error_message": err_msg}
    data = d.get("data") or {}
    return {
        "upload_url": data.get("upload_url"),
        "publish_id": data.get("publish_id"),
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
    }


def _upload_chunks(local_mp4: Path, upload_url: str, chunk_size: int,
                    total_chunks: int) -> bool:
    """Envía el mp4 por chunks vía PUT. TikTok exige Content-Range headers.

    Para el ÚLTIMO chunk (o único chunk cuando video < chunk_size), leemos
    el resto del stream — que puede ser menor que chunk_size — y usamos
    Content-Range con los bytes reales.
    """
    total_size = local_mp4.stat().st_size
    with open(local_mp4, "rb") as f:
        for i in range(total_chunks):
            start = i * chunk_size
            # Leer hasta chunk_size o hasta EOF, lo que llegue primero.
            data = f.read(chunk_size)
            if not data:
                break
            end = start + len(data) - 1  # inclusive
            headers = {
                "Content-Range": f"bytes {start}-{end}/{total_size}",
                "Content-Type": "video/mp4",
                "Content-Length": str(len(data)),
            }
            r = requests.put(upload_url, headers=headers, data=data, timeout=120)
            if r.status_code not in (200, 201, 206):
                print(f"  tt: chunk {i+1}/{total_chunks} fail {r.status_code} — {r.text[:200]}")
                return False
    return True


def _poll_status(access_token: str, publish_id: str, max_wait: int = 300) -> Optional[str]:
    """Espera a que TikTok procese el video. Devuelve status final."""
    start = time.time()
    while time.time() - start < max_wait:
        r = requests.post(
            f"{TT_API}/post/publish/status/fetch/",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={"publish_id": publish_id}, timeout=30,
        )
        try:
            d = r.json()
        except Exception:
            time.sleep(5)
            continue
        data = d.get("data") or {}
        status = (data.get("status") or "").upper()
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return status
        if status == "FAILED":
            print(f"  tt: status FAILED — {d}")
            return status
        time.sleep(5)
    print(f"  tt: status timeout tras {max_wait}s")
    return None


def _try_direct(access_token: str, local_mp4: Path, title: str) -> Optional[dict]:
    """Direct post — requiere scope video.publish."""
    size = local_mp4.stat().st_size
    init = _init_upload(
        access_token, size, "/post/publish/video/init/",
        post_info={
            "title": title[:150],
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000,
        },
    )
    return init


def _try_draft(access_token: str, local_mp4: Path) -> Optional[dict]:
    """Draft upload — solo requiere scope video.upload."""
    size = local_mp4.stat().st_size
    init = _init_upload(access_token, size, "/post/publish/inbox/video/init/")
    return init


def post_video_to_tiktok(video_title: str, local_mp4: Path, slug: str,
                          dry_run: bool = False) -> dict[str, Any] | None:
    """Sube un video a TikTok — direct al feed si scope aprobado, si no draft.

    Usa FILE_UPLOAD chunked (sin dependencia de dominio público verificado).
    """
    access_token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if not access_token:
        print("  tt: skip — falta TIKTOK_ACCESS_TOKEN")
        return None
    if not local_mp4.exists():
        print(f"  tt: skip — mp4 no existe: {local_mp4}")
        return None

    mode = (os.environ.get("TIKTOK_MODE") or "auto").lower()
    if dry_run:
        print(f"  tt DRY-RUN — modo={mode}, title={video_title[:80]}")
        return {"dry_run": True, "mode": mode, "title": video_title}

    tried_refresh = False

    def _attempt(token: str) -> Optional[dict]:
        """Devuelve init dict con publish_id + upload_url + kind."""
        if mode == "direct":
            r = _try_direct(token, local_mp4, video_title)
            if r and r.get("publish_id"):
                r["kind"] = "direct"
            return r
        if mode == "draft":
            r = _try_draft(token, local_mp4)
            if r and r.get("publish_id"):
                r["kind"] = "draft"
            return r
        # auto: prueba direct → fallback a draft si scope no aprobado
        r = _try_direct(token, local_mp4, video_title)
        if r and r.get("publish_id"):
            r["kind"] = "direct"
            return r
        needs_fallback = r and any(
            k in (r.get("error_code", "") + r.get("error_message", "")).lower()
            for k in ("scope", "unauthorized", "permission")
        )
        if needs_fallback:
            print("  tt: direct sin scope aprobado, fallback a draft")
            r2 = _try_draft(token, local_mp4)
            if r2 and r2.get("publish_id"):
                r2["kind"] = "draft"
            return r2
        return r

    init = _attempt(access_token)

    # Access token expirado (24h) → refrescar y reintentar
    if (init and not init.get("publish_id")) and not tried_refresh and any(
        k in (init.get("error_code", "") + init.get("error_message", "")).lower()
        for k in ("access_token_invalid", "unauthorized", "expired")
    ):
        print("  tt: access_token caducado, refrescando…")
        new_token = _refresh_access_token()
        tried_refresh = True
        if new_token:
            init = _attempt(new_token)
            access_token = new_token

    if not init or not init.get("publish_id") or not init.get("upload_url"):
        print(f"  tt: ❌ init falló — {str(init)[:200]}")
        return None

    # Subir chunks
    ok = _upload_chunks(
        local_mp4,
        init["upload_url"],
        init.get("chunk_size", CHUNK_SIZE),
        init.get("total_chunks", 1),
    )
    if not ok:
        print("  tt: ❌ upload de chunks falló")
        return None

    # Poll status para confirmar procesamiento
    status = _poll_status(access_token, init["publish_id"])
    kind = init.get("kind", mode)
    if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
        print(f"  tt: ✅ {kind} → publish_id={init['publish_id']} status={status}")
        return {"publish_id": init["publish_id"], "kind": kind, "status": status}

    # Chunks subidos pero status no confirmado — no aborto: TikTok puede tardar
    # en procesar, el video normalmente aparece igualmente en drafts/feed.
    print(f"  tt: ⚠️ {kind} subido pero status={status} (probablemente OK igual)")
    return {"publish_id": init["publish_id"], "kind": kind, "status": status or "unknown"}
