"""Backfill de top-performers YT a TikTok + Instagram + Threads.

Estrategia: reciclar los Shorts que rindieron mejor en YT en las nuevas
redes (TT/IG/Threads) para amortizar el contenido y acelerar crecimiento
sin gastar cuota Gemini regenerando.

Flujo:
1. Escaneo `output/uploaded/*/youtube.json` para mapear slug → video_id.
2. Cruzo con `output/stats_history.jsonl` para obtener views actuales
   de cada slug. Uso la ÚLTIMA lectura por video_id (los stats son
   snapshots temporales).
3. Ordeno por views desc, filtro los ya reposteados a cada plataforma
   consultando `output/backfill_log.json`.
4. Cross-posteo N videos por corrida. Rate-limit natural: la fn poster
   ya trae sleeps + control 429 → basta con no pasar de 3/día por red.

El ledger `output/backfill_log.json` es autoritativo: si por lo que sea
un post se cae, no se marca en el ledger y en la siguiente corrida
reintentará. Idempotente.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .config import ROOT, UPLOADED_DIR


BACKFILL_LOG = ROOT / "output" / "backfill_log.json"
STATS_HISTORY = ROOT / "output" / "stats_history.jsonl"


def _load_ledger() -> dict[str, dict[str, str]]:
    """{ slug: { platform: iso_timestamp } } — plataformas ya reposteadas."""
    if not BACKFILL_LOG.exists():
        return {}
    try:
        return json.loads(BACKFILL_LOG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_ledger(data: dict[str, dict[str, str]]) -> None:
    BACKFILL_LOG.parent.mkdir(parents=True, exist_ok=True)
    BACKFILL_LOG.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")


def _map_slug_to_video_id() -> dict[str, str]:
    """slug → YT video_id (Shorts). Ignora long-forms."""
    out: dict[str, str] = {}
    for slug_dir in UPLOADED_DIR.glob("*"):
        if not slug_dir.is_dir():
            continue
        yt_json = slug_dir / "youtube.json"
        if not yt_json.exists():
            continue  # sin YT metadata (probablemente long-form solo)
        try:
            data = json.loads(yt_json.read_text(encoding="utf-8"))
            vid = (data.get("_ids") or {}).get("es") or ""
            if vid:
                out[slug_dir.name] = vid
        except Exception:
            continue
    return out


def _latest_stats_by_video_id() -> dict[str, dict[str, Any]]:
    """Último snapshot de stats por video_id. Devuelve dict con views + title."""
    out: dict[str, dict[str, Any]] = {}
    if not STATS_HISTORY.exists():
        return out
    try:
        for line in STATS_HISTORY.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("platform") != "youtube" or d.get("kind") != "video":
                continue
            vid = d.get("video_id") or ""
            if not vid:
                continue
            # Solo conserva el snapshot más reciente
            ts = int(d.get("ts") or 0)
            prev = out.get(vid)
            if not prev or ts > int(prev.get("ts") or 0):
                out[vid] = d
    except Exception:
        pass
    return out


def pick_top_candidates(platform: str, n: int = 2, min_views: int = 20) -> list[dict[str, Any]]:
    """Top N slugs por views YT no reposteados aún a `platform`.

    platform: 'tiktok' | 'instagram' | 'threads'
    min_views: umbral para evitar backfillear videos flops (<20 views).

    NOTA: el archivo vertical mp4 NO es filtro — si no existe local (GH Actions
    corre sin uploaded/), lo descarga bajo demanda desde YT vía yt-dlp en
    _ensure_vertical_local(). Solo requiere que exista el video_id (YT público).
    """
    slug_to_vid = _map_slug_to_video_id()
    vid_to_stats = _latest_stats_by_video_id()
    ledger = _load_ledger()

    candidates: list[dict[str, Any]] = []
    for slug, vid in slug_to_vid.items():
        stats = vid_to_stats.get(vid) or {}
        views = int(stats.get("views") or 0)
        if views < min_views:
            continue
        # Ya reposteado a esta plataforma?
        if platform in (ledger.get(slug) or {}):
            continue
        candidates.append({
            "slug": slug,
            "video_id": vid,
            "title": stats.get("title") or slug.replace("-", " ").title(),
            "views": views,
            "likes": int(stats.get("likes") or 0),
            "vertical_path": UPLOADED_DIR / slug / "video_es_vertical.mp4",
        })

    candidates.sort(key=lambda x: -x["views"])
    return candidates[:n]


# Último stderr yt-dlp para diagnóstico (se lee desde _post_to_platform)
_LAST_YTDLP_ERR: str = ""


def _ensure_vertical_local(cand: dict[str, Any]) -> Path | None:
    """Devuelve la ruta al mp4 vertical.

    Prioridad de fuentes:
      1. output/uploaded/{slug}/video_es_vertical.mp4 (LOCAL Mac)
      2. docs/reels/{slug}.mp4 (commiteado — disponible en runner GH tras checkout)
      3. yt-dlp descarga desde YT (necesita YT_COOKIES en runner para bypass bot-check)
    """
    path: Path = cand["vertical_path"]
    if path.exists() and path.stat().st_size > 100_000:
        return path

    # Fuente 2: docs/reels/{slug}.mp4 — mp4 que YA está en el repo (backfill IG
    # inicial usó esto porque yt-dlp está bloqueado en runners GH sin YT_COOKIES).
    docs_reel = ROOT / "docs" / "reels" / f"{cand['slug']}.mp4"
    if docs_reel.exists() and docs_reel.stat().st_size > 100_000:
        print(f"  backfill: usando {docs_reel.relative_to(ROOT)} ({docs_reel.stat().st_size//1024}KB)")
        return docs_reel

    path.parent.mkdir(parents=True, exist_ok=True)
    video_id = cand["video_id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    import os, subprocess

    # Cookies file: si YT_COOKIES secret está presente, el workflow lo dump-ea
    # en /tmp/yt_cookies.txt antes de invocarnos. Esto salta el bot-check de YT
    # en runners cloud (fetch autenticado con la sesión del user).
    cookies_file = os.environ.get("YT_COOKIES_FILE") or "/tmp/yt_cookies.txt"
    has_cookies = os.path.exists(cookies_file) and os.path.getsize(cookies_file) > 100
    cookie_args = ["--cookies", cookies_file] if has_cookies else []

    # Estrategias: probamos varios player clients. `web` con cookies requiere
    # PO Token desde 2024 (YT anti-bot) que yt-dlp no siempre puede generar
    # → devuelve "Requested format is not available". android+tv_embedded
    # aceptan cookies sin necesitar PO Token. Con o sin cookies mismos clients.
    base_ua = "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36"
    strategies = [
        ["--extractor-args", "youtube:player_client=android", "--user-agent", base_ua],
        ["--extractor-args", "youtube:player_client=tv_embedded"],
        ["--extractor-args", "youtube:player_client=mweb"],
        ["--extractor-args", "youtube:player_client=ios"],
        [],  # default yt-dlp
    ]

    global _LAST_YTDLP_ERR
    _LAST_YTDLP_ERR = ""
    errors_by_strat: list[str] = []
    for i, extra in enumerate(strategies):
        cmd = [
            "yt-dlp",
            # Formato sin filtro extension — con player=android YT sirve
            # WebM/VP9 y [ext=mp4] no matcheaba. --merge-output-format mp4
            # re-empaqueta al final (ffmpeg ya instalado en runner).
            # Verificado 15/09 con yt-cookies-check: esta cadena funciona.
            "-f", "bv*+ba/b",
            "--merge-output-format", "mp4",
            "-o", str(path),
            "--no-warnings",
            "--no-playlist",
            *cookie_args,
            *extra,
            url,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except FileNotFoundError:
            print("  backfill: yt-dlp CLI no encontrado (dep no instalada)")
            return None
        except Exception as e:
            print(f"  backfill: yt-dlp exception estrategia {i+1} — {type(e).__name__}: {e}")
            continue

        if r.returncode == 0 and path.exists() and path.stat().st_size >= 100_000:
            src = "cookies+" if has_cookies else ""
            print(f"  backfill: descargado {path.stat().st_size // 1024}KB via {src}estrategia {i+1}")
            return path
        stderr = (r.stderr or r.stdout or "")[:300]
        print(f"  backfill: estrategia {i+1} falló ({video_id}) rc={r.returncode} — {stderr}")
        # Extrae el mensaje ERROR clave (línea que empieza por "ERROR:")
        err_line = next((l for l in stderr.split("\n") if l.startswith("ERROR")), stderr[:80])
        strat_label = extra[1] if len(extra) > 1 else "default"
        errors_by_strat.append(f"S{i+1}({strat_label[:15]}): {err_line[:80]}")

    # Guarda TODOS los errores para _post_to_platform (no solo el último)
    _LAST_YTDLP_ERR = " | ".join(errors_by_strat)[:400]

    if not has_cookies:
        print("  backfill: sin YT_COOKIES secret — YT bloquea el runner. Setup en README.")
    return None


def mark_backfilled(slug: str, platform: str) -> None:
    """Registra en el ledger que `slug` se posteó a `platform`."""
    ledger = _load_ledger()
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    ledger.setdefault(slug, {})[platform] = ts
    _save_ledger(ledger)


def backfill_once(platforms: list[str] | None = None,
                   per_platform: int = 2) -> dict[str, dict]:
    """Ejecuta un ciclo de backfill: para cada plataforma, coge top N y postea.

    Devuelve dict {platform: {posted: [...], failed: [...], candidates_found: N}}
    para diagnóstico claro (¿0 candidatos vs 3 candidatos-todos-fallaron?).
    """
    if platforms is None:
        platforms = ["tiktok", "instagram", "threads"]

    results: dict[str, dict] = {}

    for platform in platforms:
        candidates = pick_top_candidates(platform, n=per_platform)
        posted: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for cand in candidates:
            outcome = _post_to_platform(platform, cand)
            if outcome:
                mark_backfilled(cand["slug"], platform)
                posted.append({**cand, "result": outcome})
            else:
                failed.append(cand)
            time.sleep(20)
        results[platform] = {
            "posted": posted,
            "failed": failed,
            "candidates_found": len(candidates),
        }
    return results


def _post_to_platform(platform: str, cand: dict[str, Any]) -> dict | None:
    """Enruta al poster correspondiente. Asegura el mp4 local antes de postear
    (descarga desde YT si el runner no lo tiene). Guarda `fail_reason` en cand
    para diagnóstico específico (yt-dlp bloqueado vs IG rechazó vs otro)."""
    # Threads es texto solo, no necesita mp4.
    if platform != "threads":
        vert = _ensure_vertical_local(cand)
        if not vert:
            print(f"  backfill {platform}: sin mp4 disponible para {cand['slug']}")
            cand["fail_reason"] = f"yt-dlp: {_LAST_YTDLP_ERR or 'sin stderr (dep missing?)'}"
            return None
        cand["vertical_path"] = vert

    try:
        if platform == "tiktok":
            from . import tiktok_poster
            r = tiktok_poster.post_video_to_tiktok(
                cand["title"], cand["vertical_path"], cand["slug"],
            )
            if not r: cand["fail_reason"] = "tiktok poster returned None"
            return r
        if platform == "instagram":
            from . import instagram_poster
            yt_url = f"https://youtube.com/shorts/{cand['video_id']}"
            r = instagram_poster.post_reel_to_instagram(
                cand["title"], yt_url, cand["vertical_path"], cand["slug"],
            )
            if not r: cand["fail_reason"] = "IG poster returned None (mira output/ig_publish_log.json)"
            return r
        if platform == "threads":
            from . import threads_poster
            yt_url = f"https://youtube.com/shorts/{cand['video_id']}"
            r = threads_poster.post_short_to_threads(
                cand["title"], yt_url,
            )
            if not r: cand["fail_reason"] = "threads poster returned None"
            return r
    except Exception as e:
        print(f"  backfill {platform}: {type(e).__name__}: {e}")
        cand["fail_reason"] = f"{type(e).__name__}: {str(e)[:100]}"
        return None
    return None
