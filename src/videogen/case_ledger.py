"""Registro persistente de casos ya cubiertos.

Bug 08-24: Gemini repite el mismo caso (KIO 5×) porque:
1. El regex proper_nouns exigía ≥4 chars → siglas cortas (KIO, PSV) no se
   detectaban → se colaban por dedup.
2. La lista de "infrautilizados" del prompt tenía KIO al inicio → Gemini se
   anclaba al primero que veía.

Este módulo:
- Extrae el "case_key" canónico del topic elegido (Roldán, Grand Tibidabo…).
- Lo persiste en output/case_ledger.json con timestamp.
- Expone `get_recent_case_keys(days=180)` para ir excluyendo del prompt.
- Expone `available_cases()` que rota el pool de infrautilizados excluyendo
  los ya cubiertos recientemente → Gemini ve un pool DISTINTO cada llamada.
"""
from __future__ import annotations

import json
import random
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .config import ROOT


LEDGER_PATH = ROOT / "output" / "case_ledger.json"


# Pool maestro de casos infrautilizados con sentencia — ordenado por prioridad.
# Cada caso tiene múltiples aliases para reconocerlo en títulos.
INFRAUTILIZADOS: list[dict] = [
    {"key": "roldan", "name": "Roldán", "aliases": ["roldán", "roldan"],
     "hint": "Jefe Guardia Civil, robó 1.500M pesetas, huyó a Laos"},
    {"key": "filesa", "name": "Filesa", "aliases": ["filesa"],
     "hint": "Financiación ilegal PSOE, STS 1997"},
    {"key": "naseiro", "name": "Naseiro", "aliases": ["naseiro"],
     "hint": "Financiación ilegal PP, SAP Valencia 1994"},
    {"key": "kio", "name": "KIO", "aliases": ["kio", "torres kio", "torres"],
     "hint": "Fraude bursátil 300M€ familia real saudí, STS 2000"},
    {"key": "grand_tibidabo", "name": "Grand Tibidabo",
     "aliases": ["grand tibidabo", "javier de la rosa"],
     "hint": "Javier de la Rosa, fraude 40M€"},
    {"key": "blesa", "name": "Blesa (Bankia black cards)",
     "aliases": ["blesa", "tarjetas black", "tarjetas opacas"],
     "hint": "Tarjetas black Caja Madrid/Bankia, STS 2015"},
    {"key": "millet", "name": "Millet / Palau Música",
     "aliases": ["millet", "palau música", "palau de la música", "palau musica"],
     "hint": "Desvío 26M€ Palau Catalunya, 2018 9 años cárcel"},
    {"key": "faisan", "name": "Caso Faisán",
     "aliases": ["faisán", "faisan"],
     "hint": "Fuga ETA con ayuda policial, STS 2013"},
    {"key": "camps", "name": "Camps (trajes Fabra)",
     "aliases": ["camps", "trajes fabra", "trajes camps"],
     "hint": "Corrupción PP Valencia, STS 2012"},
    {"key": "3por100", "name": "Caso 3%",
     "aliases": ["caso 3%", "el 3%", "3 por ciento", "cdc catalunya", "cdc cataluña"],
     "hint": "Financiación ilegal CDC Catalunya, STS 2018"},
    {"key": "erial", "name": "Erial",
     "aliases": ["erial", "rita barberá", "rita barbera"],
     "hint": "Corrupción PP Valencia (Rita Barberá), 2015"},
    {"key": "andratx", "name": "Andratx",
     "aliases": ["andratx"],
     "hint": "Urbanismo Mallorca, 40 alcaldes imputados, STS 2010"},
    {"key": "ballena_blanca", "name": "Ballena Blanca",
     "aliases": ["ballena blanca"],
     "hint": "Blanqueo 250M€, STS 2009"},
    {"key": "emperador", "name": "Emperador",
     "aliases": ["operación emperador", "operacion emperador", "mafia china"],
     "hint": "Mafia china blanqueo 300M€, 2016"},
    {"key": "nueva_rumasa", "name": "Nueva Rumasa",
     "aliases": ["nueva rumasa", "ruiz-mateos hijos"],
     "hint": "Hijos Ruiz-Mateos, 200.000 estafados, STS 2019"},
    {"key": "psv", "name": "PSV cooperativa",
     "aliases": ["psv", "cooperativa psv", "grupo sindical"],
     "hint": "Cooperativa vivienda, 20.000 damnificados, 1993"},
    {"key": "neurona", "name": "Neurona (Podemos)",
     "aliases": ["neurona", "podemos financiación"],
     "hint": "Financiación Podemos, 2020"},
    {"key": "koldo", "name": "Caso Koldo / Ábalos",
     "aliases": ["koldo", "ábalos", "abalos", "mascarillas covid"],
     "hint": "Comisiones mascarillas COVID, 2024"},
    {"key": "innova_farma", "name": "Innova Farma",
     "aliases": ["innova farma", "innova-farma"],
     "hint": "Fraude sanitario, 2009"},
    {"key": "itv_cataluna", "name": "ITV Cataluña",
     "aliases": ["itv cataluña", "itv catalunya", "itv cataluna"],
     "hint": "Mafia inspecciones ITV Catalunya, 2008"},
    {"key": "poyato", "name": "Barreiros",
     "aliases": ["barreiros", "fraude barreiros"],
     "hint": "Fraude industrial años 70"},
    {"key": "pocero", "name": "El Pocero (Seseña)",
     "aliases": ["pocero", "seseña", "sesena"],
     "hint": "Fraude urbanístico 4.000M€ Toledo"},
    {"key": "estepona", "name": "Caso Estepona",
     "aliases": ["estepona urbanismo", "operación estepona"],
     "hint": "Urbanismo Estepona, 2008"},
    {"key": "camboya_mallorca", "name": "Camboya Mallorca",
     "aliases": ["camboya mallorca", "antoni miquel"],
     "hint": "Fraude Mallorca años 90"},
    {"key": "malaya", "name": "Malaya (Roca)",
     "aliases": ["malaya", "juan antonio roca", "marbella corrupción"],
     "hint": "Urbanismo Marbella, STS 2013"},
    {"key": "divar", "name": "Caso Dívar",
     "aliases": ["dívar", "divar", "consejo poder judicial"],
     "hint": "Consejo General Poder Judicial, 2012"},
    {"key": "faisan_naseiro", "name": "Naseiro tapes",
     "aliases": ["naseiro"],
     "hint": "Escuchas Naseiro PP 1990"},
    {"key": "punica_lezo", "name": "Lezo",
     "aliases": ["lezo", "operación lezo", "operacion lezo", "aguirre lezo"],
     "hint": "Corrupción Madrid, 2017"},
    {"key": "tandem_villarejo", "name": "Tándem (Villarejo)",
     "aliases": ["tándem", "tandem villarejo"],
     "hint": "Villarejo espionaje, 2017 (distinto de otros Villarejos)"},
    {"key": "voxpopuli", "name": "Voxpopuli fraude",
     "aliases": ["voxpopuli"],
     "hint": "Fraude periodismo, 2019"},
]


