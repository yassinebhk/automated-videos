"""LLM client unificado con fallback automático Gemini → Cerebras → Groq.

Cadena de fallback (todo GRATIS):
  1. Gemini 2.5 (20 req/día/modelo). Cuando 429/503 → siguiente.
  2. Cerebras Cloud — ~1M tokens/día en Llama 3.3 70B, latencia <1s.
  3. Groq — gpt-oss-120b JSON, gpt-oss-20b texto plano.

Cerebras es el fallback preferido porque tiene el mayor cupo diario
y latencia excepcional. Groq queda como red final por si Cerebras
también rate-limita.

Requiere:
  - GEMINI_API_KEY (aistudio.google.com)
  - CEREBRAS_API_KEY (cloud.cerebras.ai) — opcional, salta si falta
  - GROQ_API_KEY (console.groq.com)     — opcional, salta si falta

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
CEREBRAS_MODEL = "llama-3.3-70b"  # free tier Cerebras, 128k ctx
CEREBRAS_MODEL_FAST = "llama3.1-8b"  # fallback rápido si el 70b rate-limita
GROQ_MODEL = "openai/gpt-oss-120b"  # free tier Groq — 131k ctx, alta calidad
GROQ_MODEL_FAST = "openai/gpt-oss-20b"  # fallback más rápido


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


def _try_cerebras_json(prompt: str, schema: dict | None,
                         max_tokens: int, temperature: float) -> tuple[dict | None, str]:
    """Fallback a Cerebras Cloud (llama-3.3-70b free). API OpenAI-compatible."""
    key = os.environ.get("CEREBRAS_API_KEY", "").strip()
    if not key:
        return None, "no CEREBRAS_API_KEY"

    def _call(model: str) -> tuple[dict | None, str]:
        try:
            import requests
            if schema:
                schema_str = json.dumps(schema, ensure_ascii=False)
                sys_prompt = (
                    "Devuelve SOLO JSON válido siguiendo este schema. "
                    "Sin comentarios, sin markdown fences, sin texto extra.\n"
                    f"Schema:\n{schema_str}"
                )
                body = {
                    "model": model,
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
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            r = requests.post(
                "https://api.cerebras.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                          "Content-Type": "application/json"},
                json=body, timeout=60,
            )
            if r.status_code >= 300:
                return None, f"HTTP {r.status_code}: {r.text[:150]}"
            content = r.json()["choices"][0]["message"]["content"]
            if schema:
                try:
                    return json.loads(content), ""
                except Exception:
                    import re as _re
                    clean = _re.sub(r"^```(?:json)?\s*|\s*```$", "", content,
                                       flags=_re.MULTILINE)
                    try:
                        return json.loads(clean), ""
                    except Exception as je:
                        return None, f"JSON parse: {je}"
            return {"text": content.strip()}, ""
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"

    data, err = _call(CEREBRAS_MODEL)
    if data is not None and (schema or data.get("text")):
        return data, ""
    print(f"  cerebras {CEREBRAS_MODEL} fail ({err[:80]}) → intento {CEREBRAS_MODEL_FAST}")
    data2, err2 = _call(CEREBRAS_MODEL_FAST)
    if data2 is not None and (schema or data2.get("text")):
        return data2, ""
    return None, f"{CEREBRAS_MODEL}={err[:60]} · {CEREBRAS_MODEL_FAST}={err2[:60]}"


def _try_groq_json(prompt: str, schema: dict | None,
                     max_tokens: int, temperature: float) -> tuple[dict | None, str]:
    """Fallback a Groq (gpt-oss-120b free). Con retry a modelo más rápido."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None, "no GROQ_API_KEY"

    def _call(model: str) -> tuple[dict | None, str]:
        try:
            import requests
            if schema:
                schema_str = json.dumps(schema, ensure_ascii=False)
                sys_prompt = (
                    "Devuelve SOLO JSON válido siguiendo este schema. "
                    "Sin comentarios, sin markdown fences, sin texto extra.\n"
                    f"Schema:\n{schema_str}"
                )
                body = {
                    "model": model,
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
                    "model": model,
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
                return None, f"HTTP {r.status_code}: {r.text[:150]}"
            content = r.json()["choices"][0]["message"]["content"]
            if schema:
                try:
                    return json.loads(content), ""
                except Exception as je:
                    return None, f"JSON parse: {je}"
            return {"text": content.strip()}, ""
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"

    # Para JSON usa el grande (calidad), para texto plano el rápido (menos
    # reasoning tokens que dejan content vacío en gpt-oss-120b)
    primary = GROQ_MODEL if schema else GROQ_MODEL_FAST
    secondary = GROQ_MODEL_FAST if schema else GROQ_MODEL
    data, err = _call(primary)
    # Detecta content vacío (reasoning consumió todo) → fallback
    if data is not None:
        if not schema and not data.get("text"):
            print(f"  groq {primary}: content vacío (reasoning) → intento {secondary}")
        else:
            return data, ""
    else:
        print(f"  groq {primary} fail ({err[:80]}) → intento {secondary}")
    data2, err2 = _call(secondary)
    if data2 is not None:
        if schema or data2.get("text"):
            return data2, ""
    return None, f"{primary}={err[:60]} · {secondary}={err2[:60]}"


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
    print(f"  llm: gemini fail ({gerr[:120]}) → intento cerebras")
    data, cerr = _try_cerebras_json(prompt, schema, max_tokens, temperature)
    if data is not None:
        print(f"  llm: ✅ cerebras rescató el request")
        return data
    print(f"  llm: cerebras fail ({cerr[:120]}) → intento groq")
    data, ferr = _try_groq_json(prompt, schema, max_tokens, temperature)
    if data is not None:
        print(f"  llm: ✅ groq rescató el request")
        return data
    print(f"  llm: ❌ tres LLMs fallaron · gemini={gerr[:60]} · cerebras={cerr[:60]} · groq={ferr[:60]}")
    return None


def generate_text(prompt: str, max_tokens: int = 2000,
                    temperature: float = 0.9) -> str:
    """Genera texto plano con fallback. Retorna '' si falla."""
    data = generate_json(prompt, schema=None, max_tokens=max_tokens,
                          temperature=temperature)
    if not data:
        return ""
    return str(data.get("text", "")).strip()
