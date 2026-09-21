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


# Guarda el último intento catbox para diagnóstico persistente
_LAST_CATBOX_STATUS: str = ""


def _upload_to_catbox(mp4_path: Path) -> Optional[str]:
    """Sube mp4 a catbox.moe (anónimo, sin API key, propagación instantánea).

    Retorna URL directa `https://files.catbox.moe/xxxxxx.mp4` o None si falla.
    Elimina el problema de propagación edge de GH Pages verificado 15-16/09.
    Límite catbox: 200MB/archivo. Nuestros mp4 ≤30MB, dentro de sobra.

    Guarda _LAST_CATBOX_STATUS para diagnóstico (status + body[:200]).
    """
    global _LAST_CATBOX_STATUS
    _LAST_CATBOX_STATUS = ""
    try:
        size_kb = mp4_path.stat().st_size // 1024
        print(f"  ig: catbox attempting upload {mp4_path.name} ({size_kb}KB)")
        with open(mp4_path, "rb") as f:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (mp4_path.name, f, "video/mp4")},
                timeout=120,
            )
        body = r.text.strip() if r.text else ""
        _LAST_CATBOX_STATUS = f"rc={r.status_code} body={body[:200]}"
        if r.status_code == 200 and body.startswith("https://"):
            print(f"  ig: catbox OK → {body} ({size_kb}KB)")
            return body
        print(f"  ig: catbox FAIL {_LAST_CATBOX_STATUS}")
        return None
    except requests.exceptions.Timeout:
        _LAST_CATBOX_STATUS = "timeout 120s"
        print(f"  ig: catbox timeout tras 120s")
        return None
    except Exception as e:
        _LAST_CATBOX_STATUS = f"exception {type(e).__name__}: {str(e)[:150]}"
        print(f"  ig: catbox {_LAST_CATBOX_STATUS}")
        return None


def _upload_to_litterbox(mp4_path: Path) -> Optional[str]:
    """2º host: litterbox (host temporal de catbox, dominio distinto litter.catbox.moe,
    72h). Sirve el archivo directo y responde 206 al fetcher de Meta (verificado 20/09).
    (0x0.st descartado: desactivó subidas; tmpfiles.org sirve HTML, no el archivo.)"""
    try:
        size_kb = mp4_path.stat().st_size // 1024
        print(f"  ig: litterbox attempting upload {mp4_path.name} ({size_kb}KB)")
        with open(mp4_path, "rb") as f:
            r = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={"reqtype": "fileupload", "time": "72h"},
                files={"fileToUpload": (mp4_path.name, f, "video/mp4")},
                timeout=120,
            )
        body = (r.text or "").strip()
        if r.status_code == 200 and body.startswith("https://"):
            print(f"  ig: litterbox OK → {body}")
            return body
        print(f"  ig: litterbox FAIL rc={r.status_code} body={body[:120]}")
        return None
    except Exception as e:
        print(f"  ig: litterbox exception {type(e).__name__}: {str(e)[:120]}")
        return None


def _verify_meta_fetchable(url: str, tries: int = 6, wait: int = 5) -> bool:
    """Comprueba que Meta (facebookexternalhit) puede DESCARGAR la URL antes de crear
    el contenedor → evita 'fail_container_ready'. GET con Range 0-1023 + UA de Meta,
    reintentando por si el host tarda en propagar."""
    headers = {"User-Agent": "facebookexternalhit/1.1", "Range": "bytes=0-1023"}
    for i in range(tries):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            n = len(r.content or b"")
            if r.status_code in (200, 206) and n > 100:
                print(f"  ig: verify Meta OK '{url}' (rc={r.status_code}, {n}b) intento {i+1}")
                return True
            print(f"  ig: verify no-OK rc={r.status_code} n={n} intento {i+1}")
        except Exception as e:
            print(f"  ig: verify error {str(e)[:60]} intento {i+1}")
        time.sleep(wait)
    return False


