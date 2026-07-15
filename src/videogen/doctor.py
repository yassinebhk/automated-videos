"""videogen doctor — verifica que el entorno está listo para generar/subir."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import requests
from rich.console import Console

from .config import MUSIC_DIR, SECRETS_DIR

console = Console()


class Check:
    def __init__(self, name: str):
        self.name = name
        self.ok = False
        self.detail = ""
        self.fix = ""


def check_ffmpeg() -> Check:
    c = Check("ffmpeg")
    if shutil.which("ffmpeg"):
        out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        c.ok = True
        c.detail = out.stdout.splitlines()[0] if out.stdout else "found"
    else:
        c.fix = "brew install ffmpeg"
    return c


def check_env_file() -> Check:
    c = Check(".env file")
    path = Path(".env")
    if path.exists():
        c.ok = True
        c.detail = "found"
    else:
        c.fix = "cp .env.example .env  # luego rellena las keys"
    return c


def check_gemini() -> Check:
    c = Check("GEMINI_API_KEY (script + Veo)")
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        c.fix = (
            "Sácala gratis (free tier 1500 req/día) en "
            "https://aistudio.google.com/app/apikey"
        )
        return c
    try:
        r = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
            timeout=10,
        )
        if r.status_code == 200:
            c.ok = True
            c.detail = "API reachable (free tier)"
        else:
            c.detail = f"HTTP {r.status_code}"
            c.fix = "Verifica key en https://aistudio.google.com/app/apikey"
    except Exception as e:
        c.detail = str(e)[:80]
    return c


def check_voice_engine() -> Check:
    c = Check("Motor de voz")
    engine = os.environ.get("VOICE_ENGINE", "edge").strip().lower()
    if engine == "elevenlabs":
        return check_elevenlabs()
    # Edge TTS: solo requiere el paquete instalado, sin key
    try:
        import edge_tts  # noqa: F401
        c.ok = True
        es = os.environ.get("EDGE_VOICE_ES", "es-ES-AlvaroNeural")
        en = os.environ.get("EDGE_VOICE_EN", "en-US-GuyNeural")
        c.detail = f"Edge TTS (gratis) — es={es}, en={en}"
    except ImportError:
        c.fix = "pip install edge-tts"
    return c


def check_elevenlabs() -> Check:
    c = Check("ELEVENLABS_API_KEY")
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key or key == "xxx":
        c.fix = "Crea cuenta en https://elevenlabs.io/ y mete la key en .env"
        return c
    try:
        r = requests.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": key},
            timeout=10,
        )
        if r.status_code == 200:
            sub = r.json().get("subscription", {})
            limit = sub.get("character_limit", 0)
            used = sub.get("character_count", 0)
            c.ok = True
            c.detail = f"chars: {used}/{limit} ({sub.get('tier', '?')})"
        else:
            c.detail = f"HTTP {r.status_code}"
    except Exception as e:
        c.detail = str(e)[:80]
    return c


def check_elevenlabs_voices() -> Check:
    c = Check("ELEVENLABS voice IDs")
    es = os.environ.get("ELEVENLABS_VOICE_ID_ES", "").strip()
    en = os.environ.get("ELEVENLABS_VOICE_ID_EN", "").strip()
    if not es or not en:
        c.fix = "Define ELEVENLABS_VOICE_ID_ES y _EN en .env (cópialas de la Voice Library)"
        return c
    c.ok = True
    c.detail = f"es={es[:10]}… en={en[:10]}…"
    return c


def check_pexels() -> Check:
    c = Check("PEXELS_API_KEY")
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key or key == "xxx":
        c.fix = "Pide key gratis en https://www.pexels.com/api/"
        return c
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search?query=test&per_page=1",
            headers={"Authorization": key},
            timeout=10,
        )
        if r.status_code == 200:
            c.ok = True
            c.detail = "API reachable"
        else:
            c.detail = f"HTTP {r.status_code}"
    except Exception as e:
        c.detail = str(e)[:80]
    return c


def check_youtube_oauth() -> Check:
    c = Check("YouTube OAuth client_secret")
    path = SECRETS_DIR / "youtube_client_secret.json"
    if path.exists():
        c.ok = True
        c.detail = str(path)
    else:
        c.fix = (
            "Crea proyecto en Google Cloud Console → habilita YouTube Data API v3 → "
            "OAuth credentials tipo Desktop App → descarga JSON como "
            f"{path}"
        )
    return c


def check_music() -> Check:
    c = Check("Música de fondo")
    tracks = list(MUSIC_DIR.rglob("*.mp3"))
    if tracks:
        c.ok = True
        c.detail = f"{len(tracks)} pista(s): {', '.join(t.name for t in tracks[:3])}"
    else:
        c.fix = (
            f"Mete al menos 1 MP3 en {MUSIC_DIR}/ "
            "(YouTube Audio Library, Pixabay, o Free Music Archive)"
        )
    return c


def run_doctor() -> bool:
    console.rule("[bold]videogen doctor")
    checks = [
        check_ffmpeg(),
        check_env_file(),
        check_gemini(),
        check_voice_engine(),
        check_pexels(),
        check_youtube_oauth(),
        check_music(),
    ]
    all_ok = True
    for c in checks:
        if c.ok:
            console.print(f"  [green]✓[/] {c.name}  [dim]{c.detail}[/]")
        else:
            all_ok = False
            console.print(f"  [red]✗[/] {c.name}  [yellow]{c.detail}[/]")
            if c.fix:
                console.print(f"      → [cyan]{c.fix}[/]")
    if all_ok:
        console.print("\n[bold green]Todo listo.[/] Prueba: [bold]videogen create \"¿Por qué los pulpos tienen 3 corazones?\"[/]")
    else:
        console.print("\n[bold red]Faltan cosas.[/] Resuelve los ✗ y vuelve a correr [bold]videogen doctor[/]")
    return all_ok
