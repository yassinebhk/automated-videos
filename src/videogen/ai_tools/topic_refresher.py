"""Refresh dinámico del pool de AI Tools Weekly EN (anti-repetition YT 2026).

Autocontenido (no toca el topic_refresher compartido ES) porque el prompt debe
ser en INGLÉS y con fuentes/categorías tech. Mismo patrón que el refresher ES:
- Cada ~14 días regenera N topics frescos vía Gemini, usando titulares reales
  de RSS de medios AI como inspiración de tendencias.
- Guarda en output/dynamic_topics_aitools.json (short) y _aitools_long.json (long).
- get_all_topics_merged() mergea estático + dinámico (dedup por key) en runtime.

Veracidad: solo herramientas IA REALES existentes 2026, sin inventar precios ni
features. YMYL excluido (nada de salud/medicina/política/cripto/inversión).
"""
from __future__ import annotations

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

from ..config import ROOT


DYNAMIC_DIR = ROOT / "output"
REFRESH_INTERVAL_DAYS = 14
NICHE = "aitools"

# RSS de medios AI para inspiración de tendencias (titulares reales).
# Si alguno falla (404/timeout), se ignora; si todos fallan, Gemini usa su
# conocimiento general 2026.
AI_RSS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.marktechpost.com/feed/",
]

AUDIENCIAS = "creators, developers, marketers, students, business, designers, general"
CATEGORIAS = (
    "writing, image, video, coding, audio, productivity, research, marketing, "
    "design, presentations, meetings, automation, agents, data, seo, study, "
    "careers, social, email, notes, spreadsheets, youtube, free, transcription, "
    "translation"
)


def _fetch_rss_titles(url: str, limit: int = 12) -> list[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        root = ET.fromstring(data)
        titles: list[str] = []
        for it in root.iter("item"):
            t = (it.findtext("title") or "").strip()
            if t:
                titles.append(t)
            if len(titles) >= limit:
                break
        return titles
    except Exception as e:
        print(f"  aitools refresher fetch {url}: {type(e).__name__}: {e}")
        return []


def _dynamic_path(kind: str = "short") -> Path:
    suffix = "_long" if kind == "long" else ""
    return DYNAMIC_DIR / f"dynamic_topics_{NICHE}{suffix}.json"


def _load_dynamic(kind: str = "short") -> dict:
    p = _dynamic_path(kind)
    if not p.exists():
        return {"generated_at": None, "topics": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"generated_at": None, "topics": []}


def _save_dynamic(data: dict, kind: str = "short") -> None:
    p = _dynamic_path(kind)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def is_refresh_due(kind: str = "short") -> bool:
    data = _load_dynamic(kind)
    gen = data.get("generated_at")
    if not gen:
        return True
    try:
        dt = datetime.fromisoformat(gen)
        return (datetime.now(timezone.utc) - dt) > timedelta(days=REFRESH_INTERVAL_DAYS)
    except Exception:
        return True


_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "audiencia": {"type": "string"},
                    "categoria": {"type": "string"},
                    "titulo": {"type": "string"},
                    "hook": {"type": "string"},
                    "cifra_ancla": {"type": "string"},
                },
                "required": ["key", "audiencia", "categoria", "titulo", "hook", "cifra_ancla"],
            },
        }
    },
    "required": ["topics"],
}


def _trends_block() -> tuple[str, int]:
    all_titles: list[str] = []
    for url in AI_RSS:
        all_titles.extend(_fetch_rss_titles(url))
    if not all_titles:
        return "(no RSS reachable — use your general 2026 knowledge of AI tools)", 0
    return "\n".join(f"- {t[:120]}" for t in all_titles[:30]), len(all_titles)


def _gemini_topics(prompt: str, temperature: float) -> list[dict] | None:
    try:
        from google import genai
        from google.genai import types
        from ..config import gemini_key
        key = gemini_key()
        if not key:
            return None
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=5000,
                response_mime_type="application/json",
                response_schema=_SCHEMA,
            ),
        )
        text = (resp.text or "").strip()
        data = json.loads(text)
        topics = data.get("topics") or []
        return topics if len(topics) >= 3 else None
    except Exception as e:
        print(f"  aitools refresher gemini fail: {type(e).__name__}: {e}")
        return None


