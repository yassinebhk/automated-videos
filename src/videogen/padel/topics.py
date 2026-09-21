"""Pool de temas del canal Pádel — MÚLTIPLES formatos + generación dinámica.

Formatos:
- tactic    : jugada táctica (animación de pista a medida; escena en manim_scene.TACTICS)
- fact      : curiosidad / "¿sabías que?"          (plantilla PadelFact)
- compare   : comparativa de material              (plantilla PadelCompare)
- checklist : recomendaciones / errores            (plantilla PadelChecklist)

fact/compare/checklist llevan su contenido + narración en el propio topic →
generables por LLM sin hand-code. El pool SEED está fundamentado en fuentes reales;
el refresher LLM añade más cada 14 días (dedup + cooldown por ledger).

Veracidad (heredada [[veracidad-obligatoria]]): solo conocimiento general de pádel
bien establecido. PROHIBIDO inventar marcas, precios, specs o estadísticas concretas.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from ..config import ROOT
from . import manim_scene

DYNAMIC_PATH = ROOT / "output" / "dynamic_topics_padel.json"
REFRESH_INTERVAL_DAYS = 7  # semanal (antes 14 → se repetían ideas a las 2 sem)
CTA = "Follow for more padel."

# Fuentes de pádel para inspiración de temas frescos (foros/prensa del nicho).
# Si no resuelven, refresh_dynamic cae al conocimiento general de Gemini.
PADEL_RSS = [
    "https://www.padelfip.com/feed/",
    "https://www.relevo.com/rss/padel/",
    "https://www.padelspain.net/feed/",
]


def _padel_rss_titles(limit: int = 24) -> list[str]:
    import re as _re
    import urllib.request as _u
    out: list[str] = []
    for url in PADEL_RSS:
        try:
            req = _u.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = _u.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
            out.extend(t.strip() for t in _re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", data)[1:9])
        except Exception:
            continue
    return [t for t in out if t][:limit]


# ─────────────────────── SEED: tácticas (animación a medida) ───────────────────────
def _tactic_seeds() -> list[dict]:
    return [{"key": f"tactic_{k}", "format": "tactic", "tactic": k,
             "title": v["title"], "es": v["es"]}
            for k, v in manim_scene.TACTICS.items()]


# ─────────────────────── SEED: curiosidades / comparativas / checklists ───────────────────────
SEED_CONTENT: list[dict] = [
    # ── FACTS (curiosidades reales) ──
    {"key": "fact_origin_1969", "format": "fact", "kicker": "DID YOU KNOW?",
     "title": "Padel was born\nin a backyard", "punch": "Now played in 90+ countries",
     "lines": ["Invented in 1969 in Acapulco, Mexico",
               "By Enrique Corcuera — no room for a tennis court",
               "So he walled in a smaller one"],
     "narration": ("Here's something most players don't know. Padel was invented back in 1969, "
                   "in Acapulco, Mexico. A man named Enrique Corcuera didn't have room for a full "
                   "tennis court, so he built a smaller one and walled it in. That backyard experiment "
                   "is now played in over ninety countries. Follow for more padel.")},
    {"key": "fact_name_paddle", "format": "fact", "kicker": "DID YOU KNOW?",
     "title": "Why it's called\n'padel'", "punch": "And why you serve underarm",
     "lines": ["The name comes from the English word 'paddle'",
               "The court is 20 by 10 metres, walls included",
               "You must serve underarm, at waist height or below"],
     "narration": ("Ever wondered why it's called padel? The name comes from the English word paddle. "
                   "The court is twenty by ten metres, and the walls are part of the game. And unlike "
                   "tennis, you must serve underarm, at waist height or below. Follow for more padel.")},
    {"key": "fact_doubles_only", "format": "fact", "kicker": "DID YOU KNOW?",
     "title": "Padel is (almost)\nalways doubles", "punch": "The walls make it unique",
     "lines": ["The small court makes one-on-one very rare",
               "Pro padel has been doubles-only since the 1970s",
               "Balls off the glass stay in play — like squash"],
     "narration": ("Why is padel almost always played in pairs? The court is so compact that one on one "
                   "barely works, so the pro game has been doubles only since the seventies. And the walls? "
                   "They're in play. A ball off the glass keeps the point alive, just like squash. Follow for more padel.")},
    {"key": "fact_argentina_spain", "format": "fact", "kicker": "DID YOU KNOW?",
     "title": "The fastest-growing\nsport on earth", "punch": "25 million players and counting",
     "lines": ["From Mexico it spread through Spain and Argentina",
               "Over 25 million players in 90+ countries",
               "Argentina and Spain dominate the world titles"],
     "narration": ("Padel is often called the fastest growing sport on the planet. From Mexico it exploded "
                   "across Spain and Argentina, and today more than twenty five million people play it in over "
                   "ninety countries. At the top, Argentina and Spain trade the world titles between them. Follow for more padel.")},
    {"key": "fact_viviana_rules", "format": "fact", "kicker": "DID YOU KNOW?",
     "title": "A birthday gift\nwrote the rules", "punch": "Padel's first rulebook",
     "lines": ["Corcuera built the first court in 1969",
               "His wife Viviana wrote the first set of rules",
               "She presented them to him as a birthday gift"],
     "narration": ("Padel's very first rulebook was a birthday present. After Enrique Corcuera built that first "
                   "walled court, it was his wife Viviana who wrote down the first set of rules, and gave them to "
                   "him as a gift. A sport, born from a couple's backyard. Follow for more padel.")},

    # ── COMPARE (material) ──
    {"key": "compare_racket_shapes", "format": "compare", "kicker": "WHICH RACKET?",
     "title": "Round vs Teardrop\nvs Diamond", "punch": "Round = control\nDiamond = power",
     "items": [{"name": "ROUND", "shape": "round"}, {"name": "TEARDROP", "shape": "teardrop"},
               {"name": "DIAMOND", "shape": "diamond"}],
     "attrs": [{"label": "Control", "values": [95, 70, 45]},
               {"label": "Power", "values": [45, 70, 95]},
               {"label": "Forgiveness", "values": [95, 65, 40]}],
     "narration": ("Round, teardrop, or diamond — which padel racket is right for you? It all comes down to where "
                   "the weight sits. A round racket keeps the sweet spot low and central: maximum control, very "
                   "forgiving, perfect while you're learning. A diamond pushes the weight up high: big power, but "
                   "much less forgiving — a racket for advanced players. The teardrop sits in between, balanced for "
                   "improving players. Follow for more padel.")},
    {"key": "compare_balls", "format": "compare", "kicker": "WHICH BALL?",
     "title": "Pressurised vs\nPressureless balls", "punch": "New players: start slower",
     "items": [{"name": "PRESSURISED", "shape": "round"}, {"name": "PRESSURELESS", "shape": "round"}],
     "attrs": [{"label": "Bounce & speed", "values": [90, 55]},
               {"label": "Durability", "values": [45, 90]},
               {"label": "Pro feel", "values": [95, 55]}],
     "narration": ("Not all padel balls are the same. Pressurised balls are what the pros use: fast, lively, big "
                   "bounce — but they go dead quickly. Pressureless balls bounce a little lower and feel less "
                   "explosive, but they last far longer, which makes them great for training. If you're still "
                   "building consistency, a slower ball is easier to control. Follow for more padel.")},

    # ── CHECKLIST (recomendaciones / errores) ──
    {"key": "checklist_beginner_mistakes", "format": "checklist", "kicker": "BEGINNER FIXES",
     "title": "3 mistakes killing\nyour game", "punch": "Fix these and you'll\njump a level fast",
     "tips": ["Stop smashing everything — control beats power",
              "Escape no man's land — net or back, never the middle",
              "Use the walls — let the ball rebound, don't fear it"],
     "narration": ("Three mistakes quietly killing your padel game. Number one: you smash everything. In padel, "
                   "control beats power almost every time. Number two: you're stuck in no man's land. Be at the net, "
                   "or at the back, never frozen in the middle. Number three: you're scared of the walls. Let the "
                   "ball rebound and play it off the glass. Fix these three and you'll jump a level fast. Follow for more padel.")},
    {"key": "checklist_choose_racket", "format": "checklist", "kicker": "BUYING YOUR FIRST?",
     "title": "How to pick your\nfirst racket", "punch": "Comfort first,\npower later",
     "tips": ["Go round-shaped for control and a big sweet spot",
              "Pick a lighter racket that's easy to handle",
              "Don't overpay — you'll upgrade as you improve"],
     "narration": ("Buying your first padel racket? Keep it simple. First, go for a round shape — it gives you the "
                   "biggest sweet spot and the most control. Second, pick something on the lighter side, so it's easy "
                   "to swing and kind to your arm. And third, don't overspend: your game will change fast, and you'll "
                   "want to upgrade anyway. Comfort first, power later. Follow for more padel.")},
    {"key": "checklist_communication", "format": "checklist", "kicker": "TEAM PLAY",
     "title": "Play as a team,\nnot two players", "punch": "Talk every single point",
     "tips": ["Call every ball — 'mine' or 'yours', out loud",
              "Cover the middle together, never leave a gap",
              "Lob and attack as a pair — move like one unit"],
     "narration": ("Padel is a team sport, so stop playing like two strangers. First, call every ball — a loud "
                   "mine or yours stops collisions and balls dying in the middle. Second, cover the centre together "
                   "and never leave a gap between you. And third, move as one unit — when one goes up, the other goes "
                   "up. Talk every single point. Follow for more padel.")},
]


def _static_pool() -> list[dict]:
    return _tactic_seeds() + SEED_CONTENT


# ─────────────────────── dinámicos (LLM) ───────────────────────
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
    """Genera N topics frescos (fact/checklist) vía Gemini. Guarda en disco.
    Solo fact/checklist (bajo riesgo veracidad: curiosidades verificables + consejos)."""
    existing = _static_pool() + _load_dynamic().get("topics", [])
    existing_keys = [t.get("key") for t in existing]
    existing_titles = [" ".join((t.get("title") or "").split()) for t in existing if t.get("title")]
    rss = _padel_rss_titles()
    rss_block = ("\nFresh padel headlines for inspiration (do NOT copy, just spark new angles):\n"
                 + "\n".join(f"- {t[:110]}" for t in rss[:20])) if rss else ""
    avoid_block = ("\n\n⛔ ALREADY PUBLISHED — do NOT repeat or resemble these titles "
                   "(pick clearly different angles):\n"
                   + "\n".join(f"- {t[:80]}" for t in existing_titles[:60])) if existing_titles else ""
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
                "key": {"type": "string"}, "format": {"type": "string"},
                "kicker": {"type": "string"}, "title": {"type": "string"},
                "items": {"type": "array", "items": {"type": "string"}},
                "punch": {"type": "string"}, "narration": {"type": "string"},
            }, "required": ["key", "format", "kicker", "title", "items", "punch", "narration"]}}},
            "required": ["topics"],
        }
        prompt = (
            f"Generate {n} FRESH short-video ideas for an English padel (padel tennis) channel. "
            f"Two formats only:\n"
            f"- 'fact': a padel curiosity / did-you-know (history, rules, culture, the sport itself)\n"
            f"- 'checklist': 3 coaching tips or common-mistake fixes on ONE theme\n\n"
            f"STRICT TRUTH RULES: only widely-accepted, general padel knowledge. "
            f"NEVER invent brand names, prices, specs, dates you're unsure of, or statistics. "
            f"Coaching tips are fine as general advice. If unsure about a fact, don't include it.\n\n"
            f"Do NOT repeat these existing ideas (by theme): {', '.join(k for k in existing_keys if k)[:900]}."
            f"{avoid_block}{rss_block}\n\n"
            f"For each idea output:\n"
            f"- key: unique snake_case slug prefixed with the format, e.g. 'fact_xxx' or 'checklist_xxx'\n"
            f"- format: 'fact' or 'checklist'\n"
            f"- kicker: 2-3 word ALL-CAPS label (e.g. 'DID YOU KNOW?', 'NET PLAY')\n"
            f"- title: punchy 2-line title, use \\n between the lines, max ~28 chars/line\n"
            f"- items: EXACTLY 3 short strings (facts for 'fact', tips for 'checklist'), max ~55 chars each\n"
            f"- punch: 1-2 line closing line, use \\n, max ~24 chars/line\n"
            f"- narration: a 28-32s spoken voiceover (~75 words) that flows naturally, ending with 'Follow for more padel.'\n"
        )
        resp = client.models.generate_content(
            model="gemini-3.5-flash-lite", contents=prompt,
            config=types.GenerateContentConfig(temperature=1.0, max_output_tokens=6000,
                                               response_mime_type="application/json", response_schema=schema),
        )
        data = json.loads((resp.text or "").strip())
        topics = [t for t in data.get("topics", []) if t.get("format") in ("fact", "checklist")]
        # Filtro anti-repeat por título contra lo ya existente (por si la key es
        # nueva pero el tema es casi igual).
        try:
            from .. import dedup_common
            b = len(topics)
            topics = [t for t in topics
                      if not dedup_common.title_is_repeat(" ".join((t.get("title") or "").split()), existing_titles)]
            if b - len(topics):
                print(f"  padel topics: filtró {b-len(topics)} repetidos por título")
        except Exception:
            pass
        # normaliza items → lines/tips
        for t in topics:
            its = t.pop("items", [])
            if t["format"] == "fact":
                t["lines"] = its[:3]
            else:
                t["tips"] = its[:3]
        if len(topics) < 3:
            print(f"  padel topics: solo {len(topics)} generados — insuficiente")
            return None
        _save_dynamic({"generated_at": datetime.now(timezone.utc).isoformat(), "topics": topics})
        print(f"  padel topics: ✅ {len(topics)} frescos guardados")
        return topics
    except Exception as e:
        print(f"  padel topics refresh fail: {type(e).__name__}: {e}")
        return None


def all_topics() -> list[dict]:
    """Pool completo (seed + dinámicos, dedup por key). Auto-refresca cada 14d."""
    if _refresh_due():
        refresh_dynamic()
    static = _static_pool()
    seen = {t["key"] for t in static}
    dyn = [t for t in _load_dynamic().get("topics", []) if t.get("key") and t["key"] not in seen]
    return static + dyn
