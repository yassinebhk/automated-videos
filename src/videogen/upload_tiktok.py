"""Upload a TikTok (semi-automatizado).

La Content Posting API de TikTok requiere aprobación de app (semanas de espera)
y solo permite ciertos tipos de publicación. Para el MVP:

1. Copiamos el archivo a una ruta predecible
2. Abrimos https://www.tiktok.com/upload en el navegador
3. Mostramos el caption listo para pegar (con hashtags)

Cuando tengas Content Posting API aprobada, sustituye `open_uploader` por
una llamada HTTP a https://open.tiktokapis.com/v2/post/publish/video/init/
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload?lang=en"


def _copy_to_clipboard(text: str) -> bool:
    if sys.platform == "darwin":
        try:
            proc = subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
            return proc.returncode == 0
        except Exception:
            return False
    return False


def open_uploader(video_path: Path, caption: str, hashtags: list[str]) -> None:
    full_caption = f"{caption}\n\n{' '.join(hashtags)}"
    print("\n── TikTok upload ──")
    print(f"  Archivo listo: {video_path}")
    print(f"  Abrir manualmente y arrastrar el archivo.")
    if _copy_to_clipboard(full_caption):
        print("  Caption copiado al portapapeles. Pégalo en la descripción.")
    else:
        print(f"  Caption:\n{full_caption}")

    # Abre el uploader en el navegador y revela el archivo en Finder
    if sys.platform == "darwin":
        subprocess.run(["open", TIKTOK_UPLOAD_URL])
        subprocess.run(["open", "-R", str(video_path)])
    else:
        print(f"  Abre: {TIKTOK_UPLOAD_URL}")
