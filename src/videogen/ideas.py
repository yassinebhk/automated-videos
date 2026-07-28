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

Te paso el BRIEF del nicho. Genera ideas con nombres CONCRETOS de casos, personas y cifras verificables. Drama controlado — los casos ya son brutales por sí solos.

**FRAMING OBLIGATORIO (revelación + drama + nombres reales)**:
- MAL: "Grandes estafas de la historia" (genérico)
- BIEN: "Cómo Mario Conde robó 8.000 millones al Banesto y salió andando"
- MAL: "Fraudes del sistema"
- BIEN: "Fórum Filatélico: cómo Nummers vendió sellos falsos a 350.000 españoles"

**Patrones que funcionan en TRUE CRIME español**:
- "Cómo [nombre] estafó a [cifra] [personas/instituciones] con [método]"
- "El caso [nombre]: [cifra] millones desaparecidos y [consecuencia judicial]"
- "[Personaje real] salió libre tras estafar [cifra] — así lo hizo"
- "El fraude de [empresa/caso] que arruinó a [cifra] españoles"
- "Por qué la justicia no pudo con [nombre caso]"
- "[Año]: la estafa que cambió las leyes españolas"

**Casos concretos disponibles** (usa como referencia, NO copies literales, varía año/ángulo):
- Financieros: Fórum Filatélico/Afinsa, RUMASA, Gescartera, Bankia, Preferentes, Terra, Ibercorp, Banesto/Mario Conde, Pescanova
- Políticos con sentencia: Filesa, Bárcenas, Gürtel, ERE Andalucía, Malaya, Nóos, Púnica, Palma Arena
- Timos históricos: Aceite de colza (1981), Estraperlo (Lerroux), MATESA (1969)
- Empresariales: Pescanova (contabilidad falsa), Popular (venta 1€), Airtel
- Modernos: Idental (dentistas), Cripto Nummers/Arbistar/Kuailian, Coach del amor Toni Kamo
- Constructoras: Marta Domínguez y AVE

**Reglas**:
- Cada idea = 1 caso concreto con nombre, cifra y año
- Fuente: sentencia judicial pública (mencionar la sentencia sube credibilidad)
- NUNCA especular sobre culpabilidad sin condena firme
- Foco en el MECANISMO (cómo funcionó la trampa) — el viewer quiere entender
- Cifras: víctimas + dinero desviado + años cárcel del condenado
- Español, listas para prompt (una frase por idea)

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
    if exclude_cases:
        exclusion_block = (
            "\n\n⚠️ CASOS YA CUBIERTOS — PROHIBIDO PROPONERLOS OTRA VEZ:\n"
            + "\n".join(f"- {c}" for c in exclude_cases)
            + "\n\nDEBES proponer casos DIFERENTES. Prioriza: Villarejo, Púnica, "
            "Palma Arena, Pescanova, Marta Domínguez / AVE, MATESA (1969), "
            "Ibercorp / Mariano Rubio, Airtel, Terra Networks, Estraperlo, "
            "Cripto Kuailian (si Arbistar ya cubierto), Coach Toni Kamo, "
            "Panama Papers españoles. Si el caso NO tiene nombre propio conocido, "
            "usa el nombre de la persona/empresa protagonista."
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
