"""Refinamiento de keywords visuales sin tocar el script ni la voz."""
from __future__ import annotations

import json

from google import genai
from google.genai import types

from .config import gemini_key
from .models import GeneratedScripts


REFINE_SYSTEM = """You are improving visual search keywords for an existing video script.

The user gives you a JSON script (hook, body, cta) per language and your job is to REPLACE the `visual_keywords` arrays for each segment with better ones.

**You must NOT change any other field** (no title changes, no text changes, no hashtag changes). Only `visual_keywords`.

Rules for the new keywords:
- EXACTLY 3 per segment
- 2-4 words each, English nouns/scenes
- Pexels-searchable (stock library — has people, animals, places, actions, objects; does NOT have scientific abstractions, brand names, or proper nouns)
- For abstract concepts, use visual stand-ins (e.g., "hemocyanin" → "blue liquid microscope", "empathy" → "people hugging", "AI" → "computer screen code")
- First keyword: most literal match
- Second + third: visual evocations that maintain the topic vibe

Output ONLY the same JSON structure back, with updated visual_keywords arrays. Do not add commentary or markdown fences.
"""


def refine_visual_keywords(scripts: GeneratedScripts) -> GeneratedScripts:
    api_key = gemini_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY required for refine")
    client = genai.Client(api_key=api_key)
    payload = scripts.model_dump()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=json.dumps(payload, ensure_ascii=False),
        config=types.GenerateContentConfig(
            system_instruction=REFINE_SYSTEM,
            response_mime_type="application/json",
            temperature=0.4,
            max_output_tokens=4096,
        ),
    )
    raw = (response.text or "").strip()
    data = json.loads(raw)
    return GeneratedScripts.model_validate(data)
