"""Refresher de topic pools según tendencias del momento.

Cada canal tiene topic_pool.py estático. Este módulo genera topics
FRESCOS quincenalmente usando:
1. Gemini sabiendo qué está de moda en el nicho
2. RSS de medios ES específicos por nicho (fiscal, legal, motor, ayudas)
3. Google Trends fallback via web search si Gemini falla

Guarda topics dinámicos en output/dynamic_topics_{canal}.json que se
mergean con el pool estático en runtime.

Reglas de veracidad heredadas: topics deben ser sobre temas REALES vigentes,
con potencial de cifra verificable + hook concreto.
"""
from __future__ import annotations

import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .config import ROOT


DYNAMIC_DIR = ROOT / "output"
REFRESH_INTERVAL_DAYS = 14  # regenerar cada 2 semanas


# Feeds RSS específicos por nicho (para inspiración de topics reales)
NICHE_RSS = {
    "tax": [
        "https://sede.agenciatributaria.gob.es/Sede/rss/novedades-rss.html",
        "https://cincodias.elpais.com/rss/economia/pymes.xml",
    ],
    "legal": [
        "https://www.20minutos.es/rss/laboral/",
        "https://cincodias.elpais.com/rss/legal/laboral.xml",
    ],
    "ayudas": [
        "https://www.boe.es/rss/ultimas-disposiciones.php",
    ],
    "motor": [
        "https://www.motor.es/rss/noticias/",
        "https://www.autopista.es/rss/",
    ],
}


