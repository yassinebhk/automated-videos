"""Auto-poster de Instagram Reels via Meta Graph API.

Por qué IG: audiencia masiva en España (12M usuarios activos ES). Reels es el
formato prioritario del algoritmo de IG desde 2023 → mismos shorts verticales
9:16 que ya generamos funcionan directo. Zero re-encoding.

Setup one-time (15 min):
1. facebook.com/business/tools/meta-business-suite → conectar tu FB Page
2. La cuenta IG debe ser "Business" o "Creator" (no personal) — cambio gratis
   en la app IG: Ajustes → Cuenta → Cambiar a cuenta profesional.
3. developers.facebook.com/apps → Create App (type: Business)
4. Add Product: "Instagram" → habilitar Instagram Graph API
5. Generar long-lived access token (60 días, auto-refresh vía cron):
   - Marca los permisos: instagram_content_publish, instagram_basic,
     pages_show_list, pages_read_engagement
6. Obtener el INSTAGRAM_BUSINESS_ACCOUNT_ID (via Graph Explorer o script)
7. Añadir a GitHub Secrets:
   - IG_ACCESS_TOKEN (long-lived, ~60 días)
   - IG_BUSINESS_ACCOUNT_ID

Después: cada Short YT se publica también como Reel en IG con la misma
descripción + hashtags. Rate limit: 25 posts/día = suficiente.

NOTA: IG requiere que el video esté HOSTED en una URL pública. Usamos el
mismo host de GitHub Pages que el podcast (docs/reels/<id>.mp4) para servir
los archivos. El video es <100MB por Short, no impacta.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

from .config import ROOT


IG_LOG_PATH = ROOT / "output" / "ig_publish_log.json"


def _append_ig_log(entry: dict) -> None:
    """Registra intento IG en output/ig_publish_log.json (últimos 100).

    Sin esto no hay forma de saber por qué falla IG sin bucear en logs GH.
    """
    try:
        IG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if IG_LOG_PATH.exists():
            log = json.loads(IG_LOG_PATH.read_text(encoding="utf-8"))
        else:
            log = []
        entry["ts"] = datetime.now(timezone.utc).isoformat()
        log.append(entry)
        log = log[-100:]
        IG_LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False),
                                encoding="utf-8")
    except Exception as e:
        print(f"  ig: log write failed: {e}")


REELS_HOST_DIR = ROOT / "docs" / "reels"
# GitHub Pages sirve docs/ como https://<user>.github.io/<repo>/
# CT correcto (video/mp4), sin rate-limit al User-Agent de Meta.
# jsDelivr devolvía 403 Forbidden al fetch de Meta (User-Agent bloqueado).
# GH Pages es más confiable para IG API. Espera 60s para que Pages
# rebuilde tras push.
PUBLIC_REELS_BASE = "https://yassinebhk.github.io/automated-videos/reels"

# Instagram Business Login usa graph.instagram.com (v21+).
# El endpoint clásico graph.facebook.com/v21.0 es para "Facebook Login for
# Business" — otra ruta, otro token. Nosotros usamos IG Business Login.
IG_API_BASE = "https://graph.instagram.com/v21.0"


def _reencode_for_ig(local_mp4: Path, dest: Path) -> bool:
    """Re-encode strict H.264 + AAC + trim ≤90s para cumplir specs IG Reels 2026.

    IG rechaza silenciosamente (container ERROR sin detalle) videos que no
    tengan codec H.264 + audio AAC exactos. Kokoro/ffmpeg output puede
    variar. Este re-encode garantiza compatibilidad.
    """
    import subprocess
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(local_mp4),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-t", "89",  # cap 89s (IG max 90s)
        "-movflags", "+faststart",  # streaming-friendly
        str(dest),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"  ig re-encode fail: {r.stderr[-300:]}")
        return False
    return dest.exists() and dest.stat().st_size > 10000


def _prepare_public_reel(local_mp4: Path, slug: str) -> Optional[str]:
    """Re-encode strict IG + copia a docs/reels/<slug>.mp4, commit + push
    para que jsDelivr lo sirva. Devuelve URL pública o None."""
    if not local_mp4.exists():
        return None
    REELS_HOST_DIR.mkdir(parents=True, exist_ok=True)
    dst = REELS_HOST_DIR / f"{slug}.mp4"
    # Re-encode STRICT antes de subir (fix container ERROR silencioso 2026).
    # Si el codec no es exactamente H.264+AAC, IG lo rechaza sin detalle.
    if _reencode_for_ig(local_mp4, dst):
        print(f"  ig: re-encoded H.264+AAC · {dst.stat().st_size//1024}KB")
    else:
        # Fallback: copia directa (mejor que abortar)
        print(f"  ig: re-encode falló, uso mp4 original")
        if not dst.exists() or dst.stat().st_size != local_mp4.stat().st_size:
            shutil.copy2(local_mp4, dst)

    # Commit + push del mp4 antes de que IG intente descargarlo. Silencioso
    # si falla — el flujo sigue y IG lo notificará como container ERROR.
    import subprocess
    try:
        subprocess.run(["git", "config", "user.name", "videogen-bot"],
                       cwd=ROOT, check=False, capture_output=True, timeout=10)
        subprocess.run(["git", "config", "user.email", "bot@videogen.local"],
                       cwd=ROOT, check=False, capture_output=True, timeout=10)
        subprocess.run(["git", "add", str(dst.relative_to(ROOT))],
                       cwd=ROOT, check=False, capture_output=True, timeout=10)
        r = subprocess.run(["git", "commit", "-m", f"reel: {slug} [skip ci]"],
                           cwd=ROOT, capture_output=True, timeout=15)
        if r.returncode == 0:
            # Push con reintentos (race con otros workflows que commitean)
            for _ in range(3):
                p = subprocess.run(["git", "pull", "--rebase", "origin", "main"],
                                    cwd=ROOT, capture_output=True, timeout=30)
                if p.returncode != 0:
                    continue
                p = subprocess.run(["git", "push", "origin", "HEAD:main"],
                                    cwd=ROOT, capture_output=True, timeout=30)
                if p.returncode == 0:
                    print(f"  ig: mp4 pushed → poll activo GH Pages")
                    # Poll GET (no HEAD) con Range: 0-1023 y User-Agent de Meta.
                    # HEAD 200 no garantiza GET 200 en todos los edges GH Pages
                    # (verificado 15/09 tras fail_container_ready 404: HEAD ok pero
                    # Meta ve 404 en su edge). Tras GET 200, sleep 30s para que
                    # todos los edges GH Pages propaguen antes de que Meta fetche.
                    url_check = f"{PUBLIC_REELS_BASE}/{dst.stem}.mp4"
                    headers_meta = {
                        "User-Agent": "facebookexternalhit/1.1",
                        "Range": "bytes=0-1023",
                    }
                    got_200 = False
                    for i in range(36):
                        time.sleep(10)
                        try:
                            r_check = requests.get(url_check, headers=headers_meta, timeout=15)
                            # 200 (rango completo servido) o 206 (partial content)
                            if r_check.status_code in (200, 206) and len(r_check.content) > 100:
                                print(f"  ig: ✓ GH Pages GET-Meta OK tras {(i+1)*10}s (rc={r_check.status_code}, {len(r_check.content)}b)")
                                got_200 = True
                                # Wait extra para que TODOS los edges propaguen
                                # (Meta fetcha desde CDN distinto al que sirvió al runner)
                                print(f"  ig: esperando 30s para propagación edge...")
                                time.sleep(30)
                                break
                        except Exception:
                            pass
                    if not got_200:
                        print(f"  ig: ⚠ GH Pages GET-Meta no OK tras 360s — IG probablemente fallará 404")
                    break
    except Exception as e:
        print(f"  ig: commit mp4 falló ({type(e).__name__}: {e}) — IG puede fallar")

    return f"{PUBLIC_REELS_BASE}/{slug}.mp4"


def _create_media_container(access_token: str, ig_account_id: str,
                             video_url: str, caption: str) -> Optional[str]:
    """Paso 1 de IG publish: subir el video a un container. Devuelve container_id."""
    r = requests.post(
        f"{IG_API_BASE}/{ig_account_id}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption[:2200],  # límite IG
            "share_to_feed": "true",
            "access_token": access_token,
        }, timeout=60,
    )
    data = r.json()
    if r.status_code != 200 or "id" not in data:
        print(f"  ig: container fail {r.status_code} — {str(data)[:200]}")
        return None
    return data["id"]


# Módulo-level: último error de container para pasar al log persistente.
_LAST_CONTAINER_ERROR: dict = {}


def _wait_container_ready(access_token: str, container_id: str, max_wait: int = 240) -> bool:
    """IG procesa el video en su lado. Esperar hasta status=FINISHED.

    IG puede fallar por: URL no fetchable, video mal formateado, aspect
    ratio wrong. Logueamos toda la respuesta para diagnosticar. Guarda
    el detalle en _LAST_CONTAINER_ERROR para persistir en ig_publish_log.
    """
    global _LAST_CONTAINER_ERROR
    _LAST_CONTAINER_ERROR = {}
    start = time.time()
    last_status = None
    poll_count = 0
    while time.time() - start < max_wait:
        r = requests.get(
            f"{IG_API_BASE}/{container_id}",
            params={"fields": "status_code,status,error_message",
                    "access_token": access_token},
            timeout=20,
        )
        d = r.json()
        st = d.get("status_code", "").upper()
        poll_count += 1
        if last_status is None or st != last_status or (poll_count % 12 == 0):
            elapsed = int(time.time() - start)
            print(f"  ig: status@{elapsed}s = {st or '(vacío)'} · full={str(d)[:500]}")
            last_status = st
        if st == "FINISHED":
            return True
        if st == "ERROR":
            ext_status = d.get("status", "")
            err_msg = d.get("error_message", "")
            print(f"  ig: container ERROR · status='{ext_status}' · error_message='{err_msg}' · full={d}")
            _LAST_CONTAINER_ERROR = {
                "status_ext": ext_status[:200],
                "error_message": err_msg[:250],
                "full": str(d)[:400],
            }
            return False
        time.sleep(5)
    print(f"  ig: container timeout tras {max_wait}s")
    _LAST_CONTAINER_ERROR = {"error_message": f"timeout {max_wait}s waiting FINISHED"}
    return False


def _publish_container(access_token: str, ig_account_id: str, container_id: str) -> Optional[str]:
    """Paso 2: publicar el container. Devuelve media_id."""
    r = requests.post(
        f"{IG_API_BASE}/{ig_account_id}/media_publish",
        params={"creation_id": container_id, "access_token": access_token},
        timeout=30,
    )
    d = r.json()
    if r.status_code != 200:
        print(f"  ig: publish fail {r.status_code} — {str(d)[:200]}")
        return None
    return d.get("id")


def post_reel_to_instagram(video_title: str, video_url: str,
                            local_mp4: Path, slug: str,
                            teaser: str = "", dry_run: bool = False) -> dict[str, Any] | None:
    """Publica un Reel en IG. Requiere que el video esté disponible en URL
    pública — lo copiamos a docs/reels/<slug>.mp4 que sirve GH Pages.
    """
    # IG_TOKEN + IG_USER_ID vienen del setup con Instagram Business Login
    # (developers.facebook.com → app → Instagram → API setup). Los nombres
    # legacy IG_ACCESS_TOKEN + IG_BUSINESS_ACCOUNT_ID se mantienen como
    # fallback por si el entorno los tiene con la nomenclatura antigua.
    access_token = os.environ.get("IG_TOKEN") or os.environ.get("IG_ACCESS_TOKEN")
    ig_account_id = os.environ.get("IG_USER_ID") or os.environ.get("IG_BUSINESS_ACCOUNT_ID")
    if not (access_token and ig_account_id):
        missing = []
        if not access_token: missing.append("IG_TOKEN")
        if not ig_account_id: missing.append("IG_USER_ID")
        print(f"  ig: skip — faltan {'+'.join(missing)}")
        _append_ig_log({"slug": slug, "title": video_title[:80],
                         "status": "skip_no_token", "missing": missing})
        try:
            from .notify_batch import add
            add(f"⚠️ <b>IG skip · {slug}</b> — faltan GH Secrets: {' + '.join(missing)}",
                urgent=True)
        except Exception:
            pass
        return None

    from . import social_post
    # include_url=False: IG algoritmo esconde posts con links externos (YT).
    caption, _ = social_post.build_viral_post(
        video_title, video_url, teaser=teaser, cross_platform="",
        include_url=False,
    )
    # IG permite hasta 30 hashtags — nuestro build_viral_post ya los mete
    caption = caption[:2200]

    if dry_run:
        print(f"  ig DRY-RUN — {len(caption)} chars:\n{caption}")
        return {"dry_run": True, "caption": caption}

    # 1) Copiar mp4 a docs/reels/ para servir vía GH Pages
    public_url = _prepare_public_reel(local_mp4, slug)
    if not public_url:
        print(f"  ig: no local mp4 → {local_mp4}")
        _append_ig_log({"slug": slug, "title": video_title[:80],
                         "status": "fail_no_mp4"})
        return None

    # 2+3) Container + wait ready, con retry si Meta devuelve 404 URL.
    # GH Pages tiene edges asincronos: mi GET desde runner puede ver 200
    # pero el edge que Meta usa aún tener 404. Retry con espera 60s
    # entre intentos deja tiempo a que TODOS los edges propaguen.
    container_id = None
    for attempt in range(3):
        container_id = _create_media_container(access_token, ig_account_id, public_url, caption)
        if not container_id:
            print(f"  ig: retry {attempt+1}/3 — container_create devolvió None")
            time.sleep(60)
            continue

        if _wait_container_ready(access_token, container_id):
            break  # FINISHED — sigue a publish

        # Container ERROR — mira si fue 404. Si sí, retry con container nuevo.
        err_msg = _LAST_CONTAINER_ERROR.get("error_message", "").lower()
        is_404 = "404" in err_msg or "not found" in err_msg or "media could not be fetched" in err_msg
        if is_404 and attempt < 2:
            print(f"  ig: retry {attempt+1}/3 tras 404 URL — esperando 60s propagación edges Meta")
            time.sleep(60)
            container_id = None
            continue
        # Error no-404 (aspect ratio, codec, etc) → no retry, propagar fallo
        _append_ig_log({"slug": slug, "title": video_title[:80],
                         "status": "fail_container_ready",
                         "container_id": container_id,
                         "public_url": public_url,
                         "attempts": attempt + 1,
                         **_LAST_CONTAINER_ERROR})
        return None
    else:
        # 3 intentos agotados sin FINISHED
        _append_ig_log({"slug": slug, "title": video_title[:80],
                         "status": "fail_container_retries_exhausted",
                         "public_url": public_url,
                         **_LAST_CONTAINER_ERROR})
        return None

    # 4) Publish
    media_id = _publish_container(access_token, ig_account_id, container_id)
    if not media_id:
        _append_ig_log({"slug": slug, "title": video_title[:80],
                         "status": "fail_publish",
                         "container_id": container_id})
        return None

    url = f"https://instagram.com/reel/{media_id}"
    print(f"  ig: ✅ Reel published → {url}")
    _append_ig_log({"slug": slug, "title": video_title[:80],
                     "status": "ok", "media_id": media_id, "url": url})
    return {"media_id": media_id, "url": url, "caption": caption}
