"""Genera un feed RSS de podcast a partir de los long-forms subidos a YT.

Por qué: Spotify España tiene 15M MAU; el género #1 en Spotify ES en 2026 es
true crime (Criminopatía ~250k oyentes/mes, Podium Podcast). Cada long-form
de este canal YA es narrativa 8-12 min = episodio perfecto de podcast. Con
un feed RSS válido, se puede enviar UNA sola vez a Spotify Podcasters + Apple
Podcasts Connect y a partir de ahí cada nuevo long-form aparece automático.

Estructura:
- El feed vive en docs/podcasts/feed.xml (servido por GitHub Pages).
- Los MP3 se copian a docs/podcasts/<slug>.mp3 después de cada long-form.
- Este módulo se llama al final de publish_long para actualizar el feed.

Cero coste, cero mantenimiento después del setup inicial.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

from .config import ROOT, UPLOADED_DIR


PODCASTS_DIR = ROOT / "docs" / "podcasts"

# Metadatos del podcast — la información que ve el listener en Spotify/Apple.
PODCAST_META = {
    "title": "WaitWhy — Estafas Españolas con Sentencia",
    "description": (
        "Los grandes fraudes, timos y escándalos españoles con sentencia firme, "
        "explicados en 8-12 minutos. Un caso por episodio. Fuentes: BOE, "
        "Audiencia Nacional, Tribunal Supremo. Nada inventado. "
        "También en YouTube: youtube.com/@waitwhy_ybb"
    ),
    "author": "WaitWhy",
    "email": "waitwhy.podcast@gmail.com",  # requerido por Apple Podcasts
    "language": "es",
    "category": "True Crime",  # categoría iTunes válida
    "explicit": "false",
    "site_url": "https://github.com/yassinebhk/automated-videos",
    # Public base URL que Spotify/Apple/iVoox usan para descargar MP3 + feed.
    # Usa jsDelivr CDN — espeja GitHub gratis, sirve con content-type
    # correcto (application/xml para .xml, audio/mpeg para .mp3). Sin setup.
    # Bandwidth ilimitado para archivos pequeños.
    "public_base": "https://cdn.jsdelivr.net/gh/yassinebhk/automated-videos@main/docs/podcasts",
    # Cover art (1400×1400 min, JPG/PNG). Si no existe, se skip.
    "cover_relpath": "cover.jpg",
}


def _slug_from_dir(d: Path) -> str:
    return d.name


def _extract_episode_from_source(slug_dir: Path) -> Optional[dict]:
    """Extrae metadatos de un long-form recién generado en output/uploaded/.
    Solo se usa desde el pipeline para añadir un episodio NUEVO al feed.
    """
    long_scripts = slug_dir / "long_scripts.json"
    mp3 = slug_dir / "voice_es.mp3"
    yt_json = slug_dir / "youtube_long.json"
    if not (long_scripts.exists() and mp3.exists()):
        return None
    try:
        data = json.loads(long_scripts.read_text(encoding="utf-8"))
    except Exception:
        return None
    es = data.get("es", {})
    title = es.get("title", "").strip()
    if not title:
        return None
    intro_text = es.get("intro", {}).get("text", "")
    description = intro_text.strip()[:900] or es.get("description", "")[:900]
    court = es.get("court_source", {}) or {}
    if court:
        parts = [court.get("tribunal", ""), court.get("sentencia", ""), court.get("fecha", "")]
        parts = [p for p in parts if p]
        if parts:
            description = description[:850] + f"\n\n📜 Fuente: {' · '.join(parts)}"
    pub_ts = mp3.stat().st_mtime
    pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
    duration_s = 0
    voice_json = slug_dir / "voice_es.json"
    if voice_json.exists():
        try:
            vj = json.loads(voice_json.read_text(encoding="utf-8"))
            duration_s = int(vj.get("duration_seconds", 0))
        except Exception:
            pass
    if duration_s == 0:
        duration_s = int(mp3.stat().st_size / (44100 * 2 * 2 / 8) * 0.8)
    slug = _slug_from_dir(slug_dir)
    yt_url = ""
    if yt_json.exists():
        try:
            yj = json.loads(yt_json.read_text(encoding="utf-8"))
            yt_url = yj.get("es", "")
        except Exception:
            pass
    return {
        "slug": slug,
        "title": title,
        "description": description,
        "pub_ts": pub_ts,
        "duration_s": duration_s,
        "mp3_src": str(mp3),
        "size_bytes": mp3.stat().st_size,
        "yt_url": yt_url,
    }


def _persist_new_episode(ep: dict) -> None:
    """Persiste un episodio nuevo en docs/podcasts/:
    - Copia MP3 a <slug>.mp3
    - Guarda metadata en <slug>.json (para que futuros runs puedan
      reconstruir el feed sin depender de output/uploaded/)."""
    PODCASTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = ep["slug"]
    dst_mp3 = PODCASTS_DIR / f"{slug}.mp3"
    src_mp3 = Path(ep["mp3_src"])
    if not dst_mp3.exists() or dst_mp3.stat().st_size != src_mp3.stat().st_size:
        shutil.copy2(src_mp3, dst_mp3)
    # Metadata compacta persistente
    meta_out = {k: ep[k] for k in ("slug", "title", "description", "pub_ts",
                                    "duration_s", "size_bytes", "yt_url")}
    (PODCASTS_DIR / f"{slug}.json").write_text(
        json.dumps(meta_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_all_episodes_from_docs() -> list[dict]:
    """Escanea docs/podcasts/*.json para reconstruir la lista completa de
    episodios ya publicados en runs anteriores (los MP3 están commiteados)."""
    if not PODCASTS_DIR.exists():
        return []
    episodes = []
    for json_path in PODCASTS_DIR.glob("*.json"):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            data["pub_dt"] = datetime.fromtimestamp(data["pub_ts"], tz=timezone.utc)
            episodes.append(data)
        except Exception as e:
            print(f"  podcast: skip {json_path.name} ({type(e).__name__}: {e})")
    return episodes


def _format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _build_rss(episodes: list[dict]) -> str:
    """Construye XML RSS 2.0 con extensiones iTunes/Apple + Spotify."""
    meta = PODCAST_META
    now_rfc822 = format_datetime(datetime.now(timezone.utc))
    cover_url = f"{meta['public_base']}/{meta['cover_relpath']}"
    items_xml = []
    # Orden descendente por fecha (más reciente primero)
    for ep in sorted(episodes, key=lambda e: e["pub_dt"], reverse=True):
        mp3_url = f"{meta['public_base']}/{ep['slug']}.mp3"
        pub_rfc = format_datetime(ep["pub_dt"])
        dur = _format_duration(ep["duration_s"])
        yt_line = f"\n\n📺 YouTube: {ep['yt_url']}" if ep["yt_url"] else ""
        desc = xml_escape(ep["description"] + yt_line)
        title = xml_escape(ep["title"])
        items_xml.append(f"""    <item>
      <title>{title}</title>
      <description><![CDATA[{ep["description"]}{yt_line}]]></description>
      <pubDate>{pub_rfc}</pubDate>
      <enclosure url="{mp3_url}" length="{ep['size_bytes']}" type="audio/mpeg"/>
      <guid isPermaLink="false">{ep['slug']}</guid>
      <itunes:duration>{dur}</itunes:duration>
      <itunes:explicit>{meta['explicit']}</itunes:explicit>
      <itunes:episodeType>full</itunes:episodeType>
    </item>""")

    items_str = "\n".join(items_xml)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{xml_escape(meta['title'])}</title>
    <link>{meta['site_url']}</link>
    <description><![CDATA[{meta['description']}]]></description>
    <language>{meta['language']}</language>
    <copyright>© {datetime.now(timezone.utc).year} {xml_escape(meta['author'])}</copyright>
    <lastBuildDate>{now_rfc822}</lastBuildDate>
    <atom:link href="{meta['public_base']}/feed.xml" rel="self" type="application/rss+xml"/>
    <itunes:author>{xml_escape(meta['author'])}</itunes:author>
    <itunes:summary><![CDATA[{meta['description']}]]></itunes:summary>
    <itunes:owner>
      <itunes:name>{xml_escape(meta['author'])}</itunes:name>
      <itunes:email>{meta['email']}</itunes:email>
    </itunes:owner>
    <itunes:image href="{cover_url}"/>
    <itunes:category text="{meta['category']}"/>
    <itunes:explicit>{meta['explicit']}</itunes:explicit>
    <itunes:type>episodic</itunes:type>
{items_str}
  </channel>
</rss>
"""


def rebuild_feed(new_slug: Optional[str] = None) -> Optional[Path]:
    """Regenera docs/podcasts/feed.xml.

    Estrategia hybrid:
    1. Si `new_slug` está dado y existe en output/uploaded/<new_slug>/, extrae
       metadata + copia el MP3 a docs/podcasts/ + persiste JSON. Esto es lo que
       hace un run reciente que acaba de generar un long-form nuevo.
    2. Siempre carga TODOS los episodios ya persistidos en docs/podcasts/*.json
       (que incluyen los MP3s de runs anteriores, ya commiteados).
    3. Regenera feed.xml combinando lo anterior + el nuevo.
    """
    PODCASTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Nuevo episodio (si aplica)
    if new_slug:
        slug_dir = UPLOADED_DIR / new_slug
        if slug_dir.exists():
            ep = _extract_episode_from_source(slug_dir)
            if ep:
                try:
                    _persist_new_episode(ep)
                    print(f"  podcast: ✅ persistido episodio nuevo → {ep['slug']}")
                except Exception as e:
                    print(f"  podcast: persist fail {ep['slug']} ({type(e).__name__}: {e})")

    # 2) Cargar todos los episodios ya persistidos
    all_eps = _load_all_episodes_from_docs()
    if not all_eps:
        print("  podcast: 0 episodios persistidos, no genero feed")
        return None

    # 3) Escribir feed
    xml = _build_rss(all_eps)
    feed_path = PODCASTS_DIR / "feed.xml"
    feed_path.write_text(xml, encoding="utf-8")
    print(f"  podcast: ✅ feed regenerado con {len(all_eps)} episodios → {feed_path}")
    return feed_path
