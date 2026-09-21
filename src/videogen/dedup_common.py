"""Constantes y helpers de dedup compartidos por autogen y longgen.

Extracto de la lógica que estaba inline en `telegram_bot._run_autogen_daily`
para reutilizarla también en `_run_longgen_weekly` (el bug del 26/07 fue
tener KEYWORDS_ALREADY_COVERED solo en autogen — longgen lo ignoraba y
generó Colza, Fórum, RUMASA repetidos).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────
# Anti-repeat SEMÁNTICO por TÍTULO (no solo por key de topic).
# Bug crítico 21/09: el dedup de los canales genéricos era solo por `key` del
# pool → el mismo TEMA con otra key (o generado por el refresher dinámico) se
# colaba. Resultado real: WaitWhy repitió "Mario Conde 8.000M" ×4, AI Tools
# 202 pares "Top 5 AI tools for X", Legal "falso autónomo · 20.000€" ×3.
# Estas helpers comparan el SIGNIFICADO del título (tokens normalizados) contra
# los títulos REALES ya publicados (leídos de stats_history.jsonl).
# ─────────────────────────────────────────────────────────────────────────
_TITLE_STOP = {
    # ES
    "el", "la", "los", "las", "de", "del", "que", "un", "una", "unos", "unas",
    "y", "a", "en", "por", "con", "para", "su", "sus", "al", "lo", "es", "son",
    "más", "mas", "top", "mejores", "mejor", "claves", "clave", "cosas", "como",
    "cómo", "qué", "que", "cuánto", "cuanto", "cuánta", "este", "esta", "cada",
    "hasta", "año", "años", "2025", "2026", "españa", "guía", "guia", "trucos",
    "truco", "señales", "señal", "límites", "limites", "límite",
    # EN
    "the", "of", "to", "in", "for", "a", "an", "and", "your", "you", "how",
    "why", "what", "best", "top", "tools", "tool", "shorts", "short", "video",
    "videos", "guide", "ways", "tips", "things",
}
# ruido a quitar del título antes de tokenizar
_TITLE_NOISE = re.compile(r"(#\w+|[·|]\s*#?\d+.*$|\d+[\d.,]*\s*(€|euros?|millones?|k|m)\b)", re.I)


def norm_title(t: str) -> str:
    t = (t or "").lower()
    t = re.sub(r"#\w+", " ", t)                     # hashtags
    t = re.sub(r"[·|]\s*#?\d+.*$", " ", t)          # sufijo · #N / · 2026
    t = re.sub(r"[^\wáéíóúñü ]", " ", t)            # signos/emojis
    return re.sub(r"\s+", " ", t).strip()


def title_tokens(t: str) -> set[str]:
    return {w for w in norm_title(t).split() if len(w) >= 3 and w not in _TITLE_STOP}


def title_is_repeat(title: str, recent_titles, thr: float = 0.55) -> bool:
    """True si `title` se parece demasiado (tokens) a algún título reciente."""
    tk = title_tokens(title)
    if not tk:
        return False
    nt = norm_title(title)
    for r in recent_titles or ():
        rk = title_tokens(r)
        if not rk:
            continue
        if nt and nt == norm_title(r):
            return True
        # mismos tokens significativos → mismo tema (p.ej. "Top 5 AI tools for
        # MARKETING": el andamiaje es stopword y solo distingue 'marketing').
        if tk == rk:
            return True
        inter = len(tk & rk)
        union = len(tk | rk)
        if len(tk) >= 2 and union and inter / union >= thr:
            return True
        # contención: todos los tokens significativos de uno están en el otro
        if inter >= 2 and (inter == len(tk) or inter == len(rk)):
            return True
    return False


def _history_path() -> Path:
    try:
        from .config import ROOT
        return ROOT / "output" / "stats_history.jsonl"
    except Exception:
        return Path("output/stats_history.jsonl")


def recent_titles_from_history(platform, days: int = 150, limit: int = 300) -> list[str]:
    """Títulos de vídeos ya publicados (de stats_history) para uno o varios
    platform keys, de los últimos `days` días. Para dedup semántico."""
    import time as _t
    plats = {platform} if isinstance(platform, str) else set(platform)
    cutoff = _t.time() - days * 86400
    p = _history_path()
    if not p.exists():
        return []
    seen: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("kind") != "video" or r.get("platform") not in plats:
            continue
        if (r.get("ts") or 0) < cutoff:
            continue
        vid = r.get("video_id") or r.get("title")
        title = (r.get("title") or "").strip()
        if title:
            seen[vid] = title  # último título por vídeo
    return list(seen.values())[-limit:]


def recent_titles_block(platform, days: int = 150, n: int = 30) -> str:
    """Lista compacta de títulos recientes para inyectar en el prompt como
    'PROHIBIDO repetir'."""
    ts = recent_titles_from_history(platform, days=days)[-n:]
    return " · ".join(f"«{t[:70]}»" for t in ts)


def platform_key_for_prefix(yt_prefix: str) -> str:
    """YT_TAX → youtube_tax · YT_AITOOLS → youtube_aitools (convención analytics)."""
    return "youtube_" + (yt_prefix or "").replace("YT_", "").lower()

# Palabras/nombres que ya se han cubierto y que el regex `proper_nouns` puede
# no capturar solo (palabras en minúscula, aliases múltiples). Se combina con
# `proper_nouns` extraído de los títulos reales de YouTube — así los casos que
# YA se subieron se detectan automáticamente, y esta lista solo añade aliases
# y palabras minúsculas ambiguas.
KEYWORDS_ALREADY_COVERED: set[str] = {
    # === Aliases problemáticos ===
    # Bug 08-24: el regex proper_nouns exigía ≥4 chars y siglas cortas como
    # "KIO" (3) nunca se detectaban → 5 videos casi-idénticos sobre KIO en
    # 3 días. Ahora regex baja a 3 chars + estas siglas cortas en blacklist
    # como cinturón y tirantes.

    # Colza minúsculas + aliases Fórum
    "aceite de colza", "afinsa", "nummers",
    # Variantes sin diéresis
    "gurtel",
    # Siglas cortas (aunque el regex ahora las capture, aquí como refuerzo)
    "kio", "torres kio", "grand tibidabo",
    "psv", "cooperativa psv",
    "itv catalunya", "itv cataluña",
    "ere andalucía", "ere andalucia",
    "psoe filesa", "filesa",
}

# Stopwords que NO deben contar como nombre propio útil (aunque el regex las
# capture por empezar con mayúscula al inicio de una frase).
# Ampliado porque bajamos regex a 3 chars → más falsos positivos.
NON_NOUNS_STOP: set[str] = {
    "como", "cómo", "españa", "españoles", "españolas", "millones",
    "banco", "bolsa", "estafa", "fraude", "caso", "sentencia",
    "billones", "euros", "año", "años",
    # 3 chars — palabras comunes que pueden empezar frase con mayúscula
    "los", "las", "sus", "una", "más", "hoy", "así", "que", "por",
    "para", "sin", "con", "sobre", "todo", "todos", "tras",
    "esto", "esta", "está", "aún", "muy", "van", "hay",
    "www", "com", "net", "org",
}

# Regex que captura nombres propios (MixedCase y ALLCAPS con >= 3 chars).
# Bajado de 4 → 3 para capturar KIO, PSV, ITV, PSOE, ONU, etc.
_NOUN_RE = re.compile(r"\b(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}|[A-ZÁÉÍÓÚÑ]{3,})\b")


def proper_nouns(text: str) -> set[str]:
    """Extrae nombres propios normalizados en minúsculas.
    Filtra las stopwords para reducir falsos positivos (bug 08-24: al bajar
    regex a 3 chars aparecían "los", "que", etc. y contaminaban la
    intersección con títulos históricos)."""
    return {w.lower() for w in _NOUN_RE.findall(text)} - NON_NOUNS_STOP


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
