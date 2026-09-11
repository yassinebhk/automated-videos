"""Newsjacking: pipeline que detecta noticias HOY de corrupción/fraude/juicios
españoles y las convierte en Short en <2h desde la noticia. YT y algoritmo
premian brutalmente frescura ("3 horas después del veredicto…").

Flujo:
1. Fetch RSS de medios españoles (El Mundo, El País, ABC, La Vanguardia,
   secciones política/tribunales/economía).
2. Gemini clasifica cada headline: ¿corrupción/fraude/juicio importante?
3. Extrae persona + cifra + hook.
4. Dedup contra ledger de newsjacks (para no repetir noticia + case_ledger
   principal).
5. Devuelve el mejor candidato del día como topic listo para autogen.

Reglas de calidad: solo noticias con nombres propios + cifras + relevancia
(mínimo 2 medios cubren la misma historia = señal de importancia).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .config import ROOT

NEWSJACK_LOG = ROOT / "output" / "newsjack_log.json"
COOLDOWN_DAYS = 30

# RSS feeds de medios españoles (secciones relevantes)
RSS_FEEDS = [
    ("El Mundo · España", "https://e00-elmundo.uecdn.es/elmundo/rss/espana.xml"),
    ("El Mundo · Economía", "https://e00-elmundo.uecdn.es/elmundo/rss/economia.xml"),
    ("El País · España", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana/portada"),
    ("El País · Economía", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada"),
    ("ABC · España", "https://www.abc.es/rss/feeds/abc_Espana.xml"),
    ("La Vanguardia · Política", "https://www.lavanguardia.com/rss/politica.xml"),
    ("20minutos · Nacional", "https://www.20minutos.es/rss/nacional/"),
    ("Confidencial · España", "https://rss.elconfidencial.com/espana/"),
    ("Cadena SER · Nacional", "https://cadenaser.com/rss/nacional/"),
]

# Keywords que sugieren corrupción/fraude/juicio en el headline
POSITIVE_KEYWORDS = [
    "condena", "condenado", "condenados", "prisión", "cárcel",
    "sentencia", "TS", "supremo", "audiencia nacional",
    "fraude", "estafa", "corrupción", "blanqueo",
    "mordida", "soborno", "cohecho",
    "millones", "malversación", "desvía",
    "trama", "caso ", "gürtel", "púnica", "kitchen",
    "guardia civil detiene", "operación",
    "imputad", "procesad",
]

NEGATIVE_KEYWORDS = [
    "opinión", "editorial", "columna", "reportaje",
    "fútbol", "champion", "liga", "cine", "concierto",
    "necrológica", "muere", "fallece",
    "receta", "cocina",
]


def _load_ledger() -> dict[str, str]:
    if not NEWSJACK_LOG.exists():
        return {}
    try:
        return json.loads(NEWSJACK_LOG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_used(headline_hash: str) -> None:
    NEWSJACK_LOG.parent.mkdir(parents=True, exist_ok=True)
    data = _load_ledger()
    data[headline_hash] = datetime.now(timezone.utc).isoformat()
    NEWSJACK_LOG.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")


def _recently_used(headline_hash: str) -> bool:
    entry = _load_ledger().get(headline_hash)
    if not entry:
        return False
    try:
        ts = datetime.fromisoformat(entry)
    except Exception:
        return False
    return (datetime.now(timezone.utc) - ts) < timedelta(days=COOLDOWN_DAYS)


def _hash_headline(headline: str) -> str:
    # Normaliza para dedup: minúsculas + palabras significativas
    words = re.findall(r"\w+", headline.lower())
    key_words = [w for w in words if len(w) > 4][:8]
    return "-".join(sorted(key_words))


def fetch_feed(name: str, url: str) -> list[dict]:
    """Descarga un RSS y devuelve items {title, link, pubDate, source}."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        root = ET.fromstring(data)
        items = []
        # RSS 2.0
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            pub = (it.findtext("pubDate") or "").strip()
            desc = (it.findtext("description") or "").strip()
            if title:
                items.append({"title": title, "link": link, "pubDate": pub,
                              "desc": desc[:500], "source": name})
        return items
    except Exception as e:
        print(f"  newsjack fetch {name}: {type(e).__name__}: {e}")
        return []


def _is_candidate(item: dict) -> bool:
    """Heurística rápida (pre-Gemini): título tiene keyword positivo, ninguno negativo."""
    text = (item.get("title", "") + " " + item.get("desc", "")).lower()
    if any(neg in text for neg in NEGATIVE_KEYWORDS):
        return False
    return any(pos in text for pos in POSITIVE_KEYWORDS)


def fetch_all_candidates() -> list[dict]:
    """Descarga todos los feeds, devuelve candidatos deduped por hash."""
    seen: dict[str, dict] = {}
    for name, url in RSS_FEEDS:
        for item in fetch_feed(name, url):
            if not _is_candidate(item):
                continue
            h = _hash_headline(item["title"])
            if not h or _recently_used(h):
                continue
            if h not in seen:
                item["hash"] = h
                seen[h] = item
            else:
                # Si otra fuente cubre lo mismo, marca como "multi-source" (más señal)
                seen[h].setdefault("_extra_sources", []).append(item["source"])
    return list(seen.values())


