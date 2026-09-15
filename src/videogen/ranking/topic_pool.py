"""Pool rankings TopRanking — 86 topics con dataset REAL.

15/09/26: expandido de 8 → 86 topics en 7 batches. 36 World Bank +
50 bundled curated (JSON verificados con fuente + cierre_dato citable).

Con cooldown 90d y 86 topics: ~260 días sin repetir = 8,5 meses de
contenido único diario. Cuando roten, mismos topics con datos actualizados.

Categorías: economía, demografía, salud, educación, empleo, tecnología,
medio ambiente, defensa, turismo, riqueza, deporte, cine, música, cultura,
empresas, internet, videojuegos, geografía, política, arquitectura, ciencia.

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

    # ═══════════════════════════════════════════════════════════
    # BUNDLED DATA CURADA (topics virales que enganchan)
    # ═══════════════════════════════════════════════════════════
    {"key": "billonarios_forbes", "categoria": "riqueza",
     "titulo": "TOP 10 hombres MÁS RICOS del mundo · 2010-2024",
     "dataset_key": "forbes_billionaires_top",
     "fuente": "Forbes Real-Time Billionaires"},
    {"key": "champions_titulos", "categoria": "deporte",
     "titulo": "TOP 10 CLUBES con más Champions · 1990-2024",
     "dataset_key": "champions_winners",
     "fuente": "UEFA Champions League"},
    {"key": "mundiales_ganados", "categoria": "deporte",
     "titulo": "TOP 8 SELECCIONES con más Mundiales · 1930-2022",
     "dataset_key": "worldcup_winners",
     "fuente": "FIFA World Cup"},
    {"key": "peliculas_taquilla", "categoria": "cine",
     "titulo": "TOP 10 PELÍCULAS más taquilleras historia",
     "dataset_key": "highest_grossing_films",
     "fuente": "Box Office Mojo"},
    {"key": "empresas_capitalizacion", "categoria": "empresas",
     "titulo": "TOP 10 EMPRESAS por CAPITALIZACIÓN · 2010-2024",
     "dataset_key": "tech_companies_marketcap",
     "fuente": "Companiesmarketcap.com"},
    {"key": "marcas_valor", "categoria": "empresas",
     "titulo": "TOP 10 MARCAS más VALIOSAS · 2010-2024",
     "dataset_key": "most_valuable_brands",
     "fuente": "Interbrand Best Global Brands"},
    {"key": "medallero_olimpico", "categoria": "deporte",
     "titulo": "TOP 10 PAÍSES medallero olímpico · 1992-2024",
     "dataset_key": "olympic_medals",
     "fuente": "Comité Olímpico Internacional"},
    {"key": "goleadores_champions", "categoria": "deporte",
     "titulo": "TOP 10 GOLEADORES históricos Champions League",
     "dataset_key": "champions_top_scorers",
     "fuente": "UEFA Champions League"},
    {"key": "edificios_mas_altos", "categoria": "arquitectura",
     "titulo": "TOP 10 EDIFICIOS más ALTOS del mundo",
     "dataset_key": "tallest_buildings",
     "fuente": "CTBUH (Skyscraper Center)"},
    {"key": "youtubers_mas_subs", "categoria": "internet",
     "titulo": "TOP 10 CANALES de YouTube con más suscriptores",
     "dataset_key": "most_subscribed_yt",
     "fuente": "Social Blade"},

    # ═══════════════════════════════════════════════════════════
    # BUNDLED DATA CURADA · BATCH 2 (15/09/26)
    # ═══════════════════════════════════════════════════════════
    {"key": "spotify_top_canciones", "categoria": "musica",
     "titulo": "TOP 10 CANCIONES más escuchadas SPOTIFY histórico",
     "dataset_key": "spotify_most_streamed",
     "fuente": "Spotify Charts"},
    {"key": "balon_de_oro_ranking", "categoria": "deporte",
     "titulo": "TOP 10 JUGADORES con más Balones de Oro",
     "dataset_key": "balon_de_oro",
     "fuente": "France Football Ballon d'Or"},
    {"key": "oscar_extranjero_paises", "categoria": "cine",
     "titulo": "TOP 10 PAÍSES con más Óscares mejor película extranjera",
     "dataset_key": "oscar_best_picture_country",
     "fuente": "Academy of Motion Picture Arts and Sciences"},
    {"key": "nobel_paises", "categoria": "ciencia",
     "titulo": "TOP 10 PAÍSES con más PREMIOS NOBEL histórico",
     "dataset_key": "nobel_by_country",
     "fuente": "nobelprize.org"},
    {"key": "videojuegos_vendidos", "categoria": "videojuegos",
     "titulo": "TOP 10 VIDEOJUEGOS más VENDIDOS de la historia",
     "dataset_key": "videogames_bestselling",
     "fuente": "Wikipedia / oficiales devs"},
    {"key": "apps_mas_descargadas", "categoria": "tecnologia",
     "titulo": "TOP 10 APPS más DESCARGADAS · Global 2024",
     "dataset_key": "most_downloaded_apps",
     "fuente": "data.ai / Sensor Tower"},
    {"key": "arsenal_nuclear", "categoria": "defensa",
     "titulo": "TOP 10 PAÍSES con más ARMAS NUCLEARES",
     "dataset_key": "nuclear_arsenal",
     "fuente": "SIPRI Yearbook 2024"},
    {"key": "idiomas_mas_hablados", "categoria": "cultura",
     "titulo": "TOP 10 IDIOMAS más HABLADOS del mundo",
     "dataset_key": "languages_most_spoken",
     "fuente": "Ethnologue 2024"},
    {"key": "paises_mas_turistas", "categoria": "turismo",
     "titulo": "TOP 10 PAÍSES más VISITADOS del mundo · 2019-2023",
     "dataset_key": "tourism_most_visited",
     "fuente": "UN World Tourism Organization (UNWTO)"},
    {"key": "deportistas_mejor_pagados", "categoria": "deporte",
     "titulo": "TOP 10 DEPORTISTAS mejor PAGADOS del mundo",
     "dataset_key": "highest_paid_athletes",
     "fuente": "Forbes 2024 Highest-Paid Athletes"},
    {"key": "religiones_seguidores", "categoria": "cultura",
     "titulo": "TOP 10 RELIGIONES con MÁS seguidores del mundo",
     "dataset_key": "religions_worldwide",
     "fuente": "Pew Research Center"},
    {"key": "rios_mas_largos", "categoria": "geografia",
     "titulo": "TOP 10 RÍOS más LARGOS del mundo",
     "dataset_key": "rivers_longest",
     "fuente": "USGS / National Geographic"},
    {"key": "montanas_mas_altas", "categoria": "geografia",
     "titulo": "TOP 10 MONTAÑAS más ALTAS del mundo",
     "dataset_key": "mountains_highest",
     "fuente": "Nepal Survey / Wikipedia"},
    {"key": "ejercitos_mas_grandes", "categoria": "defensa",
     "titulo": "TOP 10 EJÉRCITOS más grandes del mundo",
     "dataset_key": "military_active",
     "fuente": "IISS Military Balance 2024"},
    {"key": "goleadores_laliga_historicos", "categoria": "deporte",
     "titulo": "TOP 10 GOLEADORES históricos de LA LIGA (España)",
     "dataset_key": "liga_top_scorers",
     "fuente": "LaLiga oficial"},

    # ═══════════════════════════════════════════════════════════
    # BUNDLED DATA CURADA · BATCH 3 (15/09/26)
    # ═══════════════════════════════════════════════════════════
    {"key": "grammy_artistas_top", "categoria": "musica",
     "titulo": "TOP 10 ARTISTAS con más PREMIOS GRAMMY histórico",
     "dataset_key": "grammy_most_awards",
     "fuente": "The Recording Academy (Grammy.com)"},
    {"key": "campeones_f1", "categoria": "deporte",
     "titulo": "TOP 10 CAMPEONES de F1 con más TÍTULOS",
     "dataset_key": "f1_champions",
     "fuente": "FIA / Formula1.com"},
    {"key": "anillos_nba", "categoria": "deporte",
     "titulo": "TOP 10 EQUIPOS con más ANILLOS de la NBA",
     "dataset_key": "nba_finals_winners",
     "fuente": "NBA.com"},
    {"key": "agencias_espaciales", "categoria": "ciencia",
     "titulo": "TOP 10 AGENCIAS ESPACIALES por PRESUPUESTO · 2024",
     "dataset_key": "space_agencies_budget",
     "fuente": "Statista / Space Foundation Report"},
    {"key": "redes_sociales_top", "categoria": "internet",
     "titulo": "TOP 10 REDES SOCIALES con MÁS usuarios · 2024",
     "dataset_key": "social_media_users",
     "fuente": "DataReportal Global Digital Report 2024"},

    # ═══════════════════════════════════════════════════════════
    # BUNDLED DATA CURADA · BATCH 4 (15/09/26) — enfoque España
    # ═══════════════════════════════════════════════════════════
    {"key": "ibex35_top", "categoria": "empresas",
     "titulo": "TOP 10 EMPRESAS IBEX 35 por capitalización · 2024",
     "dataset_key": "ibex35_top",
     "fuente": "Bolsa de Madrid (BME)"},
    {"key": "bancos_espana_top", "categoria": "empresas",
     "titulo": "TOP 10 BANCOS ESPAÑOLES por activos · 2024",
     "dataset_key": "spain_banks_top",
     "fuente": "Banco de España / AEB"},
    {"key": "youtube_videos_top", "categoria": "internet",
     "titulo": "TOP 10 VIDEOS más VISTOS de YouTube histórico",
     "dataset_key": "youtube_most_viewed",
     "fuente": "YouTube / Wikipedia list"},
    {"key": "tenistas_grand_slams", "categoria": "deporte",
     "titulo": "TOP 10 TENISTAS masculinos con más GRAND SLAMS",
     "dataset_key": "tennis_grand_slams",
     "fuente": "ATP / ITF"},
    {"key": "espanoles_mas_ricos", "categoria": "riqueza",
     "titulo": "TOP 10 ESPAÑOLES más RICOS · Forbes 2024",
     "dataset_key": "spain_richest",
     "fuente": "Forbes Real-Time Billionaires 2024"},

    # ═══════════════════════════════════════════════════════════
    # BUNDLED DATA CURADA · BATCH 5 (15/09/26)
    # ═══════════════════════════════════════════════════════════
    {"key": "coches_mas_vendidos", "categoria": "empresas",
     "titulo": "TOP 10 COCHES más VENDIDOS de la historia",
     "dataset_key": "cars_bestselling",
     "fuente": "Toyota / Ford / VW oficiales"},
    {"key": "ciudades_mas_pobladas", "categoria": "demografia",
     "titulo": "TOP 10 CIUDADES más POBLADAS del mundo · 2024",
     "dataset_key": "cities_biggest",
     "fuente": "UN World Urbanization Prospects 2024"},
    {"key": "aeropuertos_mas_transitados", "categoria": "tecnologia",
     "titulo": "TOP 10 AEROPUERTOS más TRANSITADOS del mundo · 2023",
     "dataset_key": "airports_busiest",
     "fuente": "Airports Council International (ACI)"},
    {"key": "lideres_mas_largos", "categoria": "politica",
     "titulo": "TOP 10 LÍDERES políticos con más AÑOS en el poder",
     "dataset_key": "dictators_longest",
     "fuente": "Wikipedia (longest ruling leaders)"},
    {"key": "paises_mas_grandes", "categoria": "geografia",
     "titulo": "TOP 10 PAÍSES más GRANDES del mundo por superficie",
     "dataset_key": "countries_biggest_area",
     "fuente": "CIA World Factbook"},

    # ═══════════════════════════════════════════════════════════
    # BUNDLED DATA CURADA · BATCH 6 (15/09/26)
    # ═══════════════════════════════════════════════════════════
    {"key": "actores_mejor_pagados", "categoria": "cine",
     "titulo": "TOP 10 ACTORES mejor PAGADOS del mundo",
     "dataset_key": "actors_highest_paid",
     "fuente": "Forbes World's Highest-Paid Actors"},
    {"key": "youtubers_espanoles_top", "categoria": "internet",
     "titulo": "TOP 10 YOUTUBERS ESPAÑOLES con más SUSCRIPTORES",
     "dataset_key": "spanish_youtubers",
     "fuente": "Social Blade"},
    {"key": "ligas_futbol_ingresos", "categoria": "deporte",
     "titulo": "TOP 10 LIGAS de FÚTBOL con más INGRESOS · 2023",
     "dataset_key": "leagues_football_revenue",
     "fuente": "Deloitte Football Money League 2024"},
    {"key": "universidades_top", "categoria": "educacion",
     "titulo": "TOP 10 UNIVERSIDADES del mundo · Shanghai Ranking",
     "dataset_key": "universities_top",
     "fuente": "Shanghai Ranking (ARWU)"},
    {"key": "aerolineas_mas_grandes", "categoria": "empresas",
     "titulo": "TOP 10 AEROLÍNEAS más grandes por PASAJEROS · 2023",
     "dataset_key": "airlines_biggest",
     "fuente": "IATA World Air Transport Statistics 2024"},

    # ═══════════════════════════════════════════════════════════
    # BUNDLED DATA CURADA · BATCH 7 (15/09/26)
    # ═══════════════════════════════════════════════════════════
    {"key": "museos_mas_visitados", "categoria": "cultura",
     "titulo": "TOP 10 MUSEOS más VISITADOS del mundo · 2023",
     "dataset_key": "museums_most_visited",
     "fuente": "The Art Newspaper Museum Ranking 2024"},
    {"key": "marcas_lujo_top", "categoria": "empresas",
     "titulo": "TOP 10 MARCAS de LUJO más valiosas · 2024",
     "dataset_key": "luxury_brands",
     "fuente": "Kantar BrandZ 2024"},
    {"key": "videojuegos_jugadores_activos", "categoria": "videojuegos",
     "titulo": "TOP 10 VIDEOJUEGOS con MÁS jugadores activos · 2024",
     "dataset_key": "videogames_active_players",
     "fuente": "Reportes oficiales devs"},
    {"key": "divorcios_mas_caros", "categoria": "riqueza",
     "titulo": "TOP 10 DIVORCIOS más CAROS de la historia",
     "dataset_key": "expensive_divorces",
     "fuente": "Forbes / Business Insider"},
    {"key": "streamers_twitch_top", "categoria": "internet",
     "titulo": "TOP 10 STREAMERS de TWITCH con más SEGUIDORES · 2024",
     "dataset_key": "streamers_twitch",
     "fuente": "Social Blade Twitch"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
