"""Pool long-form AyudaGob — semillas + auto-refresh según actualidad BOE."""
from __future__ import annotations

TOPICS = [
    {"key": "long_todas_ayudas_autonomos", "audiencia": "autonomos", "categoria": "guia",
     "titulo": "TODAS las ayudas para AUTÓNOMOS 2026 · mes a mes explicadas",
     "hook": "Tarifa plana, Kit Digital, PAE, ENISA, ICO — completo",
     "cifra_ancla": "hasta €75k préstamo + €12k Kit"},

    {"key": "long_becas_universidad_completo", "audiencia": "estudiantes", "categoria": "guia",
     "titulo": "GUÍA COMPLETA becas universidad España 2026 · MEC + autonómicas",
     "hook": "Requisitos MEC, umbrales renta, plazos, cuantías por tramo",
     "cifra_ancla": "hasta €6.000/curso"},

    {"key": "long_vivienda_joven_todas", "audiencia": "particulares", "categoria": "guia",
     "titulo": "TODAS las ayudas VIVIENDA joven 2026 · bonos, avales, deducciones",
     "hook": "Bono alquiler €250 + aval ICO 20% + reforma eficiencia",
     "cifra_ancla": "€250-€10.800 según ayuda"},

    {"key": "long_family_completo", "audiencia": "familias", "categoria": "guia",
     "titulo": "AYUDAS familia 2026: maternidad, IVI, familia numerosa, dependencia",
     "hook": "Todos los cheques + prestaciones + descuentos por hijo",
     "cifra_ancla": "€1.200-€2.400/año típico"},

    {"key": "long_dependencia_completo", "audiencia": "familias", "categoria": "guia",
     "titulo": "Ley DEPENDENCIA 2026: grados, prestación, procedimiento paso a paso",
     "hook": "Grado I/II/III + solicitud + tiempo respuesta + cuantía",
     "cifra_ancla": "€442-€1.100/mes según grado"},

    {"key": "long_next_gen_ue", "audiencia": "empresas", "categoria": "guia",
     "titulo": "Fondos NEXT GENERATION EU 2026 · qué queda para pymes ES",
     "hook": "Kit Digital, PERTE, IDAE, MOVES III — proyecto por proyecto",
     "cifra_ancla": "hasta €12.5M avales"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
