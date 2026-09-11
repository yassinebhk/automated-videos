"""Pool long-form (~7 min) TaxHack ES — temas de profundidad.
Cada tema da para 5-7 min con múltiples capítulos."""
from __future__ import annotations

TOPICS = [
    {"key": "long_autonomo_completo", "audiencia": "autonomos", "categoria": "guia",
     "titulo": "GUÍA COMPLETA autónomo 2026: alta, cuota, deducciones, jubilación",
     "hook": "Todo lo que un autónomo debe saber en 7 minutos",
     "cifra_ancla": "cuota €230-€590 · deducciones €5.000/año típico"},

    {"key": "long_irpf_tramos_historia", "audiencia": "particulares", "categoria": "historia",
     "titulo": "IRPF en España: los tramos que TE toca pagar en 2026 y por qué",
     "hook": "Historia de los tramos IRPF, evolución 2000-2026, comparativa autonómica",
     "cifra_ancla": "19-47% según tramo"},

    {"key": "long_iva_completo", "audiencia": "empresas", "categoria": "guia",
     "titulo": "TODOS los tipos de IVA en España EXPLICADOS + trucos legales",
     "hook": "0% / 4% / 10% / 21% / regímenes especiales · qué te toca",
     "cifra_ancla": "4-21% según producto"},

    {"key": "long_deducciones_familia_completo", "audiencia": "familias", "categoria": "guia",
     "titulo": "TODAS las deducciones familiares del IRPF 2026 · hasta €5.000/año",
     "hook": "Maternidad, familia numerosa, hijos, personas mayores, discapacidad",
     "cifra_ancla": "€1.200-€5.000/año"},

    {"key": "long_pension_planificar", "audiencia": "particulares", "categoria": "guia",
     "titulo": "Planificar tu JUBILACIÓN 2026: plan pensiones, PIAS, ETFs, inmobiliario",
     "hook": "Comparativa productos + fiscalidad + rentabilidad histórica",
     "cifra_ancla": "límite €1.500 planes 2026"},

    {"key": "long_stock_options_startups", "audiencia": "empresas", "categoria": "guia",
     "titulo": "Ley Startups 2026: 15% Sociedades + stock options €50k exentos",
     "hook": "Cómo aprovecharla + requisitos ENISA + casos reales de éxito ES",
     "cifra_ancla": "15% IS · €50k stock options exentos"},

    {"key": "long_crypto_hacienda", "audiencia": "particulares", "categoria": "guia",
     "titulo": "Cripto en España 2026: modelo 721, tributación, casos prácticos",
     "hook": "Modelo 721 obligatorio + FIFO + tratamiento fiscal completo",
     "cifra_ancla": "19-28% + modelo 721 <€50k"},

    {"key": "long_declaracion_renta_paso_a_paso", "audiencia": "particulares", "categoria": "guia",
     "titulo": "Declaración de la Renta 2026 PASO A PASO · ahorros que casi nadie usa",
     "hook": "Casilla por casilla + deducciones autonómicas + errores comunes",
     "cifra_ancla": "ahorro medio €500-€1.500/año"},

    {"key": "long_empresa_sl_crear", "audiencia": "empresas", "categoria": "guia",
     "titulo": "Crear una SL en España 2026 · coste, impuestos, ventajas vs autónomo",
     "hook": "Tramitación 24h + capital €1 + comparativa fiscal completa",
     "cifra_ancla": "€1 capital · €600 gastos totales"},

    {"key": "long_novedades_fiscales_2026", "audiencia": "empresas", "categoria": "novedades",
     "titulo": "NOVEDADES fiscales 2026 · todo lo que cambia y cómo te afecta",
     "hook": "Recopilación BOE 2026: SMI, cotizaciones, IRPF, IVA, IS, autónomos",
     "cifra_ancla": "según cambio BOE"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
