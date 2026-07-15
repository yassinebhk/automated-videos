"""Cross-posting semi-manual a varias redes (multiplica alcance gratis).

No hay API gratis para publicar en IG/FB/Snap/Pinterest sin aprobación business,
así que abrimos el uploader de cada una + dejamos el caption listo. El usuario
arrastra el archivo (la variante sin música, para poder añadir audio trending).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# url: uploader web · app_only: solo desde móvil
PLATFORMS = {
    "tiktok":    {"name": "TikTok",          "url": "https://www.tiktok.com/upload?lang=es", "note": "añade audio trending"},
    "instagram": {"name": "Instagram Reels", "url": "https://www.instagram.com/",            "note": "+ Crear → Reel"},
    "facebook":  {"name": "Facebook Reels",  "url": "https://www.facebook.com/reels/create/", "note": ""},
    "pinterest": {"name": "Pinterest",       "url": "https://www.pinterest.com/pin-creation-tool/", "note": "Pin de vídeo"},
    "snapchat":  {"name": "Snapchat Spotlight", "url": "https://my.snapchat.com/",           "note": "mejor desde la app móvil"},
}


def build_caption(loc) -> str:
    """Caption universal: título + hashtags + tags de alcance."""
    base_tags = ["#fyp", "#parati", "#reels", "#shorts", "#viral"]
    tags = list(dict.fromkeys([h for h in loc.hashtags] + base_tags))
    return f"{loc.title}\n\n{' '.join(tags)}"


def _clipboard(text: str) -> bool:
    if sys.platform == "darwin":
        try:
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
            return True
        except Exception:
            return False
    return False


def crosspost_file(slug_dir: Path, lang: str) -> Path | None:
    """Archivo a cross-postear: versión share (1080p comprimida, ~12MB) de la
    versión CON música royalty-free + voz clara. Para videos narrados, esto es
    autosuficiente: se sube tal cual, sin añadir canción que tape la voz."""
    from . import compose

    full = slug_dir / f"video_{lang}_vertical.mp4"  # voz + música royalty-free
    if not full.exists():
        return None
    share = slug_dir / f"share_{lang}.mp4"
    if not share.exists():
        try:
            compose.make_share(full, share)
        except Exception:
            return full
    return share


def open_desktop(slug_dir: Path, lang: str, loc, platforms: list[str] | None = None) -> None:
    """Abre los uploaders web + copia caption + revela el archivo (flujo escritorio)."""
    platforms = platforms or list(PLATFORMS.keys())
    caption = build_caption(loc)
    f = crosspost_file(slug_dir, lang)
    _clipboard(caption)
    print("── Cross-posting ──")
    print(f"Archivo: {f}")
    print("Caption copiado al portapapeles.\n")
    for key in platforms:
        p = PLATFORMS.get(key)
        if not p:
            continue
        note = f" — {p['note']}" if p["note"] else ""
        print(f"  {p['name']}: {p['url']}{note}")
        if sys.platform == "darwin":
            subprocess.run(["open", p["url"]])
    if sys.platform == "darwin" and f:
        subprocess.run(["open", "-R", str(f)])