def _fetch_rss_titles(url: str, limit: int = 15) -> list[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        root = ET.fromstring(data)
        titles = []
        for it in root.iter("item"):
            t = (it.findtext("title") or "").strip()
            if t:
                titles.append(t)
            if len(titles) >= limit:
                break
        return titles
    except Exception as e:
        print(f"  refresher fetch {url}: {type(e).__name__}: {e}")
        return []


def _dynamic_path(niche: str) -> Path:
    return DYNAMIC_DIR / f"dynamic_topics_{niche}.json"


def _load_dynamic(niche: str) -> dict:
    p = _dynamic_path(niche)
    if not p.exists():
        return {"generated_at": None, "topics": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"generated_at": None, "topics": []}


def _save_dynamic(niche: str, data: dict) -> None:
    p = _dynamic_path(niche)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def is_refresh_due(niche: str) -> bool:
    """True si toca regenerar topics (>REFRESH_INTERVAL_DAYS desde última)."""
    data = _load_dynamic(niche)
    gen = data.get("generated_at")
    if not gen:
        return True
    try:
        dt = datetime.fromisoformat(gen)
        return (datetime.now(timezone.utc) - dt) > timedelta(days=REFRESH_INTERVAL_DAYS)
    except Exception:
        return True


def _niche_context(niche: str) -> dict:
    """Metadata del nicho para prompt Gemini."""
    return {
        "tax": {
            "canal": "TaxHack ES",
            "audiencias": "autónomos, particulares, empresas",
            "categorias": "deducciones, obligaciones, trucos legales, novedades fiscales",
            "fuentes_oficiales": "BOE, Agencia Tributaria, Seguridad Social",
            "cifra_typical": "hasta €X ahorro/año",
        },
        "legal": {
            "canal": "TusDerechos ES",
            "audiencias": "trabajadores, autónomos, empresas",
            "categorias": "despidos, permisos, salarios, contratos, jornada, IT baja, jubilación",
            "fuentes_oficiales": "Estatuto Trabajadores, BOE, TS jurisprudencia, convenios",
            "cifra_typical": "€X indemnización · X días · X% base",
        },
        "ayudas": {
            "canal": "AyudaGob",
            "audiencias": "autónomos, familias, jóvenes, empresas, estudiantes",
            "categorias": "vivienda, familia, empleo, educación, movilidad, discapacidad",
            "fuentes_oficiales": "BOE, sede.seg-social, sepe.es, MEC, webs CCAA",
            "cifra_typical": "€X/mes · X meses · N% subvención",
        },
        "motor": {
            "canal": "Motor60s",
            "audiencias": "compradores, propietarios, vendedores",
            "categorias": "TOP modelos, fallos comunes, guía compra, mantenimiento, ITV, precios",
            "fuentes_oficiales": "coches.net, Ganvam, DGT, ITV, foros técnicos",
            "cifra_typical": "€X precio · €X reparación · N km",
        },
    }.get(niche, {})


def refresh_topics_for(niche: str, n: int = 15) -> list[dict] | None:
    """Genera N topics frescos vía Gemini usando RSS del nicho como
    inspiración de temas trending. Guarda en dynamic_topics_{niche}.json."""
    ctx = _niche_context(niche)
    if not ctx:
        print(f"  refresher: nicho '{niche}' desconocido")
        return None

    # Inspiración: titulares reales de RSS del nicho
    rss_urls = NICHE_RSS.get(niche, [])
    all_titles: list[str] = []
    for url in rss_urls:
        all_titles.extend(_fetch_rss_titles(url, limit=12))
    trends_block = "\n".join(f"- {t[:120]}" for t in all_titles[:30]) if all_titles else "(no hay RSS accesibles, usa tu conocimiento general 2026)"

    try:
        from google import genai
        from google.genai import types
        from .config import gemini_key
        key = gemini_key()
        if not key:
            return None
        client = genai.Client(api_key=key)

        schema = {
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
                        "required": ["key", "audiencia", "categoria",
                                      "titulo", "hook", "cifra_ancla"],
                    },
                }
            },
            "required": ["topics"],
        }

        prompt = (
            f"Genera {n} topics FRESCOS para Shorts YT del canal '{ctx['canal']}' "
            f"nicho: {niche}. Audiencias válidas: {ctx['audiencias']}. "
            f"Categorías válidas: {ctx['categorias']}.\n\n"
            f"Contexto trending de esta quincena (titulares recientes):\n{trends_block}\n\n"
            f"REGLAS ESTRICTAS DE VERACIDAD (obligatorio):\n"
            f"- Solo temas basados en NORMATIVA REAL vigente 2026\n"
            f"- Cifras del BOE / {ctx['fuentes_oficiales']} — NO INVENTAR\n"
            f"- Si dudas de una cifra concreta, usa el marcador 'según último BOE' "
            f"en cifra_ancla, NUNCA inventes número aproximado\n"
            f"- PROHIBIDO: generalizaciones absolutas, especulación, opiniones\n"
            f"- Cada topic debe tener potencial de vídeo TOP N con cifras concretas\n\n"
            f"FORMATO OUTPUT (para cada topic):\n"
            f"- key: slug único snake_case (ej. 'jub_edad_2026_novedad')\n"
            f"- audiencia: UNA de {ctx['audiencias']}\n"
            f"- categoria: UNA de {ctx['categorias']}\n"
            f"- titulo: 'TOP N X · cifra' o 'N cosas Y · cifra' (60-75 chars)\n"
            f"- hook: pregunta o dato brutal (80 chars)\n"
            f"- cifra_ancla: '{ctx['cifra_typical']}'\n\n"
            f"NO repitas topics obvios ya cubiertos por canales grandes ES.\n"
            f"Prioriza NOVEDADES 2026 y temas long-tail infravalorados."
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=1.0,
                max_output_tokens=5000,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        text = (resp.text or "").strip()
        try:
            data = json.loads(text)
        except Exception as je:
            print(f"  refresher: JSON parse fail — {je}")
            return None
        topics = data.get("topics") or []
        if len(topics) < 3:
            print(f"  refresher: solo {len(topics)} topics generados — insuficiente")
            return None

        _save_dynamic(niche, {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "trending_sources_count": len(all_titles),
            "topics": topics,
        })
        print(f"  refresher {niche}: ✅ {len(topics)} topics frescos guardados")
        return topics
    except Exception as e:
        print(f"  refresher {niche} fail: {type(e).__name__}: {e}")
        return None


def get_all_topics_merged(static_pool: list[dict], niche: str) -> list[dict]:
    """Devuelve pool estático + dinámicos (dedup por key). Auto-refresca
    si toca. Llamado desde channel_pipeline._pick_topic."""
    if is_refresh_due(niche):
        refresh_topics_for(niche)  # side-effect: guarda a disco
    dyn = _load_dynamic(niche).get("topics", [])
    seen_keys = {t.get("key") for t in static_pool}
    fresh = [t for t in dyn if t.get("key") not in seen_keys]
    return list(static_pool) + fresh


def refresh_all_niches() -> dict[str, int]:
    """Refresca los 4 nichos económico-legales + motor. CLI entry."""
    result = {}
    for niche in ("tax", "legal", "ayudas", "motor"):
        topics = refresh_topics_for(niche)
        result[niche] = len(topics) if topics else 0
    return result
