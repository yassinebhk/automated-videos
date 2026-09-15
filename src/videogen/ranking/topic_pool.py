"""Pool rankings TopRanking — 36+ topics con dataset REAL.

15/09/26: expandido de 8 → 36 topics tras user request "más variedad".
Todos con dataset_key apuntando a World Bank cache (fetch semanal).

Con cooldown 90d y 36 topics: ~120 días sin repetir = 4 meses de
contenido único diario. Cuando roten, mismos topics con datos actualizados.

Fuentes 100% verificables + citables. Cero alucinación LLM.
"""
from __future__ import annotations


TOPICS = [
    # ═══════════════════════════════════════════════════════════
    # ECONOMÍA (10)
    # ═══════════════════════════════════════════════════════════
    {"key": "pib_paises", "categoria": "economia",
     "titulo": "TOP 10 países por PIB · 2000-2024",
     "dataset_key": "wb_NY_GDP_MKTP_CD_2000_2024",
     "fuente": "World Bank Open Data"},
    {"key": "pib_percapita", "categoria": "economia",
     "titulo": "TOP 10 países más ricos per cápita · 1990-2024",
     "dataset_key": "wb_NY_GDP_PCAP_CD_1990_2024",
     "fuente": "World Bank Open Data"},
    {"key": "exportaciones", "categoria": "economia",
     "titulo": "TOP 10 países exportadores · 2000-2024",
     "dataset_key": "wb_NE_EXP_GNFS_CD_2000_2024",
     "fuente": "World Bank Open Data"},
    {"key": "importaciones", "categoria": "economia",
     "titulo": "TOP 10 países importadores · 2000-2024",
     "dataset_key": "wb_NE_IMP_GNFS_CD_2000_2024",
     "fuente": "World Bank Open Data"},
    {"key": "ied_entrante", "categoria": "economia",
     "titulo": "TOP 10 países por inversión extranjera · 2000-2024",
     "dataset_key": "wb_BX_KLT_DINV_CD_WD_2000_2024",
     "fuente": "World Bank Open Data"},
    {"key": "deuda_publica", "categoria": "economia",
     "titulo": "TOP 10 países más endeudados %PIB · 2000-2024",
     "dataset_key": "wb_GC_DOD_TOTL_GD_ZS_2000_2024",
     "fuente": "World Bank / IMF"},
    {"key": "inflacion", "categoria": "economia",
     "titulo": "TOP 10 países con MÁS inflación · 2000-2024",
     "dataset_key": "wb_FP_CPI_TOTL_ZG_2000_2024",
     "fuente": "World Bank Open Data"},
    {"key": "industria_pib", "categoria": "economia",
     "titulo": "TOP 10 países más INDUSTRIALES %PIB · 2000-2024",
     "dataset_key": "wb_NV_IND_TOTL_ZS_2000_2024",
     "fuente": "World Bank Open Data"},
    {"key": "agricultura_pib", "categoria": "economia",
     "titulo": "TOP 10 países más AGRÍCOLAS %PIB · 2000-2024",
     "dataset_key": "wb_NV_AGR_TOTL_ZS_2000_2024",
     "fuente": "World Bank Open Data"},
    {"key": "servicios_pib", "categoria": "economia",
     "titulo": "TOP 10 países más SERVICIOS %PIB · 2000-2024",
     "dataset_key": "wb_NV_SRV_TOTL_ZS_2000_2024",
     "fuente": "World Bank Open Data"},

    # ═══════════════════════════════════════════════════════════
    # DEMOGRAFÍA (6)
    # ═══════════════════════════════════════════════════════════
    {"key": "poblacion_paises", "categoria": "demografia",
     "titulo": "TOP 10 países más poblados · 1970-2024",
     "dataset_key": "wb_SP_POP_TOTL_1970_2024",
     "fuente": "World Bank / UN"},
    {"key": "poblacion_urbana", "categoria": "demografia",
     "titulo": "TOP 10 países más URBANIZADOS · 1990-2024",
     "dataset_key": "wb_SP_URB_TOTL_IN_ZS_1990_2024",
     "fuente": "World Bank / UN Habitat"},
    {"key": "crecimiento_poblacion", "categoria": "demografia",
     "titulo": "TOP 10 países que MÁS crecen en habitantes · 1970-2024",
     "dataset_key": "wb_SP_POP_GROW_1970_2024",
     "fuente": "World Bank / UN"},
    {"key": "fertilidad", "categoria": "demografia",
     "titulo": "TOP 10 países con MÁS hijos por mujer · 1970-2023",
     "dataset_key": "wb_SP_DYN_TFRT_IN_1970_2023",
     "fuente": "World Bank"},
    {"key": "envejecimiento", "categoria": "demografia",
     "titulo": "TOP 10 países MÁS envejecidos (%>65) · 1970-2024",
     "dataset_key": "wb_SP_POP_65UP_TO_ZS_1970_2024",
     "fuente": "World Bank"},
    {"key": "poblacion_joven", "categoria": "demografia",
     "titulo": "TOP 10 países MÁS jóvenes (%<14) · 1970-2024",
     "dataset_key": "wb_SP_POP_0014_TO_ZS_1970_2024",
     "fuente": "World Bank"},

    # ═══════════════════════════════════════════════════════════
    # SALUD (4)
    # ═══════════════════════════════════════════════════════════
    {"key": "esperanza_vida", "categoria": "salud",
     "titulo": "TOP 10 países con MÁS esperanza de vida · 1970-2023",
     "dataset_key": "wb_SP_DYN_LE00_IN_1970_2023",
     "fuente": "World Bank / WHO"},
    {"key": "mortalidad_infantil", "categoria": "salud",
     "titulo": "TOP 10 países con MÁS mortalidad infantil · 1990-2023",
     "dataset_key": "wb_SH_DYN_MORT_1990_2023",
     "fuente": "World Bank / UNICEF"},
    {"key": "obesidad_hombres", "categoria": "salud",
     "titulo": "TOP 10 países con MÁS obesidad masculina · 2000-2022",
     "dataset_key": "wb_SH_STA_OBAS_MA_ZS_2000_2022",
     "fuente": "World Bank / WHO"},
    {"key": "medicos_por_habitante", "categoria": "salud",
     "titulo": "TOP 10 países con MÁS médicos por habitante · 2000-2022",
     "dataset_key": "wb_SH_MED_PHYS_ZS_2000_2022",
     "fuente": "World Bank / WHO"},

    # ═══════════════════════════════════════════════════════════
    # EDUCACIÓN (2)
    # ═══════════════════════════════════════════════════════════
    {"key": "gasto_educacion", "categoria": "educacion",
     "titulo": "TOP 10 países que MÁS gastan en educación · 2000-2023",
     "dataset_key": "wb_SE_XPD_TOTL_GD_ZS_2000_2023",
     "fuente": "World Bank / UNESCO"},
    {"key": "alfabetizacion", "categoria": "educacion",
     "titulo": "TOP 10 países con MÁS alfabetización adulta · 2000-2023",
     "dataset_key": "wb_SE_ADT_LITR_ZS_2000_2023",
     "fuente": "World Bank / UNESCO"},

    # ═══════════════════════════════════════════════════════════
    # EMPLEO (2)
    # ═══════════════════════════════════════════════════════════
    {"key": "desempleo", "categoria": "empleo",
     "titulo": "TOP 10 países con MÁS paro · 2000-2024",
     "dataset_key": "wb_SL_UEM_TOTL_ZS_2000_2024",
     "fuente": "World Bank / ILO"},
    {"key": "desempleo_juvenil", "categoria": "empleo",
     "titulo": "TOP 10 países con MÁS paro juvenil (15-24) · 2000-2024",
     "dataset_key": "wb_SL_UEM_1524_ZS_2000_2024",
     "fuente": "World Bank / ILO"},

    # ═══════════════════════════════════════════════════════════
    # TECNOLOGÍA / INFRAESTRUCTURA (4)
    # ═══════════════════════════════════════════════════════════
    {"key": "internet_users", "categoria": "tecnologia",
     "titulo": "TOP 10 países más conectados a Internet · 2000-2023",
     "dataset_key": "wb_IT_NET_USER_ZS_2000_2023",
     "fuente": "World Bank / ITU"},
    {"key": "moviles_habitante", "categoria": "tecnologia",
     "titulo": "TOP 10 países con MÁS móviles por habitante · 2000-2023",
     "dataset_key": "wb_IT_CEL_SETS_P2_2000_2023",
     "fuente": "World Bank / ITU"},
    {"key": "consumo_electrico", "categoria": "tecnologia",
     "titulo": "TOP 10 países con MÁS consumo eléctrico per cápita · 1990-2022",
     "dataset_key": "wb_EG_USE_ELEC_KH_PC_1990_2022",
     "fuente": "World Bank / IEA"},
    {"key": "pasajeros_aereos", "categoria": "tecnologia",
     "titulo": "TOP 10 países con MÁS pasajeros aéreos · 2000-2023",
     "dataset_key": "wb_IS_AIR_PSGR_2000_2023",
     "fuente": "World Bank / ICAO"},

    # ═══════════════════════════════════════════════════════════
    # MEDIO AMBIENTE (4)
    # ═══════════════════════════════════════════════════════════
    {"key": "co2_percapita", "categoria": "medio_ambiente",
     "titulo": "TOP 10 países más CONTAMINANTES per cápita · 1990-2022",
     "dataset_key": "wb_EN_ATM_CO2E_PC_1990_2022",
     "fuente": "World Bank / EDGAR"},
    {"key": "co2_total", "categoria": "medio_ambiente",
     "titulo": "TOP 10 países con MÁS emisiones CO2 totales · 1990-2022",
     "dataset_key": "wb_EN_ATM_CO2E_KT_1990_2022",
     "fuente": "World Bank / EDGAR"},
    {"key": "renovables", "categoria": "medio_ambiente",
     "titulo": "TOP 10 países con MÁS energías renovables · 2000-2022",
     "dataset_key": "wb_EG_FEC_RNEW_ZS_2000_2022",
     "fuente": "World Bank / IEA"},
    {"key": "bosques", "categoria": "medio_ambiente",
     "titulo": "TOP 10 países con MÁS bosques (% superficie) · 1990-2022",
     "dataset_key": "wb_AG_LND_FRST_ZS_1990_2022",
     "fuente": "World Bank / FAO"},

    # ═══════════════════════════════════════════════════════════
    # DEFENSA (2)
    # ═══════════════════════════════════════════════════════════
    {"key": "gasto_militar_total", "categoria": "defensa",
     "titulo": "TOP 10 países por gasto militar · 2000-2024",
     "dataset_key": "wb_MS_MIL_XPND_CD_2000_2024",
     "fuente": "World Bank / SIPRI"},
    {"key": "gasto_militar_pib", "categoria": "defensa",
     "titulo": "TOP 10 países que MÁS gastan en defensa %PIB · 2000-2024",
     "dataset_key": "wb_MS_MIL_XPND_GD_ZS_2000_2024",
     "fuente": "World Bank / SIPRI"},

    # ═══════════════════════════════════════════════════════════
    # TURISMO (2)
    # ═══════════════════════════════════════════════════════════
    {"key": "ingresos_turismo", "categoria": "turismo",
     "titulo": "TOP 10 países con MÁS ingresos por turismo · 2000-2023",
     "dataset_key": "wb_ST_INT_RCPT_CD_2000_2023",
     "fuente": "World Bank / UNWTO"},
    {"key": "turistas_llegados", "categoria": "turismo",
     "titulo": "TOP 10 países con MÁS turistas internacionales · 2000-2023",
     "dataset_key": "wb_ST_INT_ARVL_2000_2023",
     "fuente": "World Bank / UNWTO"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
