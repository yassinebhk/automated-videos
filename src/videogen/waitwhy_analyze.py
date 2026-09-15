"""Análisis performance canal WaitWhy — categoriza por tema y ranquea.

Objetivo: identificar qué sub-nicho del canal rinde mejor (corrupción,
crimen, estafa, robo, etc.) para ajustar el topic pool hacia lo que
genera más views + engagement.

Consulta YT Data API v3 (auth con YT_REFRESH_TOKEN del canal principal):
  - Lista últimos 100 uploads
  - Fetch statistics (views, likes, comments) por lote de 50
  - Categoriza cada video por keywords en título
  - Ordena por views/día (views/max(1, days_online))
  - Notifica Telegram con top 10 + análisis por categoría
"""
from __future__ import annotations

import os
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import googleapiclient.discovery

from .upload_youtube import _get_credentials


# Categorías con keywords (lowercase, substring match sobre título)
CATEGORIES: dict[str, list[str]] = {
    "corrupción": ["corrupción", "corrupto", "sobornos", "mordidas",
                    "cohecho", "prevaricación", "malversación"],
    "crimen violento": ["asesinato", "asesino", "crimen", "homicidio",
                         "matanza", "cadáver", "descuartizad", "acuchill"],
    "estafa": ["estafa", "fraude", "engaño", "pirámide", "phishing",
                "timo", "esquema", "chiringuito"],
    "robo/atraco": ["robo", "atraco", "hurto", "asalto", "butrón"],
    "casos famosos ES": ["mario conde", "bárcenas", "gürtel", "kio",
                          "banesto", "matesa", "roldán", "urdangarin",
                          "villarejo"],
    "casos sin resolver": ["sin resolver", "cold case", "misterio",
                            "desaparición", "desaparecido", "impune"],
    "narcotráfico": ["narco", "cocaína", "droga", "cartel", "marbella"],
    "político": ["político", "polític", "expresidente", "ministro",
                  "diputado", "alcalde"],
    "empresarial": ["empresa", "banco", "bolsa", "quiebra", "caso koldo"],
}


def _categorize(title: str) -> list[str]:
    """Devuelve la(s) categoría(s) matching del título."""
    tl = title.lower()
    matched = []
    for cat, kws in CATEGORIES.items():
        for kw in kws:
            if kw in tl:
                matched.append(cat)
                break
    return matched or ["otros"]


def _days_since(iso_ts: str) -> float:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except Exception:
        return 1.0
    return max((datetime.now(timezone.utc) - dt).total_seconds() / 86400.0, 0.5)


