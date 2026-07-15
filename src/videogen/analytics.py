"""Histórico de stats por plataforma + gráficas diarias.

Almacenamiento: JSONL append-only (output/stats_history.jsonl). Una fila por
snapshot. Esquema:
  {date: "YYYY-MM-DD", ts: unix, platform: "youtube"|"tiktok"|"instagram",
   kind: "channel"|"video", slug: str|None, video_id: str|None, title: str|None,
   views: int, likes: int, subs: int|None, source: "api"|"manual"}

Tres paneles por plataforma:
  1. Crecimiento del canal (subs/followers + total views) en el tiempo
  2. Views por vídeo en el tiempo (línea por vídeo)
  3. Like-rate por vídeo (barras, última lectura)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import matplotlib
matplotlib.use("Agg")  # sin GUI
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from . import stats
from .config import UPLOADED_DIR

HISTORY_PATH = Path(__file__).resolve().parents[2] / "output" / "stats_history.jsonl"
CHARTS_DIR = Path(__file__).resolve().parents[2] / "output" / "charts"

PLATFORMS = ("youtube", "tiktok", "instagram")
COLORS = {  # paleta cálida coherente con la UI (terracota + ocre)
    "youtube": "#c0633f",
    "tiktok": "#3a3a3a",
    "instagram": "#a84e2c",
    "ink": "#2a2521",
    "body": "#4a443c",
    "muted": "#8a8074",
    "line": "#e7dece",
    "bg": "#fbf8f1",
}


# ───────────────────────────── almacenamiento ──────────────────────────────
def _ensure_paths() -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def record_snapshot(rows: Iterable[dict]) -> int:
    """Añade filas al histórico. Devuelve nº de filas escritas."""
    _ensure_paths()
    n = 0
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        for row in rows:
            row = {**row, "ts": row.get("ts") or int(datetime.utcnow().timestamp())}
            row.setdefault("date", datetime.fromtimestamp(row["ts"]).strftime("%Y-%m-%d"))
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def load_history(days: int = 30, platform: str | None = None) -> list[dict]:
    """Lee las filas de los últimos `days` días (todas si days=0)."""
    if not HISTORY_PATH.exists():
        return []
    cutoff = (datetime.utcnow() - timedelta(days=days)).timestamp() if days else 0
    out: list[dict] = []
    with open(HISTORY_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("ts", 0) < cutoff:
                continue
            if platform and r.get("platform") != platform:
                continue
            out.append(r)
    return out


# ─────────────────────────────── snapshots ─────────────────────────────────
def snapshot_youtube() -> list[dict]:
    """Captura el estado actual de YT (canal + por vídeo) vía API."""
    rows: list[dict] = []
    ch = stats.fetch_channel_stats() or {}
    if ch:
        rows.append({
            "platform": "youtube", "kind": "channel",
            "subs": int(ch.get("subscribers", 0) or 0),
            "views": int(ch.get("views", 0) or 0),
            "likes": 0,
            "source": "api",
        })
    for v in (stats.fetch_youtube_stats() or []):
        rows.append({
            "platform": "youtube", "kind": "video",
            "slug": v.get("slug"), "video_id": v.get("id"),
            "lang": v.get("lang"),
            "title": (v.get("title") or "")[:80],
            "views": int(v.get("views", 0)),
            "likes": int(v.get("likes", 0)),
            "source": "api",
        })
    return rows


def snapshot_instagram() -> list[dict]:
    """IG Graph API (cuenta Creator/Business). Requiere IG_ACCESS_TOKEN +
    IG_BUSINESS_ACCOUNT_ID en .env. Si faltan, devuelve [] silenciosamente."""
    import requests
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    ig_id = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "").strip()
    if not token or not ig_id:
        return []
    rows: list[dict] = []
    try:
        ch = requests.get(
            f"https://graph.facebook.com/v21.0/{ig_id}",
            params={"fields": "followers_count,media_count", "access_token": token},
            timeout=15,
        ).json()
        rows.append({
            "platform": "instagram", "kind": "channel",
            "subs": int(ch.get("followers_count", 0) or 0),
            "views": 0, "likes": 0, "source": "api",
        })
        media = requests.get(
            f"https://graph.facebook.com/v21.0/{ig_id}/media",
            params={"fields": "id,caption,timestamp", "limit": 20, "access_token": token},
            timeout=15,
        ).json().get("data", [])
        for m in media:
            ins = requests.get(
                f"https://graph.facebook.com/v21.0/{m['id']}/insights",
                params={"metric": "reach,likes,comments,plays", "access_token": token},
                timeout=15,
            ).json().get("data", [])
            vals = {x["name"]: (x["values"][0].get("value") or 0) for x in ins}
            rows.append({
                "platform": "instagram", "kind": "video",
                "video_id": m["id"], "slug": None,
                "title": (m.get("caption") or "")[:80],
                "views": int(vals.get("plays") or vals.get("reach") or 0),
                "likes": int(vals.get("likes") or 0),
                "source": "api",
            })
    except Exception:
        return rows
    return rows


# ─────────────────────────────── gráficas ──────────────────────────────────
def _setup_axes(ax, title: str) -> None:
    ax.set_title(title, fontsize=11, color=COLORS["ink"], fontweight="bold", loc="left", pad=8)
    ax.tick_params(colors=COLORS["muted"], labelsize=9)
    for s in ax.spines.values():
        s.set_color(COLORS["line"])
    ax.set_facecolor(COLORS["bg"])
    ax.grid(True, color=COLORS["line"], linewidth=0.7, alpha=0.7)


def _group_by_video(rows: list[dict]) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("kind") != "video":
            continue
        # Diferenciamos por id (cada YT id es único; ES y EN del mismo slug
        # tienen ids distintos y queremos verlos por separado).
        key = (
            r.get("video_id")
            or f"{r.get('slug', '')}-{r.get('lang', '')}"
            or (r.get("title") or "")[:40]
        )
        if not key or key == "-":
            continue
        by.setdefault(key, []).append(r)
    for k in by:
        by[k].sort(key=lambda r: r["ts"])
    return by


def render_platform_chart(platform: str, dest: Path, days: int = 30) -> Path | None:
    rows = load_history(days=days, platform=platform)
    if not rows:
        return None
    fig, axes = plt.subplots(3, 1, figsize=(9, 11), constrained_layout=True)
    fig.patch.set_facecolor(COLORS["bg"])
    color = COLORS.get(platform, COLORS["ink"])

    # Panel 1: canal (subs + total views)
    ch = sorted([r for r in rows if r.get("kind") == "channel"], key=lambda r: r["ts"])
    ax1 = axes[0]
    _setup_axes(ax1, f"{platform.upper()} · canal (suscriptores + views totales)")
    if ch:
        xs = [datetime.fromtimestamp(r["ts"]) for r in ch]
        subs = [r.get("subs", 0) or 0 for r in ch]
        views = [r.get("views", 0) or 0 for r in ch]
        ax1.plot(xs, subs, color=color, marker="o", linewidth=2, label="suscriptores")
        ax1.set_ylabel("suscriptores", color=color, fontsize=9)
        ax1.tick_params(axis="y", colors=color)
        ax2 = ax1.twinx()
        ax2.plot(xs, views, color=COLORS["muted"], linewidth=1.8, linestyle="--", label="views totales")
        ax2.set_ylabel("views totales", color=COLORS["muted"], fontsize=9)
        ax2.tick_params(axis="y", colors=COLORS["muted"])
        for s in ax2.spines.values():
            s.set_color(COLORS["line"])
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    else:
        ax1.text(0.5, 0.5, "(sin datos de canal)", ha="center", va="center",
                 transform=ax1.transAxes, color=COLORS["muted"])

    # Panel 2: views por vídeo en el tiempo
    by_vid = _group_by_video(rows)
    ax3 = axes[1]
    _setup_axes(ax3, "views por vídeo (evolución)")
    if by_vid:
        # Top 8 por views actuales para no saturar
        latest = sorted(by_vid.items(), key=lambda kv: kv[1][-1].get("views", 0), reverse=True)[:8]
        cmap = plt.get_cmap("tab10")
        for i, (key, series) in enumerate(latest):
            xs = [datetime.fromtimestamp(r["ts"]) for r in series]
            ys = [r.get("views", 0) for r in series]
            label = (series[-1].get("title") or key)[:42]
            ax3.plot(xs, ys, marker="o", linewidth=1.6, markersize=4,
                     color=cmap(i % 10), label=label)
        ax3.legend(loc="upper left", fontsize=7, frameon=False, ncol=1)
        ax3.set_ylabel("views", color=COLORS["body"], fontsize=9)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    else:
        ax3.text(0.5, 0.5, "(sin vídeos registrados)", ha="center", va="center",
                 transform=ax3.transAxes, color=COLORS["muted"])

    # Panel 3: like-rate por vídeo (última lectura)
    ax4 = axes[2]
    _setup_axes(ax4, "like-rate por vídeo (última lectura, %)")
    if by_vid:
        latest = [(k, v[-1]) for k, v in by_vid.items()]
        latest = [x for x in latest if x[1].get("views", 0) > 0]
        latest.sort(key=lambda x: (x[1].get("likes", 0) / max(x[1].get("views", 1), 1)), reverse=True)
        latest = latest[:10]
        labels = [(r.get("title") or k)[:30] for k, r in latest]
        rates = [r.get("likes", 0) / max(r.get("views", 1), 1) * 100 for _, r in latest]
        bars = ax4.barh(labels, rates, color=color, alpha=0.85)
        ax4.invert_yaxis()
        for bar, rate in zip(bars, rates):
            ax4.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                     f"{rate:.1f}%", va="center", fontsize=8, color=COLORS["ink"])
        ax4.set_xlabel("like-rate (%)", color=COLORS["body"], fontsize=9)
        ax4.axvline(2.0, color=COLORS["muted"], linewidth=0.8, linestyle="--", alpha=0.6)
        ax4.text(2.05, len(labels) - 0.5, "objetivo 2%", color=COLORS["muted"], fontsize=8)
    else:
        ax4.text(0.5, 0.5, "(sin vídeos)", ha="center", va="center",
                 transform=ax4.transAxes, color=COLORS["muted"])

    fig.suptitle(
        f"{platform.upper()} — últimos {days} días",
        fontsize=14, color=COLORS["ink"], fontweight="bold", x=0.02, ha="left",
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=130, facecolor=COLORS["bg"])
    plt.close(fig)
    return dest


def render_all(dest_dir: Path | None = None, days: int = 30) -> dict[str, Path]:
    """Renderiza una PNG por plataforma con datos disponibles. Devuelve mapping."""
    dest_dir = dest_dir or CHARTS_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for p in PLATFORMS:
        png = dest_dir / f"chart_{p}.png"
        rendered = render_platform_chart(p, png, days=days)
        if rendered:
            out[p] = rendered
    return out


# ───────────────────────────── helpers manuales ────────────────────────────
def record_manual(platform: str, views: int, likes: int = 0,
                  slug: str | None = None, title: str | None = None,
                  subs: int | None = None) -> dict:
    """Registra una lectura manual (uso típico: TikTok desde el bot)."""
    row = {
        "platform": platform,
        "kind": "channel" if subs is not None and not slug else "video",
        "slug": slug, "title": title,
        "views": int(views), "likes": int(likes),
        "subs": int(subs) if subs is not None else None,
        "source": "manual",
    }
    record_snapshot([row])
    return row


def snapshot_all(progress=lambda m: None) -> dict[str, int]:
    """Snapshot de todas las plataformas con API. Devuelve {plataforma: nº filas}."""
    counts: dict[str, int] = {}
    try:
        yt_rows = snapshot_youtube()
        if yt_rows:
            record_snapshot(yt_rows)
            counts["youtube"] = len(yt_rows)
            progress(f"YT: {len(yt_rows)} filas")
    except Exception as e:
        progress(f"YT failed: {e}")
    try:
        ig_rows = snapshot_instagram()
        if ig_rows:
            record_snapshot(ig_rows)
            counts["instagram"] = len(ig_rows)
            progress(f"IG: {len(ig_rows)} filas")
    except Exception as e:
        progress(f"IG failed: {e}")
    return counts
