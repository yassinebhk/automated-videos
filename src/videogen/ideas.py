"""Generador de ideas de video específicas para el nicho (dinero).

Usa Gemini + el brief de nicho (niche.md) para proponer ideas concretas,
virales y listas para meter al bot — nunca genéricas.
"""
from __future__ import annotations

import json
import time

from google import genai
from google.genai import types

from .config import PROMPTS_DIR, gemini_key

MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"]
NICHE_PATH = PROMPTS_DIR / "niche.md"

IDEAS_SYSTEM = """Eres un estratega de contenido VIRAL para un canal de SHORTS sobre **TRUE CRIME ESPAÑOL** — estafas, fraudes, timos y escándalos con sentencia firme en España.

Te paso el BRIEF del nicho. Genera ideas con nombres CONCRETOS de casos, personas y cifras verificables.

**REGLA #1: NO PROPONER LOS CASOS OBVIOS** — este canal ya cubrió los 15 casos más famosos (Mario Conde/Banesto, Fórum Filatélico, RUMASA/Ruiz-Mateos, Bankia, Preferentes, Bárcenas, Gürtel, ERE Andalucía, Aceite Colza, Villarejo, Púnica, Palma Arena, Pescanova, MATESA, Ibercorp). Si propones alguno de estos, **la idea se descarta automáticamente**. Ve a casos MENOS conocidos con sentencia firme:

**CASOS ESPAÑOLES INFRAUTILIZADOS con sentencia** (prioriza estos, cada uno una idea distinta):
- **Roldán** — director Guardia Civil que robó 1.500M pesetas (STS 1998, 28 años cárcel)
- **Filesa** — trama financiación ilegal PSOE (STS 1997)
- **Naseiro** — financiación ilegal PP (SAP Valencia 1994)
- **KIO / Torres KIO** — fraude bolsa 300M€ (STS 2000)
- **Grand Tibidabo** — Javier de la Rosa, fraude 40M€
- **Blesa** — Bankia tarjetas black (STS 2015, 6 años)
- **Millet / Palau Música Catalunya** — 26M€ desviados (2018, 9 años cárcel)
- **Faisán** — fuga ETA con ayuda policial (STS 2013)
- **Camps** — trajes Fabra + PP Valencia (STS 2012)
- **3%** — financiación CDC Cataluña (STS 2018)
- **Erial** — corrupción PP Valencia (2015)
- **Andratx** — urbanismo Mallorca (STS 2010, 40 alcaldes imputados)
- **Ballena Blanca** — blanqueo 250M€ (STS 2009)
- **Emperador** — mafia china blanqueo 300M€ (2016)
- **Nueva Rumasa** — Ruiz-Mateos hijos (STS 2019, 200.000 estafados)
- **PSV / Grupo Sindical** — cooperativa vivienda (1993, 20.000 damnificados)
- **Neurona** — financiación Podemos (2020)
- **Koldo / Ábalos** — comisiones mascarillas COVID (2024)
- **Innova Farma** — fraude sanitario (2009)
- **ITV Cataluña** — mafia inspecciones (2008)
- **Camboya / Antoni Miquel** — fraude Mallorca años 90
- **Fórum Nummers** ≠ Fórum Filatélico → coach de amor Toni Kamo NO es "Coach del amor Toni Kamo" que ya cubrimos
- **AVE Perpiñán-Figueres** — sobrecostes constructoras
- **Presos ETA / mesas kale borroka** — dinero desviado

**Casos internacionales con conexión española** también valen: **Panama Papers españoles**, **Pandora Papers Cataluña**, **Volkswagen dieselgate España**, **Deutsche Telekom fraude Airtel**.

**FRAMING obligatorio (revelación + drama + nombres reales)**:
- MAL: "Grandes estafas de la historia" (genérico)
- BIEN: "Roldán: cómo el jefe de la Guardia Civil robó 1.500 millones y huyó a Laos"
- BIEN: "Millet y el saqueo del Palau: 26 millones robados en Catalunya"

**Patrones de título que funcionan**:
- "Cómo [nombre] estafó a [cifra] con [método]"
- "El caso [nombre]: [cifra] millones y [consecuencia]"
- "[Personaje real] robó [cifra] y [pena]"
- "[Año]: el fraude que [consecuencia]"

**Reglas duras**:
- Cada idea = 1 caso concreto con nombre + cifra + año
- Fuente: sentencia judicial pública (menciona el tribunal si conoces)
- NUNCA especular sobre culpabilidad sin condena firme
- Foco en el MECANISMO (cómo funcionó la trampa)
- Cifras: víctimas + dinero desviado + años cárcel del condenado
- Español, listas para prompt (una frase por idea)
- **PROHIBIDO REPETIR** los 15 casos famosos listados arriba

Devuelve SOLO JSON: {"ideas": ["idea 1", "idea 2", ...]}"""


