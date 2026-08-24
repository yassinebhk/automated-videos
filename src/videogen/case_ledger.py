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


# ─────────────────────────────────────────────────────────────────────────
# Pool ACTUALIDAD — "historia detrás de los titulares"
# Tono OBJETIVO obligatorio. Solo contexto histórico + hechos verificables.
# NO opinión política. NO temas que YT desmonetiza automáticamente
# (Palestina-Israel, Ucrania-Rusia — política oficial YT 'sensitive events'
# desde 2023 → flag automático).
# ─────────────────────────────────────────────────────────────────────────
TEMAS_ACTUALIDAD: list[dict] = [
    {"key": "ceuta_melilla_frontera", "name": "Ceuta y Melilla — frontera con África",
     "aliases": ["ceuta melilla", "frontera ceuta", "frontera melilla"],
     "hint": "Origen s.XV cuando pasan a España; por qué siguen siendo españolas; conflictos migratorios; posición histórica de Marruecos"},
    {"key": "opep_petroleo", "name": "OPEP y el poder del petróleo",
     "aliases": ["opep", "petróleo geopolítica", "arabia saudi petróleo"],
     "hint": "1960 Bagdad; crisis 1973 por qué; embargo árabe; poder de la OPEP hoy; dependencia europea"},
    {"key": "otan_origen", "name": "OTAN — por qué existe",
     "aliases": ["otan", "nato origen", "alianza atlántica"],
     "hint": "1949 tras II GM; contexto Guerra Fría; España entra en 1982; qué obligaciones supone artículo 5"},
    {"key": "euro_origen", "name": "El euro — cómo llegó aquí",
     "aliases": ["euro origen", "moneda única", "tratado maastricht"],
     "hint": "1992 Maastricht; qué renunciamos al firmarlo; por qué no lo tienen UK o Suecia; problemas actuales"},
    {"key": "deuda_espana_historia", "name": "Deuda pública española — cómo se llegó ahí",
     "aliases": ["deuda pública", "deuda soberana españa", "rescate bancario"],
     "hint": "De la Transición al 100% PIB; los rescates 2012; qué significa; comparativa con Alemania"},
    {"key": "sahara_occidental", "name": "Sáhara Occidental — el conflicto",
     "aliases": ["sáhara occidental", "sahara occidental", "polisario"],
     "hint": "1975 marcha verde; posición España como potencia colonial; ONU; Marruecos vs Polisario hechos"},
    {"key": "gibraltar_historia", "name": "Gibraltar — por qué es británico",
     "aliases": ["gibraltar", "peñón gibraltar"],
     "hint": "1713 Utrecht; guerra sucesión española; qué dice el tratado; posición actual UE post-Brexit"},
    {"key": "brexit_historia", "name": "Brexit — cronología del divorcio",
     "aliases": ["brexit historia", "salida uk"],
     "hint": "2016 referéndum; qué acordaron; qué cambió para españoles; economía UK después"},
    {"key": "euro_zona_2010", "name": "Crisis euro 2010-2012 — qué pasó",
     "aliases": ["crisis euro", "crisis grecia", "rescate grecia"],
     "hint": "Grecia detonante; España en la cuerda floja; Draghi 'whatever it takes'; MEDE"},
    {"key": "franco_transicion", "name": "Transición española — cómo se hizo",
     "aliases": ["transición española", "transicion 78", "constitución 78"],
     "hint": "1975-1978; pactos de la Moncloa; ley amnistía; qué se decidió no juzgar"},
    {"key": "23f_intento_golpe", "name": "23-F — intento de golpe",
     "aliases": ["23-f", "23f", "tejero"],
     "hint": "1981; qué pasó realmente; papel del Rey; sentencia contra Tejero + Milans"},
    {"key": "eta_desarme", "name": "ETA — cómo llegó al desarme",
     "aliases": ["eta desarme", "banda armada", "fin eta"],
     "hint": "1968 primer atentado; víctimas totales; negociaciones; 2011 fin; 2017 desarme; 2018 disolución"},
    {"key": "china_potencia", "name": "China — cómo se convirtió en potencia",
     "aliases": ["china economía", "china potencia", "deng xiaoping"],
     "hint": "1978 Deng reformas; entrada OMC 2001; segunda economía mundo; nueva ruta seda"},
    {"key": "elon_musk_negocios", "name": "El imperio Musk — cómo se construyó",
     "aliases": ["musk imperio", "tesla spacex", "twitter x compra"],
     "hint": "PayPal 1999; Tesla 2004; SpaceX; compra Twitter 44B$ 2022; hechos verificables"},
    {"key": "criptomonedas_origen", "name": "Bitcoin — origen y qué es realmente",
     "aliases": ["bitcoin origen", "criptomonedas historia", "satoshi"],
     "hint": "2008 whitepaper; Satoshi anónimo; primera pizza 10.000 BTC; boom 2017 y 2021; regulación EU"},
    {"key": "chip_taiwan", "name": "Taiwán y los chips — geopolítica",
     "aliases": ["taiwan chips", "tsmc", "semiconductores"],
     "hint": "TSMC controla 60% chips avanzados; posición China; consecuencias para Europa"},
    {"key": "gas_ruso_europa", "name": "Dependencia energética Europa-Rusia",
     "aliases": ["gas ruso", "nord stream", "gazprom europa"],
     "hint": "Historia gasoductos; Nord Stream 1+2; crisis 2022; qué hicieron los países europeos"},
    {"key": "amazon_imperio", "name": "Amazon — de librería online a imperio",
     "aliases": ["amazon origen", "bezos librería", "amazon prime"],
     "hint": "1994 fundación Bezos; primera acción; AWS 2006 negocio real; posición monopolístico regulación EU"},
    {"key": "boe_como_funciona", "name": "BOE — cómo se legisla en España",
     "aliases": ["boe", "diario oficial", "leyes españa cómo"],
     "hint": "Historia desde 1661; Gaceta Madrid; hoy; diferencia entre RD, RDL, ley orgánica; quién decide"},
    {"key": "cambio_climatico_datos", "name": "Cambio climático — solo datos",
     "aliases": ["cambio climático", "ipcc datos", "temperatura global"],
     "hint": "IPCC reports; +1.1°C confirmado; consenso científico; políticas Paris 2015 hechos"},
]