def _prepare_public_reel(local_mp4: Path, slug: str) -> Optional[str]:
    """Re-encode strict IG + sube a catbox.moe. Retorna URL pública o None.

    16/09/26: cambio arquitectura. Antes usábamos docs/reels/ + GH Pages,
    pero la propagación asíncrona de edges GH causaba 40% fails IG por
    404. Catbox propaga instantáneo (single origin, sin edges) → 0 espera.
    Ademas elimina 3GB de basura de docs/reels/ (crecía sin control).

    Fallback a GH Pages si catbox falla (protege contra caída del servicio).
    """
    if not local_mp4.exists():
        return None

    # Re-encode primero a un archivo temporal (compatible IG H.264+AAC, ≤89s)
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp(prefix="ig_reel_"))
    encoded = tmp_dir / f"{slug}.mp4"
    if _reencode_for_ig(local_mp4, encoded):
        print(f"  ig: re-encoded H.264+AAC · {encoded.stat().st_size//1024}KB")
        mp4_to_upload = encoded
    else:
        # Fallback: ffmpeg stream-copy con -t 89 (rápido, sin re-encode)
        print(f"  ig: re-encode falló, intento stream-copy con trim 89s")
        import subprocess as _sp
        r_copy = _sp.run(
            ["ffmpeg", "-y", "-i", str(local_mp4),
             "-c", "copy", "-t", "89", "-movflags", "+faststart", str(encoded)],
            capture_output=True, text=True, timeout=60,
        )
        if r_copy.returncode == 0 and encoded.exists() and encoded.stat().st_size > 10000:
            print(f"  ig: stream-copy OK · {encoded.stat().st_size//1024}KB")
            mp4_to_upload = encoded
        else:
            print(f"  ig: stream-copy falló, uso mp4 original")
            mp4_to_upload = local_mp4

    # 1) Hosts instantáneos CON VERIFICACIÓN de que Meta puede descargar (fix
    # fail_container_ready 20/09): sube → comprueba con facebookexternalhit → úsalo
    # solo si sirve. Antes se creaba el contenedor sin verificar → 61% fallos.
    for host_name, host_fn in (("catbox", _upload_to_catbox), ("litterbox", _upload_to_litterbox)):
        hurl = host_fn(mp4_to_upload)
        if not hurl:
            continue
        if _verify_meta_fetchable(hurl):
            print(f"  ig: host {host_name} verificado por Meta ✓")
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
            return hurl
        print(f"  ig: host {host_name} subió pero NO verifica para Meta → siguiente host")

    # 2) Fallback: GH Pages (con su propio poll de verificación)
    print(f"  ig: hosts instantáneos no verificaron, fallback a GH Pages")
    REELS_HOST_DIR.mkdir(parents=True, exist_ok=True)
    dst = REELS_HOST_DIR / f"{slug}.mp4"
    shutil.copy2(mp4_to_upload, dst)
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

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


def _cap_hashtags(text: str, n: int = 5) -> str:
    """Deja como máximo n hashtags (Meta 2026 penaliza el exceso)."""
    import re as _re
    seen = [0]
    def _r(m):
        seen[0] += 1
        return m.group(0) if seen[0] <= n else ""
    out = _re.sub(r"#\w+", _r, text)
    return _re.sub(r"[ \t]{2,}", " ", out).strip()


def _ig_creds():
    """Creds IG por canal (IG_<SUFIJO>_TOKEN/USER_ID via YT_CHANNEL_PREFIX),
    con fallback a la cuenta compartida IG_TOKEN/IG_USER_ID."""
    prefix = os.environ.get("YT_CHANNEL_PREFIX", "").strip()
    if prefix.startswith("YT_"):
        suf = prefix[3:]
        tok = os.environ.get(f"IG_{suf}_TOKEN")
        uid = os.environ.get(f"IG_{suf}_USER_ID")
        if tok and uid:
            return tok, uid
    return (os.environ.get("IG_TOKEN") or os.environ.get("IG_ACCESS_TOKEN"),
            os.environ.get("IG_USER_ID") or os.environ.get("IG_BUSINESS_ACCOUNT_ID"))


