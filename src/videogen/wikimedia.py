"""Fotos de figuras públicas vía Wikimedia Commons (licencias CC / dominio público).

Para temas de famosos (CR7, Musk, etc.) el stock no tiene caras. Wikimedia Commons
sí tiene fotos con licencia libre. Filtramos ESTRICTO a CC/PD y devolvemos la
atribución para ponerla en la descripción (requisito de CC-BY/BY-SA).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import requests
from PIL import Image

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "videogen/1.0 (educational shorts)"}

# Solo licencias realmente libres y usables comercialmente con atribución.
_ALLOWED_LICENSE = re.compile(
    r"(cc[\s-]?by([\s-]?sa)?|public domain|cc0|pd-|attribution)", re.IGNORECASE
)


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def fetch_cc_images(query: str, dest_dir: Path, n: int = 3) -> list[dict]:
    """Busca fotos CC/PD de `query` en Commons. Devuelve hasta n dicts:
    {path (1080x1920), author, license}. [] si no hay nada usable."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(
            API,
            params={
                "action": "query", "format": "json",
                "generator": "search", "gsrsearch": f"{query} portrait",
                "gsrnamespace": 6, "gsrlimit": 12,
                "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1280,
            },
            headers=UA, timeout=30,
        ).json()
    except Exception as e:
        print(f"  wikimedia búsqueda falló: {e}")
        return []

    pages = list(r.get("query", {}).get("pages", {}).values())
    out: list[dict] = []
    for p in pages:
        if len(out) >= n:
            break
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if not _ALLOWED_LICENSE.search(lic):
            continue
        url = ii.get("thumburl") or ii.get("url")
        if not url or not url.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        author = _strip_html(meta.get("Artist", {}).get("value", "")) or "Wikimedia Commons"
        try:
            img_bytes = requests.get(url, headers=UA, timeout=60).content
            key = hashlib.sha1(url.encode()).hexdigest()[:12]
            raw = dest_dir / f"{key}_raw.jpg"
            raw.write_bytes(img_bytes)
            out_path = dest_dir / f"{key}.jpg"
            _cover_1080x1920(raw, out_path)
            out.append({"path": str(out_path), "author": author[:60], "license": lic})
        except Exception as e:
            print(f"  wikimedia descarga falló: {e}")
            continue
    return out


def _cover_1080x1920(src: Path, dest: Path) -> None:
    """Cover-resize a 1080x1920 (recorta para llenar vertical)."""
    img = Image.open(src).convert("RGB")
    W, H = 1080, 1920
    sr, dr = img.width / img.height, W / H
    if sr > dr:
        nh = H
        nw = int(H * sr)
    else:
        nw = W
        nh = int(W / sr)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - W) // 2, (nh - H) // 2
    img.crop((left, top, left + W, top + H)).save(dest, "JPEG", quality=90)


def attribution_line(images: list[dict]) -> str:
    """Construye la línea de atribución para la descripción (requisito CC)."""
    if not images:
        return ""
    authors = []
    for im in images:
        a = im["author"]
        if a and a not in authors:
            authors.append(a)
    return "📸 Imágenes: " + "; ".join(authors) + " — vía Wikimedia Commons (CC)"