def _load_ledger() -> dict:
    if LEDGER_PATH.exists():
        try:
            return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"cases": {}}
    return {"cases": {}}


def _save_ledger(data: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def match_case_key(text: str) -> str | None:
    """Devuelve el case_key canónico si el texto contiene algún alias.
    Ej: match_case_key("Caso KIO fraude bolsa") → 'kio'
    """
    tl = text.lower()
    for case in INFRAUTILIZADOS:
        for alias in case["aliases"]:
            # Match como palabra completa (para no confundir "kio" con "kiosco")
            if re.search(rf"\b{re.escape(alias)}\b", tl):
                return case["key"]
    return None


def register_used_case(topic: str) -> str | None:
    """Registra en el ledger que hemos usado este caso. Devuelve el key
    identificado, o None si el topic no matchea ningún caso conocido."""
    key = match_case_key(topic)
    if not key:
        return None
    data = _load_ledger()
    cases = data.setdefault("cases", {})
    entry = cases.setdefault(key, {"count": 0, "history": []})
    entry["count"] += 1
    entry["history"].append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "topic": topic[:200],
    })
    # Limita historial a los últimos 10 por caso
    entry["history"] = entry["history"][-10:]
    _save_ledger(data)
    return key


def get_recent_case_keys(days: int = 180) -> set[str]:
    """Devuelve el set de case_keys usados en los últimos N días."""
    data = _load_ledger()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = set()
    for key, entry in data.get("cases", {}).items():
        for h in entry.get("history", []):
            try:
                ts = datetime.fromisoformat(h["ts"])
                if ts >= cutoff:
                    recent.add(key)
                    break
            except Exception:
                pass
    return recent


def available_cases_for_prompt(days: int = 180, sample_size: int = 15) -> list[dict]:
    """Devuelve el pool de INFRAUTILIZADOS excluyendo los usados en N días
    y hace SHUFFLE para que Gemini no se ancle a los primeros de la lista.

    Este es el fix principal del bug 08-24 (5 videos de KIO seguidos).
    """
    used = get_recent_case_keys(days=days)
    available = [c for c in INFRAUTILIZADOS if c["key"] not in used]
    # Shuffle determinista por día ISO — cada día ve un orden distinto pero
    # dentro del mismo día siempre el mismo (para runs múltiples coherentes).
    seed = datetime.now(timezone.utc).toordinal()
    rng = random.Random(seed)
    rng.shuffle(available)
    return available[:sample_size]


def format_pool_for_prompt(days: int = 180) -> str:
    """Renderiza el pool disponible como texto para el system prompt."""
    pool = available_cases_for_prompt(days=days)
    if not pool:
        # Fallback: todos disponibles otra vez si agotamos el pool
        pool = INFRAUTILIZADOS[:15]
    lines = []
    for c in pool:
        lines.append(f"- **{c['name']}** — {c['hint']}")
    return "\n".join(lines)
