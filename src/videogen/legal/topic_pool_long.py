"""Pool long-form (~7 min) TusDerechos ES — semillas.
Se COMPLEMENTA con auto-refresh según actualidad (BOE / novedades laborales)."""
from __future__ import annotations

TOPICS = [
    {"key": "long_estatuto_completo", "audiencia": "trabajadores", "categoria": "guia",
     "titulo": "Estatuto de los Trabajadores 2026 en 7 minutos · lo esencial",
     "hook": "Derechos, deberes, permisos, despidos, jornada — condensado",
     "cifra_ancla": "44 art clave"},

    {"key": "long_despido_guia_completa", "audiencia": "trabajadores", "categoria": "guia",
     "titulo": "GUÍA COMPLETA despidos 2026: nulo, improcedente, procedente, objetivo",
     "hook": "Diferencias, indemnización, plazo denuncia, casos reales",
     "cifra_ancla": "20-33 días/año según tipo"},

    {"key": "long_permisos_todos", "audiencia": "trabajadores", "categoria": "guia",
     "titulo": "TODOS los permisos retribuidos del ET 2026 explicados",
     "hook": "Matrimonio, fallecimiento, mudanza, deber público, formación",
     "cifra_ancla": "hasta 15 días pagados"},

    {"key": "long_jubilacion_planificar", "audiencia": "trabajadores", "categoria": "guia",
     "titulo": "Planificar tu JUBILACIÓN en España 2026 · edad, cotizaciones, cuantía",
     "hook": "Ordinaria vs anticipada vs demorada + coeficientes reductores",
     "cifra_ancla": "66y 6m ordinaria · €3.267 max"},

    {"key": "long_autonomo_derechos", "audiencia": "autonomos", "categoria": "guia",
     "titulo": "Derechos del AUTÓNOMO 2026: cese, IT, bajas, jubilación, paro",
     "hook": "Todo lo que cotiza y a qué da derecho — completo",
     "cifra_ancla": "€560-€1.500 cese/mes"},

    {"key": "long_falso_autonomo_todo", "audiencia": "autonomos", "categoria": "guia",
     "titulo": "FALSO AUTÓNOMO en España · señales, denuncia, indemnización",
     "hook": "Test 3 requisitos + procedimiento inspección + casos ganados TS",
     "cifra_ancla": "hasta €20k+ sanción empresa"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
