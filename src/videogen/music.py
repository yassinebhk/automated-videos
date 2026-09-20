"""Música de fondo (BGM) libre y gratuita, compartida por los pipelines.

20/09: Pixabay cerró el acceso a su API de audio (HTTP 403 Access denied), así que
Freesound (CC0/CC-BY, requiere FREESOUND_API_KEY, 60 req/min) pasa a ser la fuente
principal de música corta. `fetch_bgm` intenta Pixabay (por si vuelve) y cae a Freesound.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")


def freesound_track(queries, out_path: Path, min_dur: int = 15) -> Path | None:
    """Descarga 1 preview mp3 de Freesound que dure >= min_dur. None si falla."""
    import requests
    key = os.environ.get("FREESOUND_API_KEY", "").strip()
    if not key:
        return None
    headers = {"Authorization": f"Token {key}"}
    for query in [q for q in queries if q]:
        try:
            r = requests.get(
                "https://freesound.org/apiv2/search/text/",
                headers=headers,
                params={"query": query, "filter": f"duration:[{min_dur} TO 600]",
                        "fields": "id,name,duration,previews", "sort": "rating_desc",
                        "page_size": 20},
                timeout=30,
            )
            if r.status_code == 429:
                time.sleep(3)
                continue
            if r.status_code != 200:
                continue
            for hit in r.json().get("results", []):
                url = (hit.get("previews") or {}).get("preview-hq-mp3")
                if not url:
                    continue
                data = requests.get(url, timeout=60).content
                if data and len(data) > 5000:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(data)
                    print(f"  music: Freesound OK '{query}' ({len(data)}b)")
                    return out_path
        except Exception as e:
            print(f"  music: freesound '{query}' fail: {str(e)[:60]}")
    return None


def pixabay_track(queries, out_path: Path) -> Path | None:
    """Intenta Pixabay audio (por si recuperan el acceso). Hoy da 403; None entonces."""
    import random
    import requests
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        return None
    try:
        q = random.choice([q for q in queries if q] or ["upbeat"])
        r = requests.get("https://pixabay.com/api/audio/",
                         params={"key": key, "q": q, "per_page": 20, "safesearch": "true"},
                         headers={"User-Agent": _UA}, timeout=30)
        data = r.json()  # Pixabay manda text/html; requests parsea el body igual
        for h in data.get("hits", []):
            u = h.get("audio") or h.get("url") or ""
            if u:
                b = requests.get(u, timeout=60).content
                if b and len(b) > 5000:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(b)
                    return out_path
    except Exception as e:
        print(f"  music: pixabay fail ({str(e)[:50]})")
    return None


def fetch_bgm(queries, out_path: Path, min_dur: int = 15) -> Path | None:
    """BGM libre: Pixabay (si vuelve) → Freesound. Devuelve out_path o None."""
    return pixabay_track(queries, out_path) or freesound_track(queries, out_path, min_dur)