def analyze() -> dict[str, Any]:
    """Fetch + categoriza + notifica. Devuelve dict con top + análisis."""
    from .notify_batch import add
    # Asegura que YT_CHANNEL_PREFIX está vacío para usar creds WaitWhy
    prev = os.environ.get("YT_CHANNEL_PREFIX", "")
    os.environ.pop("YT_CHANNEL_PREFIX", None)
    try:
        creds = _get_credentials()
        yt = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

        # 1. Uploads playlist del canal
        ch = yt.channels().list(part="contentDetails,snippet,statistics",
                                  mine=True).execute()
        items = ch.get("items", [])
        if not items:
            return {"error": "sin canal"}
        uploads_pl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        channel_title = items[0]["snippet"]["title"]

        # 2. Lista últimos 100 videos
        videos = []
        page = None
        while len(videos) < 100:
            resp = yt.playlistItems().list(
                part="snippet,contentDetails", playlistId=uploads_pl,
                maxResults=50, pageToken=page,
            ).execute()
            for it in resp.get("items", []):
                videos.append({
                    "id": it["contentDetails"]["videoId"],
                    "title": it["snippet"]["title"],
                    "published_at": it["snippet"]["publishedAt"],
                })
            page = resp.get("nextPageToken")
            if not page:
                break

        # 3. Stats en lotes de 50
        for i in range(0, len(videos), 50):
            batch_ids = ",".join(v["id"] for v in videos[i:i+50])
            stats_resp = yt.videos().list(
                part="statistics,contentDetails", id=batch_ids,
            ).execute()
            by_id = {s["id"]: s for s in stats_resp.get("items", [])}
            for v in videos[i:i+50]:
                s = by_id.get(v["id"], {})
                stats = s.get("statistics", {})
                v["views"] = int(stats.get("viewCount", 0))
                v["likes"] = int(stats.get("likeCount", 0))
                v["comments"] = int(stats.get("commentCount", 0))
                v["duration_iso"] = s.get("contentDetails", {}).get("duration", "")

        # 4. Métricas derivadas
        for v in videos:
            v["days"] = _days_since(v["published_at"])
            v["vpd"] = v["views"] / v["days"]  # views per day
            v["engagement_pct"] = (
                100.0 * (v["likes"] + 2 * v["comments"]) / max(v["views"], 1)
            )
            v["categories"] = _categorize(v["title"])

        # 5. Ranking global por vpd
        videos.sort(key=lambda v: -v["vpd"])
        top10 = videos[:10]

        # 6. Análisis por categoría
        cat_stats: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "total_views": 0, "total_vpd": 0.0,
                     "engagements": []}
        )
        for v in videos:
            for c in v["categories"]:
                cat_stats[c]["count"] += 1
                cat_stats[c]["total_views"] += v["views"]
                cat_stats[c]["total_vpd"] += v["vpd"]
                cat_stats[c]["engagements"].append(v["engagement_pct"])
        cat_ranked = []
        for c, s in cat_stats.items():
            if s["count"] < 2:
                continue
            avg_vpd = s["total_vpd"] / s["count"]
            avg_eng = statistics.mean(s["engagements"])
            cat_ranked.append({
                "cat": c, "count": s["count"],
                "total_views": s["total_views"],
                "avg_vpd": avg_vpd, "avg_engagement_pct": avg_eng,
            })
        cat_ranked.sort(key=lambda x: -x["avg_vpd"])

        # 7. Compone mensaje Telegram
        lines = [f"🔍 <b>WaitWhy · análisis performance</b>",
                  f"Canal: <b>{channel_title}</b> · {len(videos)} videos analizados",
                  "",
                  "<b>🏆 TOP 10 por views/día</b>"]
        for i, v in enumerate(top10, 1):
            title = v["title"][:55]
            cats = ",".join(v["categories"][:2])
            lines.append(
                f"{i}. <b>{v['vpd']:.1f} vpd</b> · {v['views']}v · "
                f"{v['engagement_pct']:.1f}%eng · <i>{cats}</i>"
            )
            lines.append(f"   <i>{title}</i>")

        lines += ["", "<b>📊 Ranking por CATEGORÍA</b> (media views/día)"]
        for c in cat_ranked[:10]:
            lines.append(
                f"  {c['cat']}: {c['count']} vids · "
                f"<b>{c['avg_vpd']:.1f} vpd</b> · {c['avg_engagement_pct']:.1f}%eng"
            )

        # 8. Recomendación
        if cat_ranked:
            best = cat_ranked[0]
            worst = cat_ranked[-1] if len(cat_ranked) > 1 else None
            rec = [f"\n<b>💡 Recomendación</b>: pivotar más hacia <b>{best['cat']}</b> "
                   f"(mejor vpd)."]
            if worst and worst["cat"] != "otros":
                rec.append(f"Reducir peso de <b>{worst['cat']}</b> (peor vpd).")
            lines += rec

        msg = "\n".join(lines)
        add(msg)
        return {
            "top10": [{"title": v["title"], "vpd": v["vpd"],
                        "views": v["views"], "categories": v["categories"]}
                       for v in top10],
            "categories_ranked": cat_ranked,
            "total_videos": len(videos),
        }
    finally:
        if prev:
            os.environ["YT_CHANNEL_PREFIX"] = prev
