"""Configuración central. Carga .env y expone settings."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

OUTPUT_DIR = ROOT / "output"
PENDING_DIR = OUTPUT_DIR / "pending_review"
APPROVED_DIR = OUTPUT_DIR / "approved"
UPLOADED_DIR = OUTPUT_DIR / "uploaded"
MUSIC_DIR = ROOT / "music"
ASSETS_DIR = ROOT / "assets"
SECRETS_DIR = ROOT / "secrets"
PROMPTS_DIR = ROOT / "prompts"

for d in (PENDING_DIR, APPROVED_DIR, UPLOADED_DIR, SECRETS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _require(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val or val.startswith("sk-ant-xxx") or val == "xxx":
        raise RuntimeError(
            f"Missing env var {key}. Copy .env.example to .env and fill it in."
        )
    return val


def elevenlabs_key() -> str:
    return _require("ELEVENLABS_API_KEY")


def elevenlabs_voice(lang: str) -> str:
    key = f"ELEVENLABS_VOICE_ID_{lang.upper()}"
    return _require(key)


def pexels_key() -> str:
    return _require("PEXELS_API_KEY")


def gemini_key() -> str | None:
    """Requerida para script (Gemini Flash) y opcional para Veo hook."""
    val = os.environ.get("GEMINI_API_KEY", "").strip()
    return val or None


def pollinations_token() -> str | None:
    """Opcional. Token de Pollinations (tier registrado, más límite)."""
    val = os.environ.get("POLLINATIONS_TOKEN", "").strip()
    return val or None


def telegram_token() -> str:
    return _require("TELEGRAM_BOT_TOKEN")


def telegram_chat_id() -> str | None:
    val = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return val or None


def default_duration() -> int:
    return int(os.environ.get("VIDEO_DEFAULT_DURATION_SECONDS", "60"))