def generate_ideas(n: int = 5, exclude_cases: list[str] | None = None) -> list[str]:
    """Genera ideas vía Gemini. Robusto frente a 503 spikes y fences markdown.

    exclude_cases: nombres de casos YA cubiertos → Gemini debe evitarlos.
    Sin esto, Gemini insiste con los casos del inicio del brief y siempre
    devuelve duplicados (bug 28/07: dedup bloqueaba todo, autogen abortaba).
    """
    import re as _re
    api_key = gemini_key()
    if not api_key:
        return []
    niche = NICHE_PATH.read_text(encoding="utf-8") if NICHE_PATH.exists() else ""
    client = genai.Client(api_key=api_key)
    cfg = types.GenerateContentConfig(
        system_instruction=IDEAS_SYSTEM,
        response_mime_type="application/json",
        temperature=1.0,  # subido de 0.9 → 1.0 para más diversidad
        max_output_tokens=2048,
    )
    exclusion_block = ""
    # Pool rotativo diario: excluye casos ya cubiertos (persistente) y hace
    # shuffle → Gemini ve un orden distinto cada día → deja de anclarse a KIO.
    from . import case_ledger
    pool_text = case_ledger.format_pool_for_prompt(days=180)
    if pool_text:
        exclusion_block = (
            f"\n\n📋 CASOS DISPONIBLES HOY (pool rotativo — ya excluidos "
            f"los usados últimos 180 días):\n{pool_text}\n\n"
            f"Elige UN caso de esta lista. NO propongas casos que no estén aquí. "
            f"Diversifica: 1 político, 1 financiero, 1 urbanístico, 1 sanitario, 1 histórico."
        )
    if exclude_cases:
        exclusion_block += (
            "\n\n⚠️ ADEMÁS PROHIBIDO PROPONER (ya cubiertos últimos meses):\n"
            + "\n".join(f"- {c}" for c in exclude_cases)
        )
    contents = (
        f"BRIEF DEL NICHO:\n{niche}{exclusion_block}\n\n"
        f"Genera {n} ideas de video específicas — CASOS NUEVOS, no repitas."
    )
    last_err = None
    for model in MODELS:
        # 4 intentos con backoff 5/10/20/40 s — los picos de 503 duran minutos
        for attempt in range(4):
            try:
                resp = client.models.generate_content(model=model, contents=contents, config=cfg)
                raw = (resp.text or "").strip()
                if raw.startswith("```"):  # strip markdown fences si Gemini los mete
                    raw = _re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=_re.MULTILINE)
                data = json.loads(raw or "{}")
                ideas = [str(x).strip() for x in data.get("ideas", []) if str(x).strip()]
                if ideas:
                    return ideas[:n]
                last_err = "Gemini devolvió JSON válido pero lista vacía"
            except json.JSONDecodeError as e:
                last_err = f"JSON inválido: {e}"
                time.sleep(2)
            except Exception as e:
                s = str(e)
                last_err = f"{type(e).__name__}: {s[:120]}"
                # 429 RESOURCE_EXHAUSTED = cuota DIARIA agotada, no timeout momentáneo.
                # No merece reintentar dentro del mismo modelo — pasa al siguiente ya.
                if "RESOURCE_EXHAUSTED" in s or ("429" in s and "quota" in s.lower()):
                    print(f"  ideas: {model} cuota AGOTADA (429), salto al siguiente modelo")
                    break
                # 503/UNAVAILABLE = spike temporal, sí merece reintento con backoff
                if any(m in s for m in ("503", "UNAVAILABLE")):
                    wait = 5 * (2 ** attempt)
                    print(f"  ideas: {model} busy ({attempt+1}/4), espera {wait}s…")
                    time.sleep(wait)
                else:
                    break
        print(f"  ideas: {model} agotado, siguiente modelo… ({last_err})")
    print(f"  ideas: TODOS los modelos fallaron · último error: {last_err}")
    return []
