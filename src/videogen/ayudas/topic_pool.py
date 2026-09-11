"""Pool ayudas y subvenciones España 2026.
Fuente: BOE, Seguridad Social, MEC, SEPE, CCAA."""
from __future__ import annotations


TOPICS = [
    # ─── AUTÓNOMOS ───
    {"key": "auto_tarifa_plana", "audiencia": "autonomos", "categoria": "cuota",
     "titulo": "Tarifa plana autónomos 2026: €80/mes primer año",
     "hook": "Requisitos, prórroga, bonif adicional mujer/discap/<30",
     "cifra_ancla": "€80/mes 12 meses"},

    {"key": "auto_kit_digital", "audiencia": "autonomos", "categoria": "empresarial",
     "titulo": "Kit Digital 2026: hasta €12.000 para digitalizar tu negocio",
     "hook": "Segmento por empleados, agentes digitalizadores, cómo pedirlo",
     "cifra_ancla": "€2k-€12k según segmento"},

    {"key": "auto_pae", "audiencia": "autonomos", "categoria": "empresarial",
     "titulo": "Pagas a autónomo por contratar 1 empleado: hasta €14.000",
     "hook": "Contrato indefinido joven, mujer, mayor 45 años",
     "cifra_ancla": "€3.000-€14.000/año"},

    # ─── FAMILIA ───
    {"key": "fam_ivi", "audiencia": "familias", "categoria": "familia",
     "titulo": "Prestación IVI 2026: €200/mes por hijo <18 años (renta baja)",
     "hook": "Umbrales renta, hijos discapacidad multiplican",
     "cifra_ancla": "€100-€200/mes hijo"},

    {"key": "fam_maternidad", "audiencia": "familias", "categoria": "familia",
     "titulo": "Baja paternidad/maternidad: 16 semanas al 100% del salario",
     "hook": "6 semanas obligatorias tras parto, 10 disfrutar libremente",
     "cifra_ancla": "16 semanas · 100%"},

    {"key": "fam_num_ayuda", "audiencia": "familias", "categoria": "familia",
     "titulo": "Familia numerosa 2026: TOP 5 ayudas + descuentos €1.500/año",
     "hook": "Título FN, deducción IRPF, IBI, transporte, guardería",
     "cifra_ancla": "€1.500-€2.400/año"},

    {"key": "fam_cheque_bebe", "audiencia": "familias", "categoria": "familia",
     "titulo": "Cheque bebé 2026: €2.500 pago único por nacimiento (CCAA)",
     "hook": "Cataluña €650, Madrid €500, Andalucía €400 — varía",
     "cifra_ancla": "€400-€2.500 según CCAA"},

    # ─── VIVIENDA ───
    {"key": "viv_bono_alquiler", "audiencia": "particulares", "categoria": "vivienda",
     "titulo": "Bono Alquiler Joven 2026: €250/mes hasta 2 años",
     "hook": "Menores 35, contrato registrado, requisitos renta",
     "cifra_ancla": "€250 x 24 meses"},

    {"key": "viv_ayuda_primera", "audiencia": "particulares", "categoria": "vivienda",
     "titulo": "Ayuda 1ª vivienda joven: €10.800 aval ICO 20% entrada",
     "hook": "Menores 35, cobertura estatal, requisitos ICO",
     "cifra_ancla": "20% entrada aval"},

    {"key": "viv_reforma", "audiencia": "particulares", "categoria": "vivienda",
     "titulo": "Ayudas eficiencia energética: hasta 80% coste reforma",
     "hook": "Aislamiento, ventanas, aerotermia — Next Generation EU",
     "cifra_ancla": "40-80% subvención"},

    # ─── EMPLEO / JOVEN ───
    {"key": "emp_activa_joven", "audiencia": "trabajadores", "categoria": "empleo",
     "titulo": "Ayuda activación empleo 2026: €480/mes 6 meses joven",
     "hook": "Sin ingresos, +18 <30, formación obligatoria",
     "cifra_ancla": "€480 x 6 meses"},

    {"key": "emp_erasmus", "audiencia": "estudiantes", "categoria": "educacion",
     "titulo": "Erasmus 2026: hasta €650/mes + matrícula pagada",
     "hook": "Grado/máster, países A/B/C, complemento zona euro",
     "cifra_ancla": "€350-€650/mes"},

    {"key": "emp_capital_beca", "audiencia": "estudiantes", "categoria": "educacion",
     "titulo": "Beca MEC 2026: €6.000 estudios universidad renta baja",
     "hook": "Umbral renta familiar, notas mínimas, plazos",
     "cifra_ancla": "hasta €6.000/curso"},

    # ─── VEHÍCULOS ───
    {"key": "veh_moves", "audiencia": "particulares", "categoria": "movilidad",
     "titulo": "Plan MOVES III 2026: €7.000 por comprar coche eléctrico",
     "hook": "Achatarramiento €500 extra, particulares y empresas",
     "cifra_ancla": "€4.500-€7.000"},

    {"key": "veh_placas_solares", "audiencia": "particulares", "categoria": "movilidad",
     "titulo": "Ayudas placas solares 2026: hasta 40% + IBI -50%",
     "hook": "Real Decreto 477/2021 vigente, tiempo tramitación",
     "cifra_ancla": "40% + IBI -50%"},

    # ─── DISCAPACIDAD / DEPENDENCIA ───
    {"key": "disc_pnc", "audiencia": "particulares", "categoria": "discapacidad",
     "titulo": "PNC 2026: €7.905/año pensión no contributiva (nunca trabajó)",
     "hook": "Requisito 65% discapacidad o >65 años sin cotizar",
     "cifra_ancla": "€7.905/año 14 pagas"},

    {"key": "disc_ley_dependencia", "audiencia": "familias", "categoria": "discapacidad",
     "titulo": "Ley dependencia grado 3: €1.100/mes cuidador familiar",
     "hook": "Grados I/II/III, prestación económica vs servicio",
     "cifra_ancla": "€442-€1.100/mes"},

    # ─── MAYORES ───
    {"key": "may_min_vital", "audiencia": "particulares", "categoria": "renta",
     "titulo": "Ingreso Mínimo Vital 2026: €700/mes garantizados",
     "hook": "Rentas insuficientes, hogares con niños, complemento",
     "cifra_ancla": "€600-€2.000/mes"},

    # ─── AGRICULTURA / RURAL ───
    {"key": "rur_jov_agri", "audiencia": "autonomos", "categoria": "empresarial",
     "titulo": "Ayuda joven agricultor 2026: €70.000 primera instalación",
     "hook": "Menores 41, plan empresarial, PAC UE",
     "cifra_ancla": "hasta €70.000"},

    # ─── EMPRENDIMIENTO / EMPRESA ───
    {"key": "emp_enisa", "audiencia": "empresas", "categoria": "empresarial",
     "titulo": "ENISA jóvenes emprendedores 2026: €75.000 préstamo participativo",
     "hook": "Menores 40, startup <2 años, sin garantías",
     "cifra_ancla": "€25k-€75k préstamo"},

    {"key": "emp_ico", "audiencia": "empresas", "categoria": "empresarial",
     "titulo": "Líneas ICO 2026: hasta €12.5M avalados por Estado",
     "hook": "Pymes, autónomos, exportación, comercio",
     "cifra_ancla": "€12.5M aval Estado"},

    # ─── DESEMPLEO / FORMACIÓN ───
    {"key": "sepe_kit", "audiencia": "trabajadores", "categoria": "empleo",
     "titulo": "Cursos gratis SEPE 2026: FP + certificado profesional",
     "hook": "100% subvencionados, becas alimentación, +100 cursos online",
     "cifra_ancla": "gratis + beca €9/día"},

    # ─── SANIDAD ───
    {"key": "san_prot_dental", "audiencia": "particulares", "categoria": "salud",
     "titulo": "Prótesis dentales gratis 2026: colectivos con derecho",
     "hook": "Menores 15, discapacidad, cobertura autonómica CCAA",
     "cifra_ancla": "hasta €600 prótesis"},

    # ─── CULTURA ───
    {"key": "cult_bono", "audiencia": "estudiantes", "categoria": "cultura",
     "titulo": "Bono Cultural Joven 2026: €400 al cumplir 18",
     "hook": "Solo 18 años, ~9 meses vigencia, cine/museos/conciertos",
     "cifra_ancla": "€400 único"},

    # ─── TRANSPORTE ───
    {"key": "trans_bono_joven", "audiencia": "estudiantes", "categoria": "movilidad",
     "titulo": "Transporte gratis 2026: TOP CCAA que mantienen bonos",
     "hook": "Cercanías, autobús urbano, requisitos",
     "cifra_ancla": "€0 abonos frecuentes"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
