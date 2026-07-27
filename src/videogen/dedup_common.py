"""Constantes y helpers de dedup compartidos por autogen y longgen.

Extracto de la lógica que estaba inline en `telegram_bot._run_autogen_daily`
para reutilizarla también en `_run_longgen_weekly` (el bug del 26/07 fue
tener KEYWORDS_ALREADY_COVERED solo en autogen — longgen lo ignoraba y
generó Colza, Fórum, RUMASA repetidos).
"""
from __future__ import annotations

import re

# Palabras/nombres que ya se han cubierto y que el regex `proper_nouns` puede
# no capturar solo (palabras en minúscula, aliases múltiples). Se combina con
# `proper_nouns` extraído de los títulos reales de YouTube — así los casos que
# YA se subieron se detectan automáticamente, y esta lista solo añade aliases
# y palabras minúsculas ambiguas.
KEYWORDS_ALREADY_COVERED: set[str] = {
    # Aceite de Colza — "colza" y "aceite" a menudo aparecen en minúsculas
    "colza", "aceite de colza",
    # Fórum Filatélico — aliases múltiples
    "afinsa", "nummers",
    # RUMASA — el regex no captura "RUMASA" (todo mayúsculas ≥5 chars sí,
    # ≥4 sí ahora) pero mantengo por seguridad
    "rumasa", "ruiz-mateos",
    # Gürtel — variantes con/sin diéresis
    "gürtel", "gurtel",
    # ERE Andalucía — 2 palabras
    "ere andalucía", "ere andalucia",
}

# Stopwords que NO deben contar como nombre propio útil (aunque el regex las
# capture por empezar con mayúscula al inicio de una frase).
NON_NOUNS_STOP: set[str] = {
    "como", "cómo", "españa", "españoles", "españolas", "millones",
    "banco", "bolsa", "estafa", "fraude", "caso", "sentencia",
    "billones", "euros", "año", "años",
}

# Regex que captura nombres propios (MixedCase y ALLCAPS con >= 4 chars).
_NOUN_RE = re.compile(r"\b(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{3,}|[A-ZÁÉÍÓÚÑ]{4,})\b")


def proper_nouns(text: str) -> set[str]:
    """Extrae nombres propios normalizados en minúsculas."""
    return {w.lower() for w in _NOUN_RE.findall(text)}


def has_covered_keyword(text: str) -> set[str]:
    """Devuelve el set de keywords 'ya cubiertas' presentes en el texto."""
    t = text.lower()
    return {kw for kw in KEYWORDS_ALREADY_COVERED if kw in t}


def dedup_ideas(ideas: list[str], seen_titles: set[str],
                recent_nouns: set[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Filtra `ideas` contra 3 capas: substring de títulos ya subidos,
    intersección de nombres propios, y keywords blacklist manual.

    Devuelve (fresh, skipped) — `skipped` es lista de (idea, razón).
    """
    recent_nouns = recent_nouns - NON_NOUNS_STOP
    fresh: list[str] = []
    skipped: list[tuple[str, str]] = []
    for idea in ideas:
        t = idea.lower().strip()
        if any(t in s or s in t for s in seen_titles if s):
            skipped.append((idea, "substring"))
            continue
        overlap = proper_nouns(idea) & recent_nouns
        if overlap:
            skipped.append((idea, f"propn:{overlap}"))
            continue
        kw_hit = has_covered_keyword(idea)
        if kw_hit:
            skipped.append((idea, f"kw:{kw_hit}"))
            continue
        fresh.append(idea)
    return fresh, skipped
