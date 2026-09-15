"""Pool rankings TopRanking — SOLO topics con dataset REAL bundled.

15/09/26: reescrito tras confirmar que Gemini alucinaba cifras (user
reportó Cristiano rank 9 en 2024 = falso). Ahora cada topic tiene
`dataset_key` apuntando a un JSON cacheado en output/ranking_datasets/
(refrescado semanal via ranking-datasets-refresh cron).

Los datasets vienen de:
  - World Bank Open Data (100% oficial, gratis, sin key)
  - Wikipedia scrapes (para rankings puntuales)
  - Datasets futuros: UEFA, FIFA, Forbes, etc.

Si un topic NO tiene dataset_key o el cache está caducado, el pipeline
usa Gemini como último recurso PERO marca el video como "estimación
aproximada" para no violar veracidad.
"""
from __future__ import annotations


TOPICS = [
    # ─── World Bank — economía y sociedad ───
    {
        "key": "pib_paises_2000_2024",
        "audiencia": "general", "categoria": "economia",
        "titulo": "TOP 10 países por PIB · 2000-2024",
        "dataset_key": "wb_NY_GDP_MKTP_CD_2000_2024",
        "fuente": "World Bank Open Data",
        "cifra_ancla": "billones USD",
    },
    {
        "key": "poblacion_paises_1970_2024",
        "audiencia": "general", "categoria": "demografia",
        "titulo": "TOP 10 países más poblados · 1970-2024",
        "dataset_key": "wb_SP_POP_TOTL_1970_2024",
        "fuente": "World Bank Open Data",
        "cifra_ancla": "millones habitantes",
    },
    {
        "key": "esperanza_vida_paises_1970_2023",
        "audiencia": "general", "categoria": "salud",
        "titulo": "TOP 10 países por esperanza de vida · 1970-2023",
        "dataset_key": "wb_SP_DYN_LE00_IN_1970_2023",
        "fuente": "World Bank Open Data",
        "cifra_ancla": "años",
    },
    {
        "key": "pib_percapita_paises_1990_2024",
        "audiencia": "general", "categoria": "economia",
        "titulo": "TOP 10 países más ricos per cápita · 1990-2024",
        "dataset_key": "wb_NY_GDP_PCAP_CD_1990_2024",
        "fuente": "World Bank Open Data",
        "cifra_ancla": "USD per cápita",
    },
    {
        "key": "desempleo_paises_2000_2024",
        "audiencia": "general", "categoria": "economia",
        "titulo": "TOP 10 países con MÁS paro · 2000-2024",
        "dataset_key": "wb_SL_UEM_TOTL_ZS_2000_2024",
        "fuente": "World Bank Open Data (ILO)",
        "cifra_ancla": "% desempleo",
    },
    {
        "key": "internet_users_paises_2000_2023",
        "audiencia": "general", "categoria": "tecnologia",
        "titulo": "TOP 10 países por uso de Internet · 2000-2023",
        "dataset_key": "wb_IT_NET_USER_ZS_2000_2023",
        "fuente": "World Bank / ITU",
        "cifra_ancla": "% población con Internet",
    },
    {
        "key": "co2_emisiones_paises_1990_2022",
        "audiencia": "general", "categoria": "medio_ambiente",
        "titulo": "TOP 10 países emisores CO2 per cápita · 1990-2022",
        "dataset_key": "wb_EN_ATM_CO2E_PC_1990_2022",
        "fuente": "World Bank / EDGAR",
        "cifra_ancla": "toneladas CO2 per cápita",
    },
    {
        "key": "gasto_militar_paises_2000_2024",
        "audiencia": "general", "categoria": "defensa",
        "titulo": "TOP 10 países por gasto militar · 2000-2024",
        "dataset_key": "wb_MS_MIL_XPND_CD_2000_2024",
        "fuente": "World Bank / SIPRI",
        "cifra_ancla": "billones USD",
    },
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
