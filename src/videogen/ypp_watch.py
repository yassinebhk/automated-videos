"""YPP watch — monitoriza distancia a monetización YouTube.

Umbrales YouTube Partner Program 2026:
  - LONG:  1000 subs + 4000h watch time
  - SHORT: 1000 subs + 10M vistas Shorts últimos 90d
  - MIXTO: 500 subs + 3000h watch time (o 3M vistas Shorts)

También bajado en 2026:
  - YT Shopping Affiliate: **500 subs** (antes 1000)
  - Super Thanks: **500 subs** (era 1000)

Estrategia: chequeo semanal. Notificación Telegram:
  - 300+ subs → "🎯 acercándose (300+)"
  - 400+ subs → "🚀 casi listo (400+) — prepara aplicación"
  - 500+ subs → "🎉 APLICA YA a YT Shopping + Super Thanks"
  - 1000+ subs → "💰 APLICA YA a YPP full"
"""
from __future__ import annotations

import os
from typing import Any

import googleapiclient.discovery

from .upload_youtube import _get_credentials


CHANNELS = [
    ("", "WaitWhy"),
    ("YT_TAX", "TaxHack ES"),
    ("YT_LEGAL", "TusDerechos ES"),
    ("YT_AYUDAS", "AyudaGob"),
    ("YT_MOTOR", "Motor60s"),
    ("YT_POV", "TiempoAtrás ES"),
    ("YT_RANKING", "TopRanking ES"),
    ("YT_AMBIENT", "MenteEnCalma"),
    ("YT_IA", "IA Autónomos ES"),
]


def _channel_stats(yt_prefix: str) -> dict | None:
    prev = os.environ.get("YT_CHANNEL_PREFIX", "")
    if yt_prefix:
        os.environ["YT_CHANNEL_PREFIX"] = yt_prefix
    else:
        os.environ.pop("YT_CHANNEL_PREFIX", None)
    try:
        creds = _get_credentials()
        yt = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
        r = yt.channels().list(part="statistics,snippet", mine=True).execute()
        items = r.get("items", [])
        if not items:
            return None
        s = items[0].get("statistics", {})
        return {
            "subs": int(s.get("subscriberCount", 0)),
            "views": int(s.get("viewCount", 0)),
            "videos": int(s.get("videoCount", 0)),
            "title": items[0].get("snippet", {}).get("title", "?"),
        }
    except Exception as e:
        return {"error": str(e)[:100]}
    finally:
        if prev:
            os.environ["YT_CHANNEL_PREFIX"] = prev
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)


def _stage(subs: int) -> tuple[str, str]:
    """Devuelve (icono, mensaje) según subs actuales."""
    if subs >= 1000:
        return ("💰", "APLICA YPP full (1000+ subs)")
    if subs >= 500:
        return ("🎉", "APLICA YT Shopping + Super Thanks (500+ subs)")
    if subs >= 400:
        return ("🚀", "Casi listo — prepara aplicación")
    if subs >= 300:
        return ("🎯", "Acercándose (300+)")
    if subs >= 100:
        return ("📈", "Creciendo")
    return ("🌱", "Fase inicial")


def check_all() -> dict[str, Any]:
    from .notify_batch import add
    lines = ["🎯 <b>YPP watch — distancia monetización</b>"]
    results: dict[str, dict] = {}
    urgent_alerts: list[str] = []
    for prefix, name in CHANNELS:
        stats = _channel_stats(prefix)
        if not stats or stats.get("error"):
            lines.append(f"❌ {name}: {stats.get('error','sin acceso') if stats else 'no creds'}")
            results[name] = {"error": True}
            continue
        subs = stats["subs"]
        icon, msg = _stage(subs)
        results[name] = {"subs": subs, "views": stats["videos"], "stage": msg}
        # Distance to next milestone
        if subs < 500:
            gap = 500 - subs
            gap_msg = f"faltan {gap} subs → YT Shopping"
        elif subs < 1000:
            gap = 1000 - subs
            gap_msg = f"faltan {gap} subs → YPP full"
        else:
            gap_msg = "ya monetizable — verifica aplicación"
        lines.append(f"{icon} <b>{name}</b>: <b>{subs}</b> subs — {gap_msg}")
        if subs >= 500:
            urgent_alerts.append(f"🎉 {name} pasó 500 subs · <b>{msg}</b>")
        elif subs >= 400:
            urgent_alerts.append(f"🚀 {name} tiene {subs} subs · aplicación cerca")

    add("\n".join(lines))
    for alert in urgent_alerts:
        add(alert, urgent=True)
    return results
