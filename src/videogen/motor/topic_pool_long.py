"""Pool long-form Motor60s — semillas + auto-refresh según actualidad DGT."""
from __future__ import annotations

TOPICS = [
    {"key": "long_guia_comprar_2mano", "audiencia": "compradores", "categoria": "guia",
     "titulo": "GUÍA COMPLETA para comprar coche 2ª mano 2026 · sin engaños",
     "hook": "Peritaje, ITV, historial DGT, contrato, transfer — todo paso a paso",
     "cifra_ancla": "€60-€150 peritaje ahorra €1000+"},

    {"key": "long_etiquetas_dgt_todo", "audiencia": "propietarios", "categoria": "guia",
     "titulo": "TODAS las etiquetas DGT · qué coche puede entrar dónde 2026",
     "hook": "0 · ECO · C · B · A · sin distintivo — ZBE ciudades",
     "cifra_ancla": "prohibido A/B ZBE Madrid 2026"},

    {"key": "long_electricos_2mano_completo", "audiencia": "compradores", "categoria": "guia",
     "titulo": "Coches ELÉCTRICOS 2ª mano 2026 · qué revisar antes de comprar",
     "hook": "Salud batería (SoH), garantía, actualizaciones, precios modelo",
     "cifra_ancla": "SoH >80% obligatorio · €12k-€35k"},

    {"key": "long_diesel_futuro", "audiencia": "propietarios", "categoria": "guia",
     "titulo": "DIESEL en España 2026-2035 · vender ya o mantener",
     "hook": "Prohibición UE 2035 + ZBE restricciones + valor residual",
     "cifra_ancla": "-40% valor 2020-2026"},

    {"key": "long_mantenimiento_todo", "audiencia": "propietarios", "categoria": "guia",
     "titulo": "TODO el mantenimiento de tu coche 2026 · cada km · costes",
     "hook": "Aceite, filtros, distribución, embrague, frenos — calendario",
     "cifra_ancla": "€300-€1.500 revisión completa"},

    {"key": "long_vender_particular", "audiencia": "vendedores", "categoria": "guia",
     "titulo": "VENDER tu coche particular 2026 · precio, fotos, contrato, transfer",
     "hook": "Ganvam para precio + coches.net foto + gestoría transfer",
     "cifra_ancla": "€30-€60 transfer · €500-€2000 más particular"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
