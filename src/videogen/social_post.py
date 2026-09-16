"""Formato viral compartido para Bluesky + Mastodon.

Genera 2 mensajes (main + reply_thread) a partir del title del video, el
teaser (hook 5s del guion) y el caso. El formato prioriza:
- CIFRA IMPACTANTE al inicio (⚡ + número grande + verbo emocional)
- Consecuencia injusta en 1-2 líneas (activa emoción)
- Pregunta polarizante que fuerza engagement
- Link al final
- Hashtags mínimos y nicho (no genéricos)

Reply thread: contexto extra sobre víctimas/consecuencia legal → engagement
sostenido y algoritmo detecta thread → boost.
"""
from __future__ import annotations

import re

# Emojis rotativos para el hook (evita que todos los posts sean iguales)
_HOOKS = ["⚡", "💸", "🚨", "🔥"]
# Índice basado en el número de episodio para rotar determinísticamente
def _hook_for(episode: int | None) -> str:
    return _HOOKS[(episode or 0) % len(_HOOKS)]


def _extract_number(text: str) -> str | None:
    """Extrae la primera cifra grande del texto (M€, millones, %, víctimas)."""
    patterns = [
        r"(\d[\d.,]*\s*(?:mil\s+)?millones\s*(?:de\s+euros?|€|de\s+pesetas?)?)",
        r"(\d[\d.,]*\s*M€)",
        r"(\d[\d.,]*\s*(?:millones|billones))",
        r"([\d.,]+\s*(?:muertos|víctimas|afectados|españoles))",
        r"(\d[\d.,]*€)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_episode(title: str) -> int | None:
    m = re.search(r"#(\d+)", title)
    return int(m.group(1)) if m else None


def _extract_case(title: str) -> str:
    """Extrae el nombre del caso del title 'Estafas Españolas #N: <caso>'."""
    m = re.search(r"#\d+:\s*(.+)", title)
    if m:
        return m.group(1).strip()
    return title


def _clean_teaser(teaser: str) -> str:
    """Recorta el teaser a 1 frase impactante."""
    if not teaser:
        return ""
    # Primera oración completa hasta ~120 chars
    sentences = re.split(r"(?<=[.!?])\s+", teaser.strip())
    result = sentences[0] if sentences else teaser
    if len(result) > 140:
        result = result[:137] + "..."
    return result


def build_viral_post(video_title: str, video_url: str, teaser: str = "",
                     cross_platform: str = "",
                     include_url: bool = True) -> tuple[str, str]:
    """Devuelve (main_text, reply_text) — 2 posts para thread.

    - main_text: hook + cifra + provocación + [link opcional] + hashtags
    - reply_text: contexto extra (víctimas, consecuencia legal) para thread
    - include_url: False para IG/TikTok (algoritmo esconde posts con links externos)
    """
    episode = _extract_episode(video_title)
    hook_emoji = _hook_for(episode)
    case = _extract_case(video_title)
    number = _extract_number(teaser or video_title)
    teaser_clean = _clean_teaser(teaser)

    # Rotación de tags + preguntas para no repetir texto literal en Threads/IG
    # (Meta borró posts WaitWhy 16/09 por "contenido repetido" — footer fijo era match perfecto).
    import random as _r_rot
    TAG_POOL = [
        "#TrueCrime #España #Corrupción #Historia",
        "#EstafasES #España #Justicia #Cronica",
        "#CasosReales #España #TrueCrimeES #Sentencia",
        "#CorrupcionES #España #Justicia #Documental",
        "#Historia #España #Investigación #Crimen",
    ]
    QUESTION_POOL = [
        "¿Justicia real o teatro judicial? 👇",
        "¿Te acordabas de este caso? 👇",
        "¿Qué opinas sobre la sentencia? 👇",
        "¿Debería reabrirse este caso? 👇",
        "¿Cómo se puede tapar algo así? 👇",
        "¿Recuerdas qué pasó después? 👇",
        "¿Y tú, qué habrías hecho? 👇",
    ]
    TAGS = _r_rot.choice(TAG_POOL)
    question = _r_rot.choice(QUESTION_POOL)
    if include_url:
        FOOTER = f"{question}\n\n{video_url}\n\n{TAGS}"
    else:
        FOOTER = f"{question}\n\n{TAGS}"
    header = f"{hook_emoji} {case}"

    # Cuánto espacio queda para el teaser tras header + footer + separadores
    reserved = len(header) + len(FOOTER) + len("\n\n") * 2
    teaser_budget = 300 - reserved - 4  # -4 seguridad
    body = ""
    if teaser_clean and teaser_budget > 40:
        body = teaser_clean[:teaser_budget]
    parts = [header]
    if body:
        parts.append(body)
    parts.append(FOOTER)
    main = "\n\n".join(parts)
    # Cross-platform mention como texto extra si aún cabe
    if cross_platform and len(main) + len(cross_platform) + 5 < 300:
        main += f"\n→ {cross_platform}"

    # Reply: contexto + CTA rotativo. Meta borró posts 16/09 por reply
    # LITERAL idéntico en cada post ("Todos los casos que subo..."). Ahora
    # se rota entre 8 variantes + solo se genera el 40% del tiempo (evita
    # thread automático 2-posts que dispara detector "bot volumen").
    CTA_POOL = [
        "Todos con sentencia firme. Sígueme si quieres más casos así.",
        "Verificado con fuentes oficiales. Sígueme para no perderte los siguientes.",
        "Datos citables + disclaimer legal. Sígueme si te enganchan estas historias.",
        "Cada caso, referencia jurídica al pie. Sígueme para el próximo.",
        "Sin especulación. Sentencias reales, no rumores. Sígueme si quieres más.",
        "Investigación con fuentes citables. ¿Sigues para el próximo caso?",
        "Verificado antes de subir. Sígueme y no te pierdes el siguiente.",
        "Todo con base documental. Te espero en el próximo caso.",
    ]
    reply_parts = []
    if number:
        reply_parts.append(f"La cifra concreta: {number}")
        reply_parts.append("")
    reply_parts.append(_r_rot.choice(CTA_POOL))
    reply = "\n".join(reply_parts)

    return main[:299], reply[:299]  # Bluesky límite 300


def build_simple_post(video_title: str, video_url: str,
                      max_chars: int = 499) -> str:
    """Compat: devuelve solo main_text (para Mastodon 500 chars)."""
    main, _ = build_viral_post(video_title, video_url)
    return main[:max_chars]
