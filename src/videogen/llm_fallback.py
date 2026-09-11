"""LLM client unificado con fallback automático Gemini → Groq.

Groq ofrece Llama 3.3 70B GRATIS con rate limit por MINUTO (30 req/min)
sin daily cap agresivo. Cuando Gemini free tier (20 req/día/modelo)
se satura con 429, caemos automáticamente a Groq.

Requiere GROQ_API_KEY (gratis en console.groq.com).

Uso:
    from videogen.llm_fallback import generate_json, generate_text
    data = generate_json(prompt, schema)  # devuelve dict o None
    text = generate_text(prompt)          # devuelve str o ''
"""
from __future__ import annotations

import json
import os
import time
from typing import Any


GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
GROQ_MODEL = "llama-3.3-70b-versatile"  # free tier Groq


def _try_gemini_json(prompt: str, schema: dict | None,
                       max_tokens: int, temperature: float) -> tuple[dict | None, str]:
    """Devuelve (data, error_msg). data=None si falla."""
    try:
        from google import genai
        from google.genai import types
        from .config import gemini_key
        key = gemini_key()
        if not key:
            return None, "no gemini key"
    except Exception as e:
        return None, f"gemini import fail: {e}"

    client = genai.Client(api_key=key)
    last_err = ""
    for model in GEMINI_MODELS:
        for attempt in range(2):
            try:
                cfg = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
                if schema:
                    cfg.response_mime_type = "application/json"
                    cfg.response_schema = schema
                resp = client.models.generate_content(
                    model=model, contents=prompt, config=cfg,
                )
                text = (resp.text or "").strip()
                if schema:
                    try:
                        return json.loads(text), ""
                    except Exception:
                        # Intenta limpiar ```json code fences
                        import re as _re
                        clean = _re.sub(r"^```(?:json)?\s*|\s*```$", "", text,
                                          flags=_re.MULTILINE)
                        try:
                            return json.loads(clean), ""
                        except Exception as je:
                            last_err = f"{model} JSON parse: {je}"
                            continue
                # Sin schema, envolvemos en dict para consistencia
                return {"text": text}, ""
            except Exception as e:
                s = str(e)
                last_err = f"{model}: {type(e).__name__}: {s[:200]}"
                if "429" in s or "RESOURCE_EXHAUSTED" in s:
                    # Rate limit → siguiente modelo
                    break
                if "503" in s or "UNAVAILABLE" in s:
                    time.sleep(3 * (attempt + 1))
                    continue
                # Otro error → siguiente modelo
                break
    return None, last_err


def _try_groq_json(prompt: str, schema: dict | None,
                     max_tokens: int, temperature: float) -> tuple[dict | None, str]:
    """Fallback a Groq (Llama 3.3 70B free). JSON mode via prompt eng."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None, "no GROQ_API_KEY"
    try:
        import requests
        # Enriquece prompt con instrucción JSON si hay schema
        if schema:
            schema_str = json.dumps(schema, ensure_ascii=False)
            sys_prompt = (
                "Devuelve SOLO JSON válido siguiendo este schema. "
                "Sin comentarios, sin markdown fences, sin texto extra.\n"
                f"Schema:\n{schema_str}"
            )
            body = {
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            }
        else:
            body = {
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}",
                      "Content-Type": "application/json"},
            json=body, timeout=60,
        )
        if r.status_code >= 300:
            return None, f"groq HTTP {r.status_code}: {r.text[:200]}"
        content = r.json()["choices"][0]["message"]["content"]
        if schema:
            try:
                return json.loads(content), ""
            except Exception as je:
                return None, f"groq JSON parse: {je}"
        return {"text": content.strip()}, ""
    except Exception as e:
        return None, f"groq: {type(e).__name__}: {e}"


def generate_json(prompt: str, schema: dict | None = None,
                    max_tokens: int = 3000,
                    temperature: float = 0.9) -> dict | None:
    """Genera JSON estructurado con Gemini + fallback Groq.

    Devuelve dict con datos parseados, o None si ambos fallan.
    Si schema=None, devuelve {"text": <string>}.
    """
    data, gerr = _try_gemini_json(prompt, schema, max_tokens, temperature)
    if data is not None:
        return data
    print(f"  llm: gemini fail ({gerr[:150]}) → intento groq")
    data, ferr = _try_groq_json(prompt, schema, max_tokens, temperature)
    if data is not None:
        print(f"  llm: ✅ groq rescató el request")
        return data
    print(f"  llm: ❌ ambos LLMs fallaron · gemini={gerr[:80]} · groq={ferr[:80]}")
    return None


def generate_text(prompt: str, max_tokens: int = 2000,
                    temperature: float = 0.9) -> str:
    """Genera texto plano con fallback. Retorna '' si falla."""
    data = generate_json(prompt, schema=None, max_tokens=max_tokens,
                          temperature=temperature)
    if not data:
        return ""
    return str(data.get("text", "")).strip()