def _all_pools() -> list[dict]:
    """Devuelve pool combinado con etiqueta kind."""
    out = []
    for c in INFRAUTILIZADOS:
        out.append({**c, "kind": "crime"})
    for c in TEMAS_ACTUALIDAD:
        out.append({**c, "kind": "actualidad"})
    return out


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
    Busca en AMBOS pools (crime + actualidad).
    Ej: match_case_key("Caso KIO fraude bolsa") → 'kio'
        match_case_key("Origen conflicto Ceuta Melilla") → 'ceuta_melilla_frontera'
    """
    tl = text.lower()
    for case in _all_pools():
        for alias in case["aliases"]:
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


def available_cases_for_prompt(days: int = 180, sample_size: int = 15,
                                 mix_actualidad_pct: int = 30) -> list[dict]:
    """Devuelve pool mixto crime + actualidad excluyendo usados últimos N días.

    mix_actualidad_pct: porcentaje del sample dedicado a temas de actualidad
    (default 30% — 70% crime porque el nicho principal es true crime español).
    Shuffle determinista por día ISO → cada día distinto orden, mismo run coherente.
    """
    used = get_recent_case_keys(days=days)
    crime_pool = [{**c, "kind": "crime"}
                  for c in INFRAUTILIZADOS if c["key"] not in used]
    act_pool = [{**c, "kind": "actualidad"}
                for c in TEMAS_ACTUALIDAD if c["key"] not in used]

    n_act = max(1, int(sample_size * mix_actualidad_pct / 100))
    n_crime = sample_size - n_act

    seed = datetime.now(timezone.utc).toordinal()
    rng = random.Random(seed)
    rng.shuffle(crime_pool)
    rng.shuffle(act_pool)

    return crime_pool[:n_crime] + act_pool[:n_act]


def format_pool_for_prompt(days: int = 180) -> str:
    """Renderiza el pool disponible como texto para el system prompt.
    Marca cada entry con [CRIMEN] o [ACTUALIDAD] para que Gemini sepa qué
    framing usar (crimen = punchy hook con cifra; actualidad = neutro y objetivo).
    """
    pool = available_cases_for_prompt(days=days)
    if not pool:
        pool = [{**c, "kind": "crime"} for c in INFRAUTILIZADOS[:15]]
    lines = []
    for c in pool:
        tag = "[CRIMEN]" if c.get("kind") == "crime" else "[ACTUALIDAD]"
        lines.append(f"- {tag} **{c['name']}** — {c['hint']}")
    return "\n".join(lines)
