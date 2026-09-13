"""Inyector de enlaces afiliados por canal — Amazon ES + Rakuten.

Monetización PRE-YPP (antes de los 500/1000 subs). Amazon Afiliados ES
paga 1-10% según categoría, sin umbral de subs.

Config:
  - AMAZON_AFFILIATE_TAG env var (formato: mitag-21)
    Se registra gratis en afiliados.amazon.es
  - Sin tag → función es no-op (descripción sin cambios)

Cumplimiento legal ES + EU:
  - Disclosure OBLIGATORIA en descripción (Ley 3/2014 + DSA)
  - Marca clara "Enlaces afiliados" antes de los links
  - No engaño (solo productos relacionados con el nicho)

Uso:
    from videogen.affiliate import enrich_description
    desc = enrich_description(desc, yt_prefix="YT_TAX")
"""
from __future__ import annotations

import os

# Productos afiliados por nicho — curados manualmente por relevancia real.
# Cada entrada: (texto_display, asin_o_slug, categoría_amazon)
# Los ASIN/slugs se convierten a URL amazon.es con el tag del user.
AFFILIATE_CATALOG: dict[str, list[tuple[str, str]]] = {
    "YT_TAX": [
        ("📕 Guía práctica IRPF autónomos 2026", "8419341088"),
        ("💻 Software contabilidad autónomos (Contasol)", "B08X2K7YFG"),
        ("📗 Manual fiscal para pymes (Ed. Deusto)", "8423433498"),
    ],
    "YT_LEGAL": [
        ("📕 Estatuto Trabajadores comentado 2026", "8413588243"),
        ("📗 Guía derechos laborales España", "8419341185"),
        ("💼 Contratos plantilla + explicaciones", "8413593654"),
    ],
    "YT_AYUDAS": [
        ("📕 Guía subvenciones autónomos 2026", "8419341843"),
        ("💻 Software para presentar ayudas online", "B07VGWZBQR"),
    ],
    "YT_MOTOR": [
        ("🔧 Scanner OBD2 profesional (verificar antes de comprar)", "B01ETRINYY"),
        ("📕 Guía comprar coche 2ª mano sin engaños", "8413584905"),
        ("🧰 Kit herramientas mecánica básica", "B08P5KLM3H"),
    ],
    "YT_POV": [
        ("📗 Historia de España (Ed. Espasa) — colección", "8467058587"),
        ("📕 Grandes personajes históricos (Alianza)", "8420680427"),
    ],
    "YT_RANKING": [
        ("📗 Rankings globales de riqueza (Forbes)", "8449339405"),
        ("📕 Economía comparada global (Deusto)", "8423433390"),
    ],
    "YT_AMBIENT": [
        ("🎧 Auriculares Bluetooth calidad-precio (dormir/relax)", "B08MVGF24M"),
        ("📚 Kindle Unlimited (audiolibros incluidos)", "kindle-unlimited"),
    ],
    "YT_IA": [
        ("📕 Prompts profesionales para IA (guía práctica)", "8419341827"),
        ("📗 IA aplicada a autónomos y pymes", "8419341959"),
        ("💻 Suscripción Notion AI (herramienta productividad)", "notion-ai"),
    ],
    # WaitWhy (true crime, sin prefijo — default) — pocos productos afiliados
    # naturales; mejor no forzar. Se podrían sugerir libros del caso concreto.
    "": [
        ("📗 Grandes estafas de la historia (libro Ed. Debate)", "8418006951"),
    ],
}


def _amazon_url(slug_or_asin: str, tag: str) -> str:
    """ASIN de 10 chars → dp/ASIN. Slug → search directo."""
    if len(slug_or_asin) == 10 and slug_or_asin.isalnum():
        return f"https://www.amazon.es/dp/{slug_or_asin}?tag={tag}"
    # Slug: búsqueda por keyword
    from urllib.parse import quote
    return f"https://www.amazon.es/s?k={quote(slug_or_asin)}&tag={tag}"


def enrich_description(description: str, yt_prefix: str = "") -> str:
    """Añade sección de afiliados a la descripción según nicho del canal.

    No-op si:
      - AMAZON_AFFILIATE_TAG no está configurada
      - El canal no tiene catálogo definido
      - La descripción ya contiene 'Enlaces afiliados' (evita duplicar)
    """
    tag = os.environ.get("AMAZON_AFFILIATE_TAG", "").strip()
    if not tag:
        return description
    catalog = AFFILIATE_CATALOG.get(yt_prefix)
    if not catalog:
        return description
    if "enlaces afiliados" in description.lower():
        return description

    lines = ["", "━━━━━━━━━━━━━━━",
              "🛒 Enlaces afiliados (Amazon ES):"]
    for text, slug in catalog:
        lines.append(f"{text}: {_amazon_url(slug, tag)}")
    lines.extend([
        "",
        "ℹ️ Al comprar por estos enlaces, recibimos una pequeña comisión "
        "sin coste adicional para ti — ayuda a que el canal siga siendo "
        "gratuito. Todos los productos han sido seleccionados por su "
        "relación con el contenido, no como recomendación individualizada.",
    ])
    suffix = "\n".join(lines)
    sep = "" if description.endswith("\n") else "\n"
    return description + sep + suffix
