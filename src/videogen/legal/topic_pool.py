"""Pool de temas legal-laboral españoles.

Cubre: despidos, permisos, salarios, contratos, jornada, discriminación,
ERTE, autónomos vs trabajadores, cotizaciones, jubilación, IT/baja médica.

Fuente base: Estatuto de los Trabajadores + BOE 2026. Gemini enriquece
con cifras concretas y ejemplos. SIEMPRE disclaimer legal obligatorio.
"""
from __future__ import annotations


TOPICS = [
    # ─── DESPIDOS ───
    {"key": "desp_nulo", "audiencia": "trabajadores", "categoria": "despidos",
     "titulo": "3 causas de despido NULO — indemnización + readmisión",
     "hook": "Embarazo, IT, discriminación por sexo/edad/raza",
     "cifra_ancla": "readmisión obligada + salarios de tramitación"},

    {"key": "desp_improcedente", "audiencia": "trabajadores", "categoria": "despidos",
     "titulo": "Despido improcedente 2026: 33 días por año, tope 24 mensualidades",
     "hook": "Cálculo real, salario regulador, límite",
     "cifra_ancla": "33 días/año · máx 24 meses"},

    {"key": "desp_disciplinario", "audiencia": "trabajadores", "categoria": "despidos",
     "titulo": "TOP 5 motivos de despido disciplinario válidos según ET",
     "hook": "Faltas repetidas, agresión, embriaguez laboral, fraude",
     "cifra_ancla": "0€ indemnización si procede"},

    # ─── PERMISOS RETRIBUIDOS ───
    {"key": "perm_matrimonio", "audiencia": "trabajadores", "categoria": "permisos",
     "titulo": "TOP 5 permisos retribuidos que TODO trabajador tiene",
     "hook": "15 días matrimonio, 2 días fallecimiento familiar, mudanza, deberes públicos",
     "cifra_ancla": "hasta 15 días pagados"},

    {"key": "perm_lactancia", "audiencia": "trabajadores", "categoria": "permisos",
     "titulo": "Lactancia acumulada: 15 días juntos vs 1h/día",
     "hook": "Cómo pedirlo, hasta 9 meses del bebé",
     "cifra_ancla": "15 días acumulados"},

    {"key": "perm_asuntos_propios", "audiencia": "trabajadores", "categoria": "permisos",
     "titulo": "Permiso 'asuntos propios' 2026 — cuándo TIENES derecho",
     "hook": "Convenio colectivo lo regula, no ley general",
     "cifra_ancla": "3-6 días típico"},

    # ─── SALARIOS Y NÓMINAS ───
    {"key": "sal_smi_2026", "audiencia": "trabajadores", "categoria": "salarios",
     "titulo": "SMI 2026: €1.184 en 14 pagas — cifra oficial",
     "hook": "Neto vs bruto, jornada parcial, incidencia IRPF",
     "cifra_ancla": "€1.184 SMI 14 pagas"},

    {"key": "sal_horas_extras", "audiencia": "trabajadores", "categoria": "salarios",
     "titulo": "Horas extras: cómo cobrarlas obligatoriamente en 2026",
     "hook": "Límite 80/año, precio hora, compensar con descanso",
     "cifra_ancla": "máx 80/año · +75%"},

    {"key": "sal_pagas_extras", "audiencia": "trabajadores", "categoria": "salarios",
     "titulo": "Pagas extras: pueden pagarse prorrateadas si lo pides",
     "hook": "Junio y Navidad, prorrateo mensual, cotización",
     "cifra_ancla": "2 pagas anuales"},

    # ─── CONTRATOS ───
    {"key": "cont_temporal_fraude", "audiencia": "trabajadores", "categoria": "contratos",
     "titulo": "3 señales de contrato temporal EN FRAUDE de ley 2026",
     "hook": "Encadenar contratos, sin causa real, más de X meses",
     "cifra_ancla": "conversión indefinido"},

    {"key": "cont_indefinido_fijo", "audiencia": "trabajadores", "categoria": "contratos",
     "titulo": "TOP 5 diferencias contrato indefinido vs temporal 2026",
     "hook": "Indemnización, cotización, vacaciones, extras, jubilación",
     "cifra_ancla": "33 vs 12 días/año despido"},

    {"key": "cont_periodo_prueba", "audiencia": "trabajadores", "categoria": "contratos",
     "titulo": "Periodo de prueba: máximo 6 meses técnicos, 2 no cualificados",
     "hook": "Convenio manda, mujer embarazada = nulo despedirla",
     "cifra_ancla": "2-6 meses según cualificación"},

    # ─── JORNADA Y VACACIONES ───
    {"key": "jorn_registro", "audiencia": "trabajadores", "categoria": "jornada",
     "titulo": "Registro horario 2026: obligación empresa + multa €7.500",
     "hook": "Fichar entrada/salida, 4 años conservación, sanción alta",
     "cifra_ancla": "multa €625-€7.500"},

    {"key": "vac_dias", "audiencia": "trabajadores", "categoria": "jornada",
     "titulo": "22 días vacaciones + 14 festivos = 36 días LIBRES 2026",
     "hook": "Mínimo legal, convenio puede ampliar, no compensables",
     "cifra_ancla": "22+14 días"},

    {"key": "jorn_reduccion_hijos", "audiencia": "trabajadores", "categoria": "jornada",
     "titulo": "Reducción jornada por hijo <12: hasta 87.5% menos horas",
     "hook": "Guarda legal, decisión unilateral trabajador, sin justificar",
     "cifra_ancla": "1/8 a 1/2 de jornada"},

    # ─── IT / BAJA MÉDICA ───
    {"key": "it_calculo", "audiencia": "trabajadores", "categoria": "it_baja",
     "titulo": "Baja médica común: 60% base 1er día, 75% desde día 21",
     "hook": "Cálculo exacto, quién paga (empresa/SS), duración máx",
     "cifra_ancla": "60% / 75% base reguladora"},

    {"key": "it_at_100", "audiencia": "trabajadores", "categoria": "it_baja",
     "titulo": "Baja accidente laboral: 75% desde el día 1 (no 4to)",
     "hook": "Diferencia con enfermedad común, mutua paga",
     "cifra_ancla": "75% desde día 1"},

    # ─── AUTÓNOMOS LABORAL ───
    {"key": "trap_falso_autonomo", "audiencia": "autonomos", "categoria": "contratos",
     "titulo": "3 señales de FALSO AUTÓNOMO: sanción €20k a la empresa",
     "hook": "Horario impuesto, medios de la empresa, 1 solo cliente",
     "cifra_ancla": "multa €20.000+ · alta obligatoria"},

    {"key": "auto_cese_actividad", "audiencia": "autonomos", "categoria": "salarios",
     "titulo": "Cese de actividad autónomos: paro por 24 meses hasta €1.500",
     "hook": "Requisitos, tiempo cotizado, cuantía por tramo",
     "cifra_ancla": "€560-€1.500/mes · 4-24 meses"},

    # ─── JUBILACIÓN Y COTIZACIONES ───
    {"key": "jub_edad_2026", "audiencia": "trabajadores", "categoria": "jubilacion",
     "titulo": "Jubilación 2026: 66 años y 6 meses ordinaria",
     "hook": "38 años y 3 meses cotizados = 65 exacto",
     "cifra_ancla": "66y 6m · 38y 3m"},

    {"key": "jub_anticipada", "audiencia": "trabajadores", "categoria": "jubilacion",
     "titulo": "Jubilación anticipada 2026: hasta -30% pensión",
     "hook": "Voluntaria vs involuntaria, coeficientes reductores",
     "cifra_ancla": "-3.75% a -30% por adelanto"},

    {"key": "jub_pension_max", "audiencia": "trabajadores", "categoria": "jubilacion",
     "titulo": "Pensión máxima 2026: €3.267/mes en 14 pagas",
     "hook": "Base máxima cotización, tope legal",
     "cifra_ancla": "€3.267 max/14"},

    # ─── DISCRIMINACIÓN Y ACOSO ───
    {"key": "acoso_laboral", "audiencia": "trabajadores", "categoria": "derechos",
     "titulo": "Mobbing laboral: 3 pruebas VÁLIDAS en juicio",
     "hook": "Testigos, WhatsApp, informe médico, protocolo empresa",
     "cifra_ancla": "indemnización + despido nulo"},

    {"key": "disc_salarial", "audiencia": "trabajadores", "categoria": "derechos",
     "titulo": "Auditoría retributiva 2026: empresas >50 trabajadores obligadas",
     "hook": "Registro público, denunciar diferencia salarial mujer-hombre",
     "cifra_ancla": "multa €187k+ empresa"},

    # ─── ERTE Y CRISIS ───
    {"key": "erte_derechos", "audiencia": "trabajadores", "categoria": "derechos",
     "titulo": "ERTE 2026: TU sueldo baja pero se acumula antigüedad",
     "hook": "Suspensión vs reducción, paro consumido/no consumido",
     "cifra_ancla": "50-70% base según tramos"},

    # ─── PARO ───
    {"key": "paro_duracion", "audiencia": "trabajadores", "categoria": "salarios",
     "titulo": "Paro contributivo: 4 meses por cada año trabajado, máx 2 años",
     "hook": "70% base 6 meses, 50% después, tope",
     "cifra_ancla": "4 meses/año · máx 24m"},

    {"key": "paro_subsidio", "audiencia": "trabajadores", "categoria": "salarios",
     "titulo": "Subsidio desempleo 2026: €480/mes si ya no cobras paro",
     "hook": "Rentas insuficientes, hijos a cargo, +52 años",
     "cifra_ancla": "€480 · 6-30 meses"},

    # ─── EXCEDENCIAS ───
    {"key": "exc_voluntaria", "audiencia": "trabajadores", "categoria": "permisos",
     "titulo": "Excedencia voluntaria: 4 meses a 5 años, sin sueldo pero conservas plaza",
     "hook": "Requisitos, reserva puesto, cotización parada",
     "cifra_ancla": "4m-5y · reserva puesto"},

    {"key": "exc_hijo", "audiencia": "trabajadores", "categoria": "permisos",
     "titulo": "Excedencia por hijo <3 años: reserva puesto + cotización cotiza",
     "hook": "Sin sueldo pero SS acumula antigüedad + trienios",
     "cifra_ancla": "3 años · reserva puesto"},

    # ─── SANCIONES EMPRESA ───
    {"key": "sanc_amonestacion", "audiencia": "trabajadores", "categoria": "derechos",
     "titulo": "TU jefe NO puede sancionarte por 3 cosas legalmente",
     "hook": "Enfermar, embarazo, denunciar acoso, ejercer derechos",
     "cifra_ancla": "sanción nula + indemnización"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
