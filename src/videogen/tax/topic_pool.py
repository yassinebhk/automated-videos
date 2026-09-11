"""Pool de temas fiscales españoles para Shorts.

Organizados por audiencia (autónomos / particulares / empresas) y por
categoría (deducciones / obligaciones / trucos / novedades). Datos base
verificables 2026 — Gemini enriquece con cifras concretas en el script.

Rotación: ledger `output/tax_ledger.json` marca usados; cooldown 90 días
para permitir revisitar con dato actualizado (año fiscal).
"""
from __future__ import annotations


TOPICS = [
    # ─── AUTÓNOMOS: deducciones ───
    {"key": "auto_gastos_deducibles", "audiencia": "autonomos",
     "categoria": "deducciones",
     "titulo": "5 gastos que TODO autónomo puede deducirse (y no sabe)",
     "hook": "Suministros del hogar, dietas, formación, seguro salud, coche parcial",
     "cifra_ancla": "hasta 30% ahorro IRPF"},

    {"key": "auto_iva_deducible", "audiencia": "autonomos",
     "categoria": "deducciones",
     "titulo": "IVA que puedes recuperar como autónomo (con factura correcta)",
     "hook": "Gasolina, comidas de trabajo, material, alquiler local, teléfono",
     "cifra_ancla": "21% recuperable"},

    {"key": "auto_teletrabajo", "audiencia": "autonomos",
     "categoria": "deducciones",
     "titulo": "Autónomo teletrabajando: cómo deducir tu casa oficina en 2026",
     "hook": "30% del m² afecto × suministros + amortización",
     "cifra_ancla": "hasta €200/mes"},

    {"key": "auto_dietas", "audiencia": "autonomos",
     "categoria": "deducciones",
     "titulo": "Dietas del autónomo: €26.67/día sin justificar en España",
     "hook": "Límite legal + condiciones + qué documentar",
     "cifra_ancla": "€26.67/día España"},

    {"key": "auto_coche_afecto", "audiencia": "autonomos",
     "categoria": "deducciones",
     "titulo": "Coche del autónomo: 50%, 100% o 0% deducible — la clave",
     "hook": "Uso exclusivo profesional vs mixto vs personal",
     "cifra_ancla": "50%-100% IVA"},

    # ─── AUTÓNOMOS: obligaciones ───
    {"key": "auto_mod130", "audiencia": "autonomos",
     "categoria": "obligaciones",
     "titulo": "Modelo 130: qué es y cuándo NO tienes que presentarlo",
     "hook": "20% beneficio trimestral, excepción si 70% clientes retienen",
     "cifra_ancla": "20% trimestral"},

    {"key": "auto_cuota_2026", "audiencia": "autonomos",
     "categoria": "obligaciones",
     "titulo": "Nueva cuota autónomos 2026: cuánto pagas según tus ingresos",
     "hook": "Tramos reales, tabla completa",
     "cifra_ancla": "€230-€590/mes"},

    {"key": "auto_iva_trimestral", "audiencia": "autonomos",
     "categoria": "obligaciones",
     "titulo": "Cómo hacer tu IVA trimestral solo (sin gestoría)",
     "hook": "Modelo 303 explicado en 60s — casillas clave",
     "cifra_ancla": "€150-€300 ahorro/año"},

    {"key": "auto_estimacion_directa", "audiencia": "autonomos",
     "categoria": "obligaciones",
     "titulo": "Estimación directa vs simplificada: cuál te conviene",
     "hook": "Diferencias, cuándo saltar, gastos permitidos",
     "cifra_ancla": "hasta €600.000 ingresos"},

    # ─── AUTÓNOMOS: trucos ───
    {"key": "auto_facturar_menos_ganar_mas", "audiencia": "autonomos",
     "categoria": "trucos",
     "titulo": "Facturar menos y ganar más: el juego de tramos IRPF",
     "hook": "Diferir facturas + reinvertir + deducciones plena",
     "cifra_ancla": "hasta €5.000 ahorro"},

    {"key": "auto_baja_cuota_pluri", "audiencia": "autonomos",
     "categoria": "trucos",
     "titulo": "Pluriactividad: cómo reducir tu cuota autónomo si trabajas también por cuenta ajena",
     "hook": "Bonificación 50% + devolución retroactiva",
     "cifra_ancla": "50% descuento primer año"},

    {"key": "auto_hijos_pareja_deducciones", "audiencia": "autonomos",
     "categoria": "trucos",
     "titulo": "Contratar a tu pareja como autónomo: cuánto ahorras",
     "hook": "Sueldo deducible + tramos IRPF familia + Seguridad Social",
     "cifra_ancla": "€2.000-4.000 ahorro/año"},

    # ─── PARTICULARES: IRPF ───
    {"key": "part_deduc_alquiler", "audiencia": "particulares",
     "categoria": "deducciones",
     "titulo": "Deducción por alquiler vivienda 2026: quién y cuánto",
     "hook": "10.05% estatal + autonómicas — Andalucía, Madrid, Cataluña",
     "cifra_ancla": "hasta €1.200/año"},

    {"key": "part_plan_pension", "audiencia": "particulares",
     "categoria": "deducciones",
     "titulo": "Planes de pensiones 2026: cuánto puedes desgravar de verdad",
     "hook": "Límite €1.500 particular + €10.000 empresa — quién gana",
     "cifra_ancla": "€1.500-€10.000 desgrava"},

    {"key": "part_donaciones_ong", "audiencia": "particulares",
     "categoria": "deducciones",
     "titulo": "Donar a ONG: 80% deducción hasta €250, después 40%",
     "hook": "Ley Mecenazgo 2026 + fideliza 3 años = +40%",
     "cifra_ancla": "80%/40%/45%"},

    {"key": "part_reforma_vivienda", "audiencia": "particulares",
     "categoria": "deducciones",
     "titulo": "Deducción por obras vivienda: hasta €7.500 por reformar",
     "hook": "Eficiencia energética + habitual + certificado",
     "cifra_ancla": "hasta €7.500 desgrava"},

    {"key": "part_familia_numerosa", "audiencia": "particulares",
     "categoria": "deducciones",
     "titulo": "Familia numerosa: €1.200-€2.400/año deducibles + otras ayudas",
     "hook": "Deducción IRPF + cheques escolares + IBI",
     "cifra_ancla": "€1.200-€2.400/año"},

    {"key": "part_maternidad", "audiencia": "particulares",
     "categoria": "deducciones",
     "titulo": "Deducción por maternidad: €1.200/año + €1.000 guardería",
     "hook": "Trabajadoras activas + hijo <3 años",
     "cifra_ancla": "€1.200+€1.000"},

    # ─── PARTICULARES: bolsa/inversión ───
    {"key": "part_etf_tributacion", "audiencia": "particulares",
     "categoria": "obligaciones",
     "titulo": "Cómo tributan tus ETFs en España 2026 (ojo, cambió)",
     "hook": "19-28% ganancia + traspasos NO están exentos",
     "cifra_ancla": "19-28% tramo"},

    {"key": "part_criptos_tributacion", "audiencia": "particulares",
     "categoria": "obligaciones",
     "titulo": "Cripto en España: cuánto Hacienda te quita si vendes",
     "hook": "19-28% + modelo 721 obligatorio + FIFO",
     "cifra_ancla": "19-28% + modelo 721"},

    {"key": "part_dividendos", "audiencia": "particulares",
     "categoria": "obligaciones",
     "titulo": "Dividendos: los primeros €1.500 NO están exentos desde 2015",
     "hook": "Se acabó el chollo — tributas desde €0",
     "cifra_ancla": "19% desde €0"},

    # ─── PARTICULARES: trucos ───
    {"key": "part_venta_vivienda_65", "audiencia": "particulares",
     "categoria": "trucos",
     "titulo": "Vender tu casa con +65 años: 100% exento de IRPF",
     "hook": "Habitual + reinversión NO obligatoria",
     "cifra_ancla": "100% exento"},

    {"key": "part_reinversion_vivienda", "audiencia": "particulares",
     "categoria": "trucos",
     "titulo": "Vender casa y comprar otra: exención por reinversión",
     "hook": "Habitual + 2 años + reinvertir el 100%",
     "cifra_ancla": "100% exención"},

    {"key": "part_perdidas_bolsa", "audiencia": "particulares",
     "categoria": "trucos",
     "titulo": "Cómo usar tus pérdidas en bolsa para pagar MENOS Hacienda",
     "hook": "Compensación 4 años + regla 2 meses",
     "cifra_ancla": "hasta -25% base"},

    # ─── EMPRESAS ───
    {"key": "emp_deduc_id", "audiencia": "empresas",
     "categoria": "deducciones",
     "titulo": "Deducción I+D+i: hasta 42% del gasto directo",
     "hook": "Proyecto certificado + informe motivado + Hacienda",
     "cifra_ancla": "25-42%"},

    {"key": "emp_deduc_contratacion", "audiencia": "empresas",
     "categoria": "deducciones",
     "titulo": "Contratar joven <30 años: bonificaciones 2026",
     "hook": "Bonificación 3 años + reducción Seguridad Social",
     "cifra_ancla": "€300-€500/mes"},

    {"key": "emp_deduc_reservas", "audiencia": "empresas",
     "categoria": "deducciones",
     "titulo": "Reserva capitalización: cómo pagar menos IS legalmente",
     "hook": "10% del beneficio no distribuido — Sociedades",
     "cifra_ancla": "10% base IS"},

    # ─── NOVEDADES ───
    {"key": "novedad_ley_startups", "audiencia": "empresas",
     "categoria": "novedades",
     "titulo": "Ley de Startups: 15% Sociedades 4 años + stock options",
     "hook": "Requisitos ENISA + tributación stock options 50k€",
     "cifra_ancla": "15% IS · €50k exento"},

    {"key": "novedad_teletrabajo_ley", "audiencia": "autonomos",
     "categoria": "novedades",
     "titulo": "Novedad 2026: teletrabajo obligado a pagar suministros del empleado",
     "hook": "Empresa paga proporcional + deducción para autónomos",
     "cifra_ancla": "min €30-€100/mes"},

    {"key": "novedad_impuesto_solidaridad", "audiencia": "particulares",
     "categoria": "novedades",
     "titulo": "Impuesto Grandes Fortunas 2026: quién paga y cuánto",
     "hook": "€3M patrimonio + tramos 1.7-3.5% + prórroga",
     "cifra_ancla": "1.7-3.5%"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None


def by_audiencia(aud: str) -> list[dict]:
    return [t for t in TOPICS if t.get("audiencia") == aud]