def score_with_gemini(items: list[dict], max_out: int = 3) -> list[dict]:
    """Gemini rankea los candidatos y devuelve los top con hook estructurado.

    Devuelve items con extra: {rank, hook, cifra_estim, persona, hook_para_short}.
    """
    if not items:
        return []
    try:
        from .llm_fallback import generate_json
        # Build compact input
        input_lines = []
        for i, it in enumerate(items[:30]):
            extra = ""
            if it.get("_extra_sources"):
                extra = f" [+{len(it['_extra_sources'])} medios]"
            input_lines.append(f"{i}. [{it['source']}]{extra} {it['title']}")
        prompt = (
            "Eres editor de un canal true crime español (WaitWhy). Estos son "
            "titulares de HOY. Elige los mejores para hacer un Short YT de <60s "
            "sobre corrupción/fraude/juicio español relevante.\n\n"
            "REGLAS:\n"
            "- Solo casos con CIFRA (millones €) o PERSONA CONOCIDA (político, "
            "empresario) o SENTENCIA/JUICIO relevante.\n"
            "- NO opiniones, NO análisis, NO fútbol/cultura/sucesos menores.\n"
            "- Prefiere titulares con multi-medios (señal de importancia).\n\n"
            "Titulares:\n" + "\n".join(input_lines) + "\n\n"
            f"Devuelve JSON con {{ \"picks\": [{{\"index\": N, \"persona\": ..., "
            f"\"cifra\": \"...\" o null, \"hook_short\": frase gancho para el vídeo "
            f"(máx 90 chars), \"topic\": tema completo listo para autogen (formato "
            f"'[NEWSJACK] persona/tema — hook con cifra' máx 120 chars) }}, ...] }}. "
            f"Máximo {max_out} picks, ordenados por relevancia."
        )
        schema = {
            "type": "object",
            "properties": {
                "picks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "persona": {"type": "string"},
                            "cifra": {"type": "string"},
                            "hook_short": {"type": "string"},
                            "topic": {"type": "string"},
                        },
                        "required": ["index", "topic"],
                    },
                }
            },
            "required": ["picks"],
        }
        # Fallback Gemini→Groq
        data = generate_json(prompt, schema=schema, max_tokens=5000, temperature=0.7)
        if not data:
            print(f"  newsjack: ambos LLMs fallaron — retorno top {max_out} sin scoring")
            return items[:max_out]
        picks = data.get("picks", [])
        out = []
        for p in picks[:max_out]:
            idx = p.get("index")
            if not isinstance(idx, int) or idx >= len(items):
                continue
            base = items[idx].copy()
            base["persona"] = p.get("persona", "")
            base["cifra"] = p.get("cifra", "")
            base["hook_short"] = p.get("hook_short", "")
            base["topic"] = p.get("topic") or f"[NEWSJACK] {base['title']}"
            out.append(base)
        return out
    except Exception as e:
        print(f"  newsjack score: {type(e).__name__}: {e}")
        return items[:max_out]


def pick_best_today() -> dict | None:
    """Devuelve el mejor candidato del día para newsjacking, o None."""
    items = fetch_all_candidates()
    print(f"  newsjack: {len(items)} candidatos pre-Gemini")
    scored = score_with_gemini(items, max_out=3)
    print(f"  newsjack: {len(scored)} tras Gemini scoring")
    if not scored:
        return None
    best = scored[0]
    _mark_used(best["hash"])
    print(f"  newsjack: elegido «{best.get('topic','')[:100]}»")
    return best


def run_once() -> dict[str, Any]:
    """CLI entry: elige noticia + dispara autogen con topic newsjacked."""
    from . import telegram_bot
    import asyncio

    best = pick_best_today()
    if not best:
        return {"status": "no_candidate"}

    topic = best.get("topic") or f"[NEWSJACK] {best['title']}"
    # Notif previa
    _notify(f"🚨 <b>Newsjack detectado</b>\n<i>{best.get('title','')[:120]}</i>\n"
            f"→ Generando short sobre: {topic[:120]}")

    # Dispara autogen con este topic forzado
    # Reusa la lógica existente de _run_autogen_with_topic si existe,
    # o llama a service.generate directamente.
    try:
        from . import service
        slug = service.generate(topic, ("es",), lambda m: print(f"  {m}"), ai_hero=True)
        return {"status": "ok", "slug": slug, "topic": topic,
                "source_headline": best.get("title", "")}
    except Exception as e:
        _notify(f"❌ Newsjack falló en generación: {type(e).__name__}: {e}")
        return {"status": "gen_fail", "topic": topic, "error": str(e)}


def _notify(text: str) -> None:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data=json.dumps({"chat_id": int(chat), "text": text,
                              "parse_mode": "HTML"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass
