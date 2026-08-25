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


def _ensure_vertical_local(cand: dict[str, Any]) -> Path | None:
    """Devuelve la ruta al mp4 vertical. Si no existe local (típico en GH
    Actions runner tras fresh checkout), descarga el Short desde YouTube via
    yt-dlp usando el video_id. Los Shorts son públicos → download OK sin auth.
    """
    path: Path = cand["vertical_path"]
    if path.exists() and path.stat().st_size > 100_000:
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://youtube.com/shorts/{cand['video_id']}"
    try:
        import subprocess
        # yt-dlp mp4 en la mejor calidad disponible <=1080p (para 9:16 shorts)
        cmd = [
            "yt-dlp",
            "-f", "bestvideo[height<=1920]+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", str(path),
            "--quiet", "--no-warnings",
            url,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            print(f"  backfill: yt-dlp fail para {cand['video_id']} — {r.stderr[:200]}")
            return None
        if not path.exists() or path.stat().st_size < 100_000:
            print(f"  backfill: yt-dlp completó pero mp4 vacío: {path}")
            return None
        return path
    except FileNotFoundError:
        print("  backfill: yt-dlp no instalado (falta dep en el entorno)")
        return None
    except Exception as e:
        print(f"  backfill: yt-dlp exception — {type(e).__name__}: {e}")
        return None


def mark_backfilled(slug: str, platform: str) -> None:
    """Registra en el ledger que `slug` se posteó a `platform`."""
    ledger = _load_ledger()
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    ledger.setdefault(slug, {})[platform] = ts
    _save_ledger(ledger)


def backfill_once(platforms: list[str] | None = None,
                   per_platform: int = 2) -> dict[str, list[dict[str, Any]]]:
    """Ejecuta un ciclo de backfill: para cada plataforma, coge top N y postea.

    Devuelve dict {platform: [resultados]}.
    """
    if platforms is None:
        platforms = ["tiktok", "instagram", "threads"]

    results: dict[str, list[dict[str, Any]]] = {}

    for platform in platforms:
        candidates = pick_top_candidates(platform, n=per_platform)
        results[platform] = []
        for cand in candidates:
            outcome = _post_to_platform(platform, cand)
            if outcome:
                mark_backfilled(cand["slug"], platform)
                results[platform].append({**cand, "result": outcome})
            # Espaciar posts para evitar rate-limit
            time.sleep(20)
    return results


def _post_to_platform(platform: str, cand: dict[str, Any]) -> dict | None:
    """Enruta al poster correspondiente. Asegura el mp4 local antes de postear
    (descarga desde YT si el runner no lo tiene)."""
    # Threads es texto solo, no necesita mp4.
    if platform != "threads":
        vert = _ensure_vertical_local(cand)
        if not vert:
            print(f"  backfill {platform}: sin mp4 disponible para {cand['slug']}")
            return None
        cand["vertical_path"] = vert

    try:
        if platform == "tiktok":
            from . import tiktok_poster
            return tiktok_poster.post_video_to_tiktok(
                cand["title"], cand["vertical_path"], cand["slug"],
            )
        if platform == "instagram":
            from . import instagram_poster
            yt_url = f"https://youtube.com/shorts/{cand['video_id']}"
            return instagram_poster.post_reel_to_instagram(
                cand["title"], yt_url, cand["vertical_path"], cand["slug"],
            )
        if platform == "threads":
            from . import threads_poster
            yt_url = f"https://youtube.com/shorts/{cand['video_id']}"
            return threads_poster.post_short_to_threads(
                cand["title"], yt_url,
            )
    except Exception as e:
        print(f"  backfill {platform}: {type(e).__name__}: {e}")
        return None
    return None
