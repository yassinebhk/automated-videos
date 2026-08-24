"""Auto-poster de TikTok via Content Posting API v2.

Por qué TikTok: la red donde el algoritmo empuja más contenido nuevo sin
followers previos. Shorts verticales 9:16 (mismos que YT) funcionan directo.
Zero re-encoding.

Setup one-time:
1. developers.tiktok.com → registrar developer (SMS verify)
2. Manage Apps → Create App:
   - Products: Login Kit + Content Posting API
   - Terms/Privacy: cdn.jsdelivr.net/.../docs/legal/{tos,privacy}.html
3. Configurar Login Kit → Redirect URI: {VERCEL}/api/tiktok-callback
4. Configurar Content Posting API:
   - Scope: video.upload (immediate)
   - Scope: video.publish (requiere app review 2-4 sem)
   - URL Properties → añadir dominio confiable: cdn.jsdelivr.net
5. Anotar Client Key + Client Secret → Vercel env:
   - TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET
6. Iniciar OAuth desde el bot Telegram (o directo a {VERCEL}/api/tiktok-auth?t=<chat_id>)
   → callback guarda automáticamente:
   - TIKTOK_ACCESS_TOKEN
   - TIKTOK_REFRESH_TOKEN (24h TTL access, 365d TTL refresh)
   - TIKTOK_OPEN_ID

Modos:
- **Direct** (video.publish aprobado): publica al feed inmediatamente.
- **Draft** (solo video.upload): video llega a bandeja de borradores del user,
  publica manualmente 3 taps desde app TikTok móvil.

Auto-detección: intenta direct primero, si TikTok responde con scope error
cae a inbox. Se puede forzar con env TIKTOK_MODE=direct|draft.

NOTA: TikTok PULL_FROM_URL requiere que el dominio esté registrado en el app
como "URL property" verificada. cdn.jsdelivr.net funciona porque jsDelivr
sirve HTTPS con headers CORS abiertos.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any, Optional

import requests

from .config import ROOT


TT_HOST_DIR = ROOT / "docs" / "reels"  # mismo dir que IG — reusa
PUBLIC_TT_BASE = "https://cdn.jsdelivr.net/gh/yassinebhk/automated-videos@main/docs/reels"

TT_API = "https://open.tiktokapis.com/v2"


def _prepare_public_url(local_mp4: Path, slug: str) -> Optional[str]:
    """Copia el mp4 a docs/reels/<slug>.mp4 (compartido con IG)."""
    if not local_mp4.exists():
        return None
    TT_HOST_DIR.mkdir(parents=True, exist_ok=True)
    dst = TT_HOST_DIR / f"{slug}.mp4"
    if not dst.exists() or dst.stat().st_size != local_mp4.stat().st_size:
        shutil.copy2(local_mp4, dst)
    return f"{PUBLIC_TT_BASE}/{slug}.mp4"


def _refresh_access_token() -> Optional[str]:
    """Refresca el access_token usando el refresh_token. Devuelve el nuevo
    access_token o None si falla. Los access tokens de TikTok expiran en 24h,
    los refresh en 365 días.
    """
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


def _direct_post(access_token: str, video_url: str, title: str) -> Optional[dict]:
    """Publica directo al feed. Requiere scope video.publish (aprobado)."""
    r = requests.post(
        f"{TT_API}/post/publish/video/init/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "post_info": {
                "title": title[:150],
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video_url,
            },
        },
        timeout=60,
    )
    return _handle_init_response(r, kind="direct")


def _draft_upload(access_token: str, video_url: str) -> Optional[dict]:
    """Upload a bandeja de borradores. Solo requiere scope video.upload."""
    r = requests.post(
        f"{TT_API}/post/publish/inbox/video/init/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video_url,
            },
        },
        timeout=60,
    )
    return _handle_init_response(r, kind="draft")


def _handle_init_response(r: requests.Response, kind: str) -> Optional[dict]:
    try:
        d = r.json()
    except Exception:
        print(f"  tt: {kind} respuesta no-JSON {r.status_code} — {r.text[:200]}")
        return None
    err_code = ((d.get("error") or {}).get("code") or "").lower()
    err_msg = ((d.get("error") or {}).get("message") or "")
    if r.status_code != 200 or err_code not in ("", "ok"):
        print(f"  tt: {kind} fail {r.status_code} — code={err_code} msg={err_msg[:200]}")
        return {"error_code": err_code, "error_message": err_msg}
    data = d.get("data") or {}
    return {"publish_id": data.get("publish_id"), "raw": d}


def post_video_to_tiktok(video_title: str, local_mp4: Path, slug: str,
                          dry_run: bool = False) -> dict[str, Any] | None:
    """Sube un video a TikTok — direct al feed si scope aprobado, si no draft.

    Prep: copia el mp4 a docs/reels/ (compartido con IG) para servir vía
    jsDelivr → TikTok hace PULL_FROM_URL desde ahí.
    """
    access_token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if not access_token:
        print("  tt: skip — falta TIKTOK_ACCESS_TOKEN")
        return None

    mode = (os.environ.get("TIKTOK_MODE") or "auto").lower()

    if dry_run:
        print(f"  tt DRY-RUN — modo={mode}, title={video_title[:80]}")
        return {"dry_run": True, "mode": mode, "title": video_title}

    public_url = _prepare_public_url(local_mp4, slug)
    if not public_url:
        print(f"  tt: no local mp4 → {local_mp4}")
        return None

    # Espera ~30s para que jsDelivr propague el fichero recién commited.
    # (jsDelivr cachea GitHub raw; nuevos ficheros tardan segundos en aparecer.)
    time.sleep(3)

    tried_refresh = False

    def _attempt(token: str) -> Optional[dict]:
        if mode == "direct":
            return _direct_post(token, public_url, video_title)
        if mode == "draft":
            return _draft_upload(token, public_url)
        # auto: prueba direct → si scope insuficiente cae a draft
        r = _direct_post(token, public_url, video_title)
        if r and r.get("publish_id"):
            return {**r, "kind": "direct"}
        if r and ("scope" in (r.get("error_code", "") + r.get("error_message", "")).lower()
                  or "unauthorized" in (r.get("error_code", "") + r.get("error_message", "")).lower()):
            print("  tt: direct sin scope aprobado, fallback a draft")
            r2 = _draft_upload(token, public_url)
            if r2:
                r2["kind"] = "draft"
            return r2
        return r

    resp = _attempt(access_token)

    # Si error de autenticación (access_token expirado 24h), refresca y reintenta.
    if resp and not resp.get("publish_id") and any(
        k in (resp.get("error_code", "") + resp.get("error_message", "")).lower()
        for k in ("access_token_invalid", "unauthorized", "expired")
    ) and not tried_refresh:
        print("  tt: access_token caducado, refrescando…")
        new_token = _refresh_access_token()
        tried_refresh = True
        if new_token:
            resp = _attempt(new_token)

    if not resp or not resp.get("publish_id"):
        print(f"  tt: ❌ upload falló — {str(resp)[:200]}")
        return None

    kind = resp.get("kind", mode)
    print(f"  tt: ✅ enviado ({kind}) → publish_id={resp['publish_id']}")
    return {"publish_id": resp["publish_id"], "kind": kind}
