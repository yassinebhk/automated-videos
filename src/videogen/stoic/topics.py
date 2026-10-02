"""Pool de temas de Stoic Mind (EN) — estoicismo aplicado a estrés moderno.

Cada topic = 1 estresor moderno + 1 principio estoico que lo reencuadra. El guion
final lo escribe el modelo (service.generate) con prompts/stoic_en_system.md; aquí
solo el ángulo (ni citas ni biografía — veracidad: el system prompt PROHÍBE inventar
citas/atribuciones). Pool SEED + refresher dinámico (Gemini) que ACUMULA.

Ver [[dedup-semantico-titulo]] (anti-repetición) y [[veracidad-obligatoria]].
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

from ..config import ROOT

DYNAMIC_PATH = ROOT / "output" / "dynamic_topics_stoic.json"
REFRESH_INTERVAL_DAYS = 7
MAX_DYNAMIC = 200


# estresor moderno → principio estoico que lo disuelve. 18 semilla.
SEED: list[dict] = [
    {"key": "boss_takes_credit", "stoic": "Epictetus", "principle": "dichotomy of control",
     "stressor": "a boss who takes credit for your work",
     "hook": "Your boss just took credit for your work in front of everyone.",
     "titulo": "The Stoic way to handle a boss who steals your credit",
     "visual": "ancient Roman bust, empty office at night, stormy sky"},
    {"key": "feeling_behind_social", "stoic": "Seneca", "principle": "life is long enough if used well",
     "stressor": "feeling behind when everyone online seems ahead",
     "hook": "You open your phone and feel behind. Everyone's winning but you.",
     "titulo": "When everyone seems ahead of you — a Stoic reset",
     "visual": "lone figure on a mountain, calm sea at dusk, marble statue"},
    {"key": "anxiety_before_big_day", "stoic": "Marcus Aurelius", "principle": "premeditatio malorum",
     "stressor": "anxiety the night before something important",
     "hook": "It's the night before the big day and your mind won't stop.",
     "titulo": "How Stoics kill anxiety before a big day",
     "visual": "candle flame in darkness, rain on window, quiet temple columns"},
    {"key": "toxic_people", "stoic": "Marcus Aurelius", "principle": "expect difficult people, guard your judgment",
     "stressor": "dealing with rude, difficult people",
     "hook": "Someone was rude to you and it's still in your head hours later.",
     "titulo": "Marcus Aurelius' trick for toxic people",
     "visual": "marble statue close up, grey stormy sky, columns in fog"},
    {"key": "doomscrolling", "stoic": "Epictetus", "principle": "control your attention, not the feed",
     "stressor": "doomscrolling and feeling worse after",
     "hook": "You picked up your phone for one minute. Forty minutes gone, mood worse.",
     "titulo": "The Stoic cure for doomscrolling",
     "visual": "phone glow in dark room, candle, stormy night sky"},
    {"key": "fear_of_failure", "stoic": "Seneca", "principle": "we suffer more in imagination",
     "stressor": "fear of failing before you even start",
     "hook": "You haven't started because you're terrified it won't work.",
     "titulo": "What Stoics do with the fear of failure",
     "visual": "lone mountain peak, figure walking in fog, marble statue"},
    {"key": "criticism_haters", "stoic": "Epictetus", "principle": "it's your opinion of the insult that wounds",
     "stressor": "a harsh comment or criticism that stung",
     "hook": "One cruel comment and it ruined your whole day.",
     "titulo": "How a Stoic handles criticism and haters",
     "visual": "stone bust, cracked marble, dark moody sky"},
    {"key": "comparison_trap", "stoic": "Seneca", "principle": "run your own race",
     "stressor": "comparing your life to others",
     "hook": "Their highlight reel just made your real life feel small.",
     "titulo": "The Stoic answer to the comparison trap",
     "visual": "calm sea at dusk, single star, ancient statue silhouette"},
    {"key": "procrastination", "stoic": "Marcus Aurelius", "principle": "do the task in front of you now",
     "stressor": "procrastinating on what matters",
     "hook": "You know exactly what to do. You're still not doing it.",
     "titulo": "Marcus Aurelius on beating procrastination",
     "visual": "sunrise over mountains, marble statue, empty desk by window"},
    {"key": "money_worry", "stoic": "Seneca", "principle": "fortune, not you, owns what you fear to lose",
     "stressor": "lying awake worried about money",
     "hook": "It's 3am and you're doing math you can't win.",
     "titulo": "A Stoic way to sit with money worry",
     "visual": "rain on window at night, candle, quiet empty room"},
    {"key": "anger_traffic", "stoic": "Marcus Aurelius", "principle": "the obstacle teaches patience",
     "stressor": "losing your temper in traffic or small daily friction",
     "hook": "The light's red again and you can feel your jaw tighten.",
     "titulo": "The Stoic reset for everyday anger",
     "visual": "stormy sky clearing, marble statue, long empty road at dusk"},
    {"key": "rejection", "stoic": "Epictetus", "principle": "some things are not up to us",
     "stressor": "being rejected — a job, a person, an opportunity",
     "hook": "The 'no' came and it hit harder than you expected.",
     "titulo": "How Stoics survive rejection",
     "visual": "lone figure in fog, closing door, grey marble bust"},
    {"key": "overthinking_night", "stoic": "Marcus Aurelius", "principle": "the view from above",
     "stressor": "overthinking replaying the day at night",
     "hook": "Your body is in bed. Your mind is still in the argument.",
     "titulo": "The Stoic trick to stop overthinking at night",
     "visual": "night sky full of stars, earth from above, candle in dark"},
    {"key": "impostor_syndrome", "stoic": "Epictetus", "principle": "judge yourself by effort, not applause",
     "stressor": "feeling like a fraud who'll be found out",
     "hook": "You got the role and now you're sure they'll find you out.",
     "titulo": "The Stoic answer to impostor syndrome",
     "visual": "marble statue half in shadow, quiet temple, misty columns"},
    {"key": "people_pleasing", "stoic": "Epictetus", "principle": "you can't control being liked",
     "stressor": "exhausting yourself trying to please everyone",
     "hook": "You said yes again. You meant no again.",
     "titulo": "How Stoics stop people-pleasing",
     "visual": "single figure walking away, stone bust, calm sea"},
    {"key": "bad_news_cycle", "stoic": "Epictetus", "principle": "separate what you can act on from the rest",
     "stressor": "feeling heavy from constant bad news",
     "hook": "The headlines are grim and you feel powerless.",
     "titulo": "A Stoic way through the endless bad news",
     "visual": "storm over city skyline, candle, marble statue"},
    {"key": "perfectionism", "stoic": "Seneca", "principle": "done and useful beats perfect and unfinished",
     "stressor": "perfectionism that stops you finishing",
     "hook": "It's good enough to ship. You're still polishing it.",
     "titulo": "What Stoicism says about perfectionism",
     "visual": "unfinished marble sculpture, workshop light, calm sky"},
    {"key": "loss_change", "stoic": "Marcus Aurelius", "principle": "amor fati — love what happens",
     "stressor": "struggling to accept a change you didn't choose",
     "hook": "Something ended that you didn't want to end.",
     "titulo": "The Stoic practice of amor fati",
     "visual": "autumn leaves falling, marble statue, sea at dusk"},
]


def _static_pool() -> list[dict]:
    return list(SEED)


# ─────────────────────────────── dinámicos (LLM) ───────────────────────────────
def _load_dynamic() -> dict:
    if not DYNAMIC_PATH.exists():
        return {"generated_at": None, "topics": []}
    try:
        return json.loads(DYNAMIC_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"generated_at": None, "topics": []}


def _save_dynamic(data: dict) -> None:
    DYNAMIC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DYNAMIC_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _refresh_due() -> bool:
    gen = _load_dynamic().get("generated_at")
    if not gen:
        return True
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(gen)) > timedelta(days=REFRESH_INTERVAL_DAYS)
    except Exception:
        return True


def refresh_dynamic(n: int = 12) -> list[dict] | None:
    """Pide a Gemini N ángulos NUEVOS (estresor moderno + principio estoico) y ACUMULA.

    Solo el ÁNGULO (no el guion, no citas). Veracidad: el principio se enseña con
    palabras propias en el guion; aquí no se piden citas verbatim ni biografía.
    """
    existing = _static_pool() + _load_dynamic().get("topics", [])
    existing_keys = {t.get("key") for t in existing}
    existing_titles = [" ".join((t.get("titulo") or "").split()) for t in existing if t.get("titulo")]
    avoid = "\n".join(f"- {t[:70]}" for t in existing_titles[:80])
    try:
        from google import genai
        from google.genai import types
        from ..config import gemini_key
        key = gemini_key()
        if not key:
            return None
        client = genai.Client(api_key=key)
        schema = {
            "type": "object",
            "properties": {"topics": {"type": "array", "items": {"type": "object", "properties": {
                "key": {"type": "string"}, "stoic": {"type": "string"},
                "principle": {"type": "string"}, "stressor": {"type": "string"},
                "hook": {"type": "string"}, "titulo": {"type": "string"},
                "visual": {"type": "string"},
            }, "required": ["key", "stoic", "principle", "stressor", "hook", "titulo", "visual"]}}},
            "required": ["topics"],
        }
        prompt = (
            f"Generate {n} NEW ideas for a faceless English YouTube Shorts channel that applies "
            f"STOIC PHILOSOPHY to MODERN STRESS (work, burnout, anxiety, social media, money, "
            f"relationships, self-doubt).\n\n"
            f"Each idea = ONE concrete modern stressor + ONE Stoic principle that reframes it.\n"
            f"STRICT RULES:\n"
            f"- Do NOT invent verbatim quotes or put words in a philosopher's mouth. 'stoic' is just "
            f"which Stoic the idea draws on (Marcus Aurelius, Seneca, Epictetus, Zeno, Musonius Rufus).\n"
            f"- 'principle' = the Stoic idea in plain words (e.g. 'dichotomy of control', 'amor fati').\n"
            f"- No YMYL (no medical/therapy/financial advice framed as fact), no politics/religion bait.\n"
            f"- Fresh, specific, 2026-relatable stressors. Do NOT repeat these existing angles:\n{avoid}\n\n"
            f"For each: key (snake_case, unique), stoic, principle, stressor (short phrase), "
            f"hook (a vivid 1-sentence scene naming the stressor), titulo (English SEO title: "
            f"problem + Stoic answer), visual (3-4 dark cinematic scene keywords: statues, storms, "
            f"candles, mountains, rain)."
        )
        resp = client.models.generate_content(
            model="gemini-3.5-flash-lite", contents=prompt,
            config=types.GenerateContentConfig(temperature=1.0, max_output_tokens=6000,
                                               response_mime_type="application/json", response_schema=schema),
        )
        got = json.loads((resp.text or "").strip()).get("topics", [])
        try:
            from .. import dedup_common
            _isrep = lambda t: dedup_common.title_is_repeat(  # noqa: E731
                " ".join((t.get("titulo") or "").split()), existing_titles)
        except Exception:
            _isrep = lambda t: False  # noqa: E731
        fresh: list[dict] = []
        seen = set(existing_keys)
        for t in got:
            k = (t.get("key") or "").strip()
            if not k or k in seen or not t.get("titulo") or not t.get("stressor"):
                continue
            if _isrep(t):
                continue
            seen.add(k)
            fresh.append(t)
        if not fresh:
            print("  stoic topics: 0 ángulos nuevos válidos")
            return None
        acc = (_load_dynamic().get("topics", []) + fresh)[-MAX_DYNAMIC:]
        _save_dynamic({"generated_at": datetime.now(timezone.utc).isoformat(), "topics": acc})
        print(f"  stoic topics: ✅ +{len(fresh)} ángulos (pool dinámico={len(acc)})")
        return fresh
    except Exception as e:
        print(f"  stoic topics refresh fail: {type(e).__name__}: {e}")
        return None


def all_topics() -> list[dict]:
    """Pool completo (seed + dinámicos acumulados, dedup por key). Auto-refresca 7d."""
    if _refresh_due():
        refresh_dynamic()
    static = _static_pool()
    seen = {t["key"] for t in static}
    dyn = [t for t in _load_dynamic().get("topics", []) if t.get("key") and t["key"] not in seen]
    return static + dyn