_VERACITY_RULES = (
    "STRICT VERACITY RULES (mandatory):\n"
    "- ONLY real AI tools that actually exist in 2026. NEVER invent tool names.\n"
    "- Do NOT invent pricing or features. If unsure, use soft anchors like "
    "'free tier available' — never a made-up number.\n"
    "- EXCLUDE any YMYL niche: no health/medical, no politics, no crypto/investing "
    "advice tools. Keep it about productivity/creative/dev/marketing tools.\n"
    "- No absolute claims ('the only tool', 'guaranteed'). Keep it factual.\n"
)


def refresh_topics_for(n: int = 15) -> list[dict] | None:
    """Genera N topics SHORT frescos (formato 'Top 5 AI tools for X')."""
    trends, n_sources = _trends_block()
    prompt = (
        f"Generate {n} FRESH short-video topics for the YouTube channel "
        f"'AI Tools Weekly' (English, faceless). Each topic is a 'Top 5 AI tools "
        f"for X' list video (~50s).\n"
        f"Valid audiencia values: {AUDIENCIAS}.\n"
        f"Valid categoria values: {CATEGORIAS}.\n\n"
        f"Trending AI headlines this fortnight (for inspiration only):\n{trends}\n\n"
        f"{_VERACITY_RULES}\n"
        f"OUTPUT FORMAT (per topic):\n"
        f"- key: unique snake_case slug (e.g. 'ai_tools_for_podcasters')\n"
        f"- audiencia: ONE of the valid values\n"
        f"- categoria: ONE of the valid values\n"
        f"- titulo: 'Top 5 AI tools for X' style, English, 45-70 chars\n"
        f"- hook: punchy English hook, first 3 seconds, max 90 chars\n"
        f"- cifra_ancla: a soft VERIFIABLE anchor (e.g. 'all have free tiers')\n\n"
        f"Prefer fresh, long-tail use cases (a specific job/audience), NOT generic "
        f"'best AI tools' already covered by huge channels. Rotate use cases widely."
    )
    topics = _gemini_topics(prompt, temperature=1.0)
    if not topics:
        return None
    _save_dynamic({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trending_sources_count": n_sources,
        "topics": topics,
    }, kind="short")
    print(f"  aitools refresher: ✅ {len(topics)} short topics frescos")
    return topics


def refresh_longform_topics_for(n: int = 8) -> list[dict] | None:
    """Genera N topics LONG-FORM (~8 min, guía/comparativa en profundidad)."""
    trends, n_sources = _trends_block()
    prompt = (
        f"Generate {n} LONG-FORM video topics (~8 min, 16:9) for the YouTube "
        f"channel 'AI Tools Weekly' (English, faceless).\n"
        f"These are IN-DEPTH pieces: 'complete guide to X', 'AI tools compared', "
        f"'how to build Y with AI' — NOT 30s shorts. 3-5 chapters of substance.\n"
        f"Valid audiencia values: {AUDIENCIAS}.\n"
        f"Valid categoria values: {CATEGORIAS}.\n\n"
        f"Trending AI headlines this fortnight (inspiration only):\n{trends}\n\n"
        f"{_VERACITY_RULES}\n"
        f"OUTPUT FORMAT (per topic):\n"
        f"- key: unique snake_case slug, prefix 'long_' (e.g. 'long_ai_video_workflow')\n"
        f"- audiencia: ONE of the valid values\n"
        f"- categoria: ONE of the valid values\n"
        f"- titulo: English, max 90 chars (e.g. 'The Complete AI Video Workflow in 2026')\n"
        f"- hook: what the viewer will learn, max 100 chars\n"
        f"- cifra_ancla: a soft verifiable anchor / key takeaway\n\n"
        f"Each topic must have enough substance for 3-5 distinct chapters."
    )
    topics = _gemini_topics(prompt, temperature=0.9)
    if not topics:
        return None
    _save_dynamic({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trending_sources_count": n_sources,
        "kind": "long",
        "topics": topics,
    }, kind="long")
    print(f"  aitools refresher long: ✅ {len(topics)} long topics frescos")
    return topics


def get_all_topics_merged(static_pool: list[dict], kind: str = "short") -> list[dict]:
    """Pool estático + dinámicos (dedup por key). Auto-refresca si toca."""
    if is_refresh_due(kind):
        if kind == "long":
            refresh_longform_topics_for()
        else:
            refresh_topics_for()
    dyn = _load_dynamic(kind).get("topics", [])
    seen = {t.get("key") for t in static_pool}
    fresh = [t for t in dyn if t.get("key") not in seen]
    return list(static_pool) + fresh