def _upload_resumable(access_token: str, ig_account_id: str,
                      local_mp4: Path, caption: str) -> Optional[str]:
    """Sube el vídeo por BYTES directos a Meta (Resumable Upload Protocol) → SIN URL
    pública. Elimina el 'fail_container_ready' por fetch (que dejaba IG a ~50%).
    Devuelve container_id (a la espera de FINISHED) o None → cae al flujo URL."""
    import subprocess as _sp
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp(prefix="ig_ru_"))
    enc = tmp_dir / "reel.mp4"
    try:
        # Re-encode compatible IG (H.264+AAC, ≤89s), igual que el flujo URL
        if not _reencode_for_ig(local_mp4, enc):
            r = _sp.run(["ffmpeg", "-y", "-i", str(local_mp4), "-c", "copy", "-t", "89",
                         "-movflags", "+faststart", str(enc)],
                        capture_output=True, text=True, timeout=60)
            if not (r.returncode == 0 and enc.exists() and enc.stat().st_size > 10000):
                enc = local_mp4
        size = enc.stat().st_size
        # 1) crear contenedor en modo resumable → devuelve id + uri de subida
        r = requests.post(
            f"{IG_API_BASE}/{ig_account_id}/media",
            params={"media_type": "REELS", "upload_type": "resumable",
                    "caption": caption[:2200], "share_to_feed": "true",
                    "access_token": access_token}, timeout=60,
        )
        d = r.json() if r.content else {}
        cid, uri = d.get("id"), d.get("uri")
        if not (cid and uri):
            print(f"  ig: resumable container fail {r.status_code} — {str(d)[:200]}")
            return None
        # 2) subir los bytes al uri (Authorization: OAuth <token>, offset+file_size)
        with open(enc, "rb") as f:
            up = requests.post(uri, headers={"Authorization": f"OAuth {access_token}",
                                             "offset": "0", "file_size": str(size)},
                               data=f, timeout=300)
        try:
            upj = up.json()
        except Exception:
            upj = {}
        if up.status_code == 200 and (upj.get("success") in (True, "true", 1) or upj.get("id")):
            print(f"  ig: resumable bytes subidos OK ({size//1024}KB) → container {cid}")
            return cid
        print(f"  ig: resumable upload fail {up.status_code} — {str(upj)[:200]}")
        return None
    except Exception as e:
        print(f"  ig: resumable exception {type(e).__name__}: {str(e)[:150]}")
        return None
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def post_reel_to_instagram(video_title: str, video_url: str,
                            local_mp4: Path, slug: str,
                            teaser: str = "", caption_override: str = "", dry_run: bool = False) -> dict[str, Any] | None:
    """Publica un Reel en IG. Requiere que el video esté disponible en URL
    pública — lo copiamos a docs/reels/<slug>.mp4 que sirve GH Pages.
    """
    # DEDUP CRÍTICO 18/09/26: bug detectado — mi retry lógica creaba
    # 2 containers Meta cuando el primer timeout parecía fail pero Meta
    # ya había publicado. Resultado: mismo slug subido 2× (verificado
    # padel_back_wall en 23s, top-5-ai-transcription-tools en 69s).
    # Fix: si slug ya está en log como 'ok' en últimas 48h → skip.
    try:
        if IG_LOG_PATH.exists():
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            log_data = json.loads(IG_LOG_PATH.read_text(encoding="utf-8"))
            cutoff = _dt.now(_tz.utc) - _td(hours=48)
            for _entry in reversed(log_data[-200:]):  # solo últimos 200
                if _entry.get("slug") != slug or _entry.get("status") != "ok":
                    continue
                try:
                    _ts = _dt.fromisoformat(_entry.get("ts", ""))
                    if _ts > cutoff:
                        print(f"  ig: DEDUP skip — {slug} ya publicado {_ts.isoformat()[:16]} → {_entry.get('url')}")
                        return {"media_id": _entry.get("media_id"),
                                "url": _entry.get("url"),
                                "dedup_skip": True}
                except Exception:
                    pass
    except Exception as _e:
        print(f"  ig: dedup check falló ({_e}), sigue publicación normal")

    # IG_TOKEN + IG_USER_ID vienen del setup con Instagram Business Login
    # (developers.facebook.com → app → Instagram → API setup). Los nombres
    # legacy IG_ACCESS_TOKEN + IG_BUSINESS_ACCOUNT_ID se mantienen como
    # fallback por si el entorno los tiene con la nomenclatura antigua.
    access_token, ig_account_id = _ig_creds()
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
    if caption_override:
        caption = caption_override
    else:
        caption, _ = social_post.build_viral_post(
            video_title, video_url, teaser=teaser, cross_platform="",
            include_url=False,
        )
    # Meta 2026: máx ~5 hashtags relevantes (más = señal de spam/shadowban)
    caption = _cap_hashtags(caption, 5)[:2200]

    if dry_run:
        print(f"  ig DRY-RUN — {len(caption)} chars:\n{caption}")
        return {"dry_run": True, "caption": caption}

    # 🚀 PRIMARIO (21/09): Resumable Upload — bytes directos a Meta, SIN URL pública.
    # Elimina el fail_container_ready por fetch (que dejaba IG a ~50%). Si funciona,
    # publica y retorna aquí; si no, cae al flujo de URL pública de abajo (intacto).
    _ru_cid = _upload_resumable(access_token, ig_account_id, local_mp4, caption)
    if _ru_cid and _wait_container_ready(access_token, _ru_cid):
        _mid = _publish_container(access_token, ig_account_id, _ru_cid)
        if _mid:
            _url = f"https://instagram.com/reel/{_mid}"
            print(f"  ig: ✅ Reel publicado (resumable, sin URL) → {_url}")
            _append_ig_log({"slug": slug, "title": video_title[:80], "status": "ok",
                            "media_id": _mid, "url": _url, "via": "resumable"})
            return {"media_id": _mid, "url": _url, "caption": caption}
        print("  ig: resumable llegó a FINISHED pero publish falló → fallback URL")
    elif _ru_cid:
        print("  ig: resumable no llegó a FINISHED → fallback URL")

    # 1) Copiar mp4 a docs/reels/ para servir vía GH Pages
    public_url = _prepare_public_reel(local_mp4, slug)
    if not public_url:
        print(f"  ig: no local mp4 → {local_mp4}")
        _append_ig_log({"slug": slug, "title": video_title[:80],
                         "status": "fail_no_mp4"})
        return None

    # 2+3) Container + wait ready, con backoff exponencial si Meta devuelve
    # 404 URL. Antes: 3×60s (3 min total) insuficiente cuando GH Pages
    # está saturado por 4+ pushes/min. Ahora backoff 60→120→240→300s
    # = 13min total. Tras 4 intentos si sigue 404 → hoisting a backfill
    # nocturno (el mp4 ya está en docs/reels/, el backfill lo reintenta
    # tras horas cuando propagación garantizada).
    container_id = None
    backoff = [60, 120, 240, 300]  # segundos entre intentos
    for attempt in range(len(backoff)):
        container_id = _create_media_container(access_token, ig_account_id, public_url, caption)
        if not container_id:
            print(f"  ig: retry {attempt+1}/{len(backoff)} — container_create devolvió None")
            time.sleep(backoff[attempt])
            continue

        if _wait_container_ready(access_token, container_id):
            break  # FINISHED — sigue a publish

        # Container ERROR — mira si fue 404. Si sí, retry con container nuevo.
        err_msg = _LAST_CONTAINER_ERROR.get("error_message", "").lower()
        is_404 = "404" in err_msg or "not found" in err_msg or "media could not be fetched" in err_msg
        is_timeout = "timeout" in err_msg
        # ANTI-DUPLICADO 18/09: si es timeout (no 404 real), Meta puede haber
        # terminado tras nuestro timeout local. Intentar publicar el container
        # actual ANTES de crear otro (evita bug: mismo slug subido 2× en 23s).
        if is_timeout:
            print(f"  ig: timeout local — intento publish del container actual antes de retry")
            _media_id_try = _publish_container(access_token, ig_account_id, container_id)
            if _media_id_try:
                # ✅ Se publicó — evita duplicado saltando al bloque publish
                container_id = container_id  # keep for sig below
                break  # sale del loop, va al bloque publish que reusa container_id
        if (is_404 or is_timeout) and attempt < len(backoff) - 1:
            wait_s = backoff[attempt]
            print(f"  ig: retry {attempt+1}/{len(backoff)} tras {'404' if is_404 else 'timeout'} — espera {wait_s}s (backoff)")
            time.sleep(wait_s)
            container_id = None
            continue
        # Error no-404 (aspect ratio, codec, etc) → no retry, propagar fallo
        _append_ig_log({"slug": slug, "title": video_title[:80],
                         "status": "fail_container_ready",
                         "container_id": container_id,
                         "public_url": public_url,
                         "attempts": attempt + 1,
                         "catbox_status": _LAST_CATBOX_STATUS,
                         **_LAST_CONTAINER_ERROR})
        return None
    else:
        # 4 intentos agotados sin FINISHED
        _append_ig_log({"slug": slug, "title": video_title[:80],
                         "status": "fail_container_retries_exhausted",
                         "public_url": public_url,
                         "attempts": len(backoff),
                         "catbox_status": _LAST_CATBOX_STATUS,
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
