"""Auditoría rápida rendimiento Shorts (últimos N).

Umbrales YT Shorts 2026 (SocialPilot algorithm update ago-2026):
- <30s → 65% avg retention
- 30-60s → 50% avg retention

YT Analytics API (getAvgViewPercentage) requiere scope adicional
`yt-analytics.readonly` que aún no está solicitado. Este script usa
proxy razonable con datos disponibles en Data API v3:

    engagement_rate = (likes + 2*comments) / max(views, 1)
    views_per_day = views / max(days_online, 1)

Marca "sospechoso" si views_per_day < mediana/3 (candidato a rehacer).

Cuando amplíes scope yt-analytics.readonly, integramos avg retention
real; hasta entonces esto identifica los outliers negativos suficiente
para decidir dónde repivotar.
"""
from __future__ import annotations

import json
import os
import statistics
import urllib.request
from datetime import datetime, timezone
from typing import Any

import googleapiclient.discovery

from .upload_youtube import _get_credentials


def _fetch_last_uploads(youtube: Any, n: int = 20) -> list[dict]:
    ch = youtube.channels().list(part="contentDetails", mine=True).execute()
    items = ch.get("items", [])
    if not items:
        return []
    uploads_pl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    resp = youtube.playlistItems().list(
        part="snippet,contentDetails", playlistId=uploads_pl,
        maxResults=min(50, n),
    ).execute()
    videos = [
        {"id": it["contentDetails"]["videoId"],
          "title": it["snippet"]["title"],
          "published_at": it["snippet"]["publishedAt"]}
        for it in resp.get("items", [])
    ][:n]
    if not videos:
        return []
    ids = ",".join(v["id"] for v in videos)
    stats_resp = youtube.videos().list(
        part="statistics,contentDetails", id=ids,
    ).execute()
    by_id = {s["id"]: s for s in stats_resp.get("items", [])}
    for v in videos:
        s = by_id.get(v["id"], {})
        stats = s.get("statistics", {})
        v["views"] = int(stats.get("viewCount", 0))
        v["likes"] = int(stats.get("likeCount", 0))
        v["comments"] = int(stats.get("commentCount", 0))
        v["duration"] = s.get("contentDetails", {}).get("duration", "")
    return videos


def _days_since(iso_ts: str) -> float:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except Exception:
        return 1.0
    delta = datetime.now(timezone.utc) - dt
    return max(delta.total_seconds() / 86400.0, 0.5)


def _notify(text: str) -> None:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data=json.dumps({"chat_id": int(chat), "text": text,
                                "parse_mode": "HTML"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass


def audit_channel(yt_prefix: str = "", n: int = 20,
                     notify: bool = True) -> dict:
    prev_prefix = os.environ.get("YT_CHANNEL_PREFIX", "")
    if yt_prefix:
        os.environ["YT_CHANNEL_PREFIX"] = yt_prefix
    else:
        os.environ.pop("YT_CHANNEL_PREFIX", None)
    try:
        creds = _get_credentials()
        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
        vids = _fetch_last_uploads(youtube, n=n)
        if not vids:
            return {"status": "no_videos", "prefix": yt_prefix}
        for v in vids:
            v["days"] = _days_since(v["published_at"])
            v["views_per_day"] = v["views"] / v["days"]
            v["engagement_rate"] = (
                v["likes"] + 2 * v["comments"]
            ) / max(v["views"], 1)
        vpd = [v["views_per_day"] for v in vids]
        median_vpd = statistics.median(vpd) if vpd else 0.0
        threshold = median_vpd / 3.0
        underperformers = [
            v for v in vids
            if v["views_per_day"] < threshold and v["days"] >= 2
        ]
        underperformers.sort(key=lambda v: v["views_per_day"])
        summary = {
            "status": "ok", "prefix": yt_prefix or "MAIN",
            "total": len(vids), "median_vpd": round(median_vpd, 2),
            "threshold_vpd": round(threshold, 2),
            "underperformers": [
                {"id": v["id"], "title": v["title"][:80],
                  "views": v["views"], "days": round(v["days"], 1),
                  "vpd": round(v["views_per_day"], 2),
                  "engagement": round(v["engagement_rate"] * 100, 2)}
                for v in underperformers[:8]
            ],
        }
        if notify and underperformers:
            label = yt_prefix or "WaitWhy (MAIN)"
            lines = [f"📉 <b>Audit shorts · {label}</b>",
                       f"Mediana views/día: <b>{median_vpd:.1f}</b>",
                       f"Underperformers (&lt;{threshold:.1f} vpd, >=2 días):"]
            for v in underperformers[:5]:
                lines.append(
                    f"• <i>{v['title'][:60]}</i> — "
                    f"{v['views']} views · {v['views_per_day']:.1f} vpd"
                )
            lines.append("\nCandidatos a rehacer o retirar del canal.")
            _notify("\n".join(lines))
        return summary
    except Exception as e:
        return {"status": "error", "prefix": yt_prefix, "error": str(e)[:200]}
    finally:
        if prev_prefix:
            os.environ["YT_CHANNEL_PREFIX"] = prev_prefix
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)


CHANNELS = ["", "YT_TAX", "YT_LEGAL", "YT_AYUDAS", "YT_MOTOR",
             "YT_POV", "YT_RANKING", "YT_AMBIENT"]


def audit_all(n: int = 20) -> dict:
    return {(p or "MAIN"): audit_channel(p, n=n) for p in CHANNELS}
