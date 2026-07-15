"""Generación de script bilingüe con Gemini (Google AI Studio, free tier)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from google import genai
from google.genai import types

from .config import PROMPTS_DIR, gemini_key
from .models import GeneratedLongScripts, GeneratedScripts, TTNativeScript


SYSTEM_PROMPT_PATH = PROMPTS_DIR / "script_system.md"
LONG_PROMPT_PATH = PROMPTS_DIR / "long_form_system.md"
TT_NATIVE_PROMPT_PATH = PROMPTS_DIR / "tt_native_system.md"
NICHE_PROMPT_PATH = PROMPTS_DIR / "niche.md"
# Cadena de modelos: si el primario da 503/429, cae al siguiente.
MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"]


def _system_prompt() -> str:
    """Reglas de formato + brief del nicho (si existe niche.md)."""
    base = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    if NICHE_PROMPT_PATH.exists():
        niche = NICHE_PROMPT_PATH.read_text(encoding="utf-8")
        return f"{niche}\n\n---\n\n{base}"
    return base


def _slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "video"


def generate_scripts(topic: str) -> GeneratedScripts:
    """Llama a Gemini y devuelve scripts bilingües validados."""
    api_key = gemini_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY no configurada. Sácala gratis en "
            "https://aistudio.google.com/app/apikey y mete en .env"
        )

    system = _system_prompt()

    client = genai.Client(api_key=api_key)
    import time as _time

    cfg = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        temperature=0.85,
        max_output_tokens=16384,  # scripts detallados bilingües pueden ser largos
    )
    contents = f"Topic: {topic}\n\nGenerate the bilingual script as JSON."

    last_err = None
    for model in MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model, contents=contents, config=cfg
                )
                raw = (response.text or "").strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE)
                data = json.loads(raw)  # un JSON malformado/truncado reintenta
                if not data.get("slug"):
                    data["slug"] = _slugify(topic)
                return GeneratedScripts.model_validate(data)
            except json.JSONDecodeError as e:
                last_err = e
                print(f"  {model}: JSON inválido/truncado ({attempt+1}/3), reintento...")
                _time.sleep(2)
            except Exception as e:
                last_err = e
                if any(s in str(e) for s in ("503", "429", "UNAVAILABLE")):
                    wait = 4 * (attempt + 1)
                    print(f"  {model} busy ({attempt+1}/3), reintento en {wait}s...")
                    _time.sleep(wait)
                else:
                    raise
        print(f"  {model} no disponible, probando siguiente modelo...")
    raise RuntimeError(f"Ningún modelo Gemini devolvió script válido: {last_err}")


def _ensure_outro(data: dict, lang: str) -> None:
    """Si Gemini olvida el outro en un long-form, inyecta uno genérico con
    follow ask explícito (regla del proyecto) para evitar crash de validación."""
    loc = data.get(lang)
    if not isinstance(loc, dict):
        return
    if loc.get("outro") and isinstance(loc.get("outro"), dict) and loc["outro"].get("text"):
        return
    chapters = loc.get("chapters") or []
    topic_hint = (data.get("topic") or loc.get("title") or "").strip()
    if lang == "es":
        text = (
            f"Y esto es solo la punta del iceberg sobre {topic_hint or 'este tema'}. "
            f"Si te ha volado la cabeza, suscríbete y te cuento una historia así cada semana."
        )
    else:
        text = (
            f"And this is just the tip of the iceberg on {topic_hint or 'this topic'}. "
            f"If it blew your mind, subscribe — one mind-blowing story every week."
        )
    visual_keywords = chapters[-1].get("visual_keywords", [])[:3] if chapters else []
    loc["outro"] = {
        "text": text, "visual_keywords": visual_keywords, "approx_seconds": 55.0,
    }


def _long_system_prompt() -> str:
    base = LONG_PROMPT_PATH.read_text(encoding="utf-8")
    if NICHE_PROMPT_PATH.exists():
        niche = NICHE_PROMPT_PATH.read_text(encoding="utf-8")
        return f"{niche}\n\n---\n\n{base}"
    return base


def generate_long_scripts(topic: str, target_minutes: int = 7) -> GeneratedLongScripts:
    """Genera guion long-form bilingüe (intro + capítulos + outro).
    Mismo patrón de robustez que generate_scripts (cadena de modelos + retry)."""
    api_key = gemini_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no configurada.")

    system = _long_system_prompt()
    client = genai.Client(api_key=api_key)
    import time as _time

    # Long-form pide más texto → más tokens
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        temperature=0.8,
        max_output_tokens=32768,
    )
    contents = (
        f"Topic: {topic}\nTarget duration: {target_minutes} minutes per language.\n\n"
        f"Generate the bilingual LONG-FORM script as JSON. "
        f"Remember: 3-5 chapters that map 1:1 between ES and EN."
    )

    last_err = None
    for model in MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model, contents=contents, config=cfg
                )
                raw = (response.text or "").strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE)
                data = json.loads(raw)
                if not data.get("slug"):
                    data["slug"] = _slugify(topic)
                data.setdefault("target_minutes", target_minutes)
                # Fallback robusto si a Gemini se le olvida el outro
                _ensure_outro(data, "es")
                _ensure_outro(data, "en")
                return GeneratedLongScripts.model_validate(data)
            except json.JSONDecodeError as e:
                last_err = e
                print(f"  {model}: long JSON inválido ({attempt+1}/3), reintento...")
                _time.sleep(2)
            except Exception as e:
                last_err = e
                if any(s in str(e) for s in ("503", "429", "UNAVAILABLE")):
                    wait = 4 * (attempt + 1)
                    print(f"  {model} busy ({attempt+1}/3), reintento en {wait}s...")
                    _time.sleep(wait)
                else:
                    raise
        print(f"  {model} no disponible, siguiente modelo...")
    raise RuntimeError(f"Ningún modelo Gemini devolvió long script válido: {last_err}")


def _tt_native_system_prompt() -> str:
    base = TT_NATIVE_PROMPT_PATH.read_text(encoding="utf-8")
    if NICHE_PROMPT_PATH.exists():
        niche = NICHE_PROMPT_PATH.read_text(encoding="utf-8")
        return f"{niche}\n\n---\n\n{base}"
    return base


def generate_tt_native_script(topic: str, fmt: str | None = None) -> TTNativeScript:
    """Genera guion TT-first (28-34s, 9:16, sin música, comment-bait).
    Si fmt no es None, fuerza el formato (series|list|pov|curiosity); si es None,
    Gemini elige el mejor según el topic.
    """
    api_key = gemini_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no configurada.")
    system = _tt_native_system_prompt()
    client = genai.Client(api_key=api_key)
    import time as _time

    cfg = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        temperature=0.9,
        max_output_tokens=4096,
    )
    contents = f"Topic: {topic}\n"
    if fmt:
        contents += f"Format: USE \"{fmt}\" exactly.\n"
    contents += "Generate the TikTok-native script as JSON. Lang: ES."

    last_err = None
    for model in MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model, contents=contents, config=cfg
                )
                raw = (response.text or "").strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE)
                data = json.loads(raw)
                if not data.get("slug"):
                    data["slug"] = _slugify(topic) + "-tt"
                return TTNativeScript.model_validate(data)
            except json.JSONDecodeError as e:
                last_err = e
                print(f"  {model}: TT JSON inválido ({attempt+1}/3), reintento...")
                _time.sleep(2)
            except Exception as e:
                last_err = e
                if any(s in str(e) for s in ("503", "429", "UNAVAILABLE")):
                    wait = 4 * (attempt + 1)
                    print(f"  {model} busy ({attempt+1}/3), reintento en {wait}s...")
                    _time.sleep(wait)
                else:
                    raise
        print(f"  {model} no disponible, siguiente modelo...")
    raise RuntimeError(f"Ningún modelo Gemini devolvió TT script válido: {last_err}")


def save_tt_native_script(s: TTNativeScript, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "tt_native_script.json"
    path.write_text(s.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_tt_native_script(dir_: Path) -> TTNativeScript:
    return TTNativeScript.model_validate_json(
        (dir_ / "tt_native_script.json").read_text(encoding="utf-8")
    )


def save_long_scripts(scripts: GeneratedLongScripts, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "long_scripts.json"
    path.write_text(scripts.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_long_scripts(dir_: Path) -> GeneratedLongScripts:
    return GeneratedLongScripts.model_validate_json(
        (dir_ / "long_scripts.json").read_text(encoding="utf-8")
    )


def save_scripts(scripts: GeneratedScripts, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "scripts.json"
    path.write_text(scripts.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_scripts(dir_: Path) -> GeneratedScripts:
    return GeneratedScripts.model_validate_json(
        (dir_ / "scripts.json").read_text(encoding="utf-8")
    )
