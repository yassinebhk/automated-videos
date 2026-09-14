"""Auto-refresh del pool ambient — genera topics nuevos con Gemini cada 14d.

Objetivo: evitar que el canal se estanque en los 22 topics estáticos y
sume variaciones que se están buscando actualmente en YT (nuevas
frecuencias virales, nuevos usos, nuevas combinaciones).

Guarda en `output/dynamic_topics_ambient.json`. El pipeline lo fusiona
con el pool estático (dedup por key).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from ..config import ROOT

DYNAMIC_PATH = ROOT / "output" / "dynamic_topics_ambient.json"
REFRESH_INTERVAL_DAYS = 14


def _load_dynamic() -> dict:
    if not DYNAMIC_PATH.exists():
        return {}
    try:
        return json.loads(DYNAMIC_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_dynamic(data: dict) -> None:
    DYNAMIC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DYNAMIC_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_due() -> bool:
    d = _load_dynamic()
    gen = d.get("generated_at")
    if not gen:
        return True
    try:
        dt = datetime.fromisoformat(gen)
        return (datetime.now(timezone.utc) - dt) > timedelta(days=REFRESH_INTERVAL_DAYS)
    except Exception:
        return True


def refresh_ambient_topics(n: int = 5) -> list[dict] | None:
    """Genera N topics ambient nuevos con Gemini/fallback."""
    from . import topic_pool
    from ..llm_fallback import generate_json

    existing_keys = [t["key"] for t in topic_pool.all_topics()]
    existing_keys += [t.get("key") for t in _load_dynamic().get("topics", [])]

    prompt = f"""Genera {n} topics NUEVOS para el canal YouTube "MenteEnCalma"
(música ambient/relax ES). NO repitas ninguno de estos:
{', '.join(existing_keys)}

Sugiere topics basados en búsquedas trending YT ES 2026:
- Frecuencias específicas emergentes (852Hz, 174Hz, 963Hz, etc.)
- Combinaciones (lluvia + piano, mar + flauta india, etc.)
- Usos específicos (yoga vinyasa, meditación mindfulness, pilates,
  siesta 30 min, power nap, spa, masaje relajante)
- Nichos que crecen (ASMR ambient, chakras específicos, mantras,
  frecuencia solfeggio 396Hz para miedo, etc.)

Cada topic devuelve estructura exacta:
{{
  "key": "slug_snake_case_unico",
  "mood_type": "binaural" | "pixabay",
  "carrier_hz": <int solo si binaural, ej 200 para alpha, 528 para solfeggio; 0 si noise>,
  "beat_hz": <int solo si binaural, 4-40 rango; 0 si noise>,
  "wave": "alpha" | "beta" | "theta" | "delta" | "gamma" | "solfeggio" | "noise_white" | "noise_pink" | "noise_brown" | null (si pixabay),
  "pixabay_music_query": "<string EN corto para búsqueda Pixabay Music, null si binaural>",
  "pixabay_fallback_queries": ["<query alt>", "<query alt2>"],
  "pexels_image_query": "<string EN 4-6 words describing image visual>",
  "base_keywords": [
    "<Título SEO ES largo, tipo Musica para Estudiar y Concentrarse 2 Horas>",
    "<Variación 2>",
    "<Variación 3>"
  ],
  "modifiers": ["<uso concreto 1>", "<uso concreto 2>", "<uso 3>", "<uso 4>"],
  "mood": "<one word mood snake_case>",
  "min_duration_minutes": <int>,
  "max_duration_minutes": <int, entre 60-480>
}}

Devuelve SOLO JSON con array "topics" que contiene los {n} objetos.
NO markdown, NO comentarios. JSON puro."""

    data = generate_json(prompt, schema=None, max_tokens=4000, temperature=0.9)
    if not data:
        print("  ambient refresher: LLM devolvió None")
        return None

    raw = (data.get("text") or "").strip()
    if raw.startswith("```"):
        import re as _re
        raw = _re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=_re.MULTILINE)
    try:
        parsed = json.loads(raw)
        topics = parsed.get("topics", []) if isinstance(parsed, dict) else parsed
    except Exception as e:
        print(f"  ambient refresher: JSON parse fail — {e}")
        return None

    if not topics or not isinstance(topics, list):
        return None

    # Guarda dedup por key
    existing = _load_dynamic().get("topics", [])
    existing_keys_all = {t["key"] for t in existing} | set(existing_keys)
    new_topics = [t for t in topics if t.get("key") not in existing_keys_all
                    and t.get("key") and t.get("base_keywords")]
    combined = existing + new_topics
    _save_dynamic({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topics": combined[-40:],  # cap 40 dinámicos
    })
    print(f"  ambient refresher: +{len(new_topics)} topics nuevos (total dinámicos: {len(combined)})")
    return new_topics


def get_all_topics_merged() -> list:
    """Devuelve pool estático + dinámicos. Auto-refresca si toca."""
    from . import topic_pool
    if _is_due():
        try:
            refresh_ambient_topics()
        except Exception as e:
            print(f"  ambient refresher fail (usando solo estático): {e}")
    static_pool = topic_pool.all_topics()
    seen = {t["key"] for t in static_pool}
    dynamic = _load_dynamic().get("topics", [])
    fresh = [t for t in dynamic if t.get("key") not in seen]
    return list(static_pool) + fresh
