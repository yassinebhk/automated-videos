"""Pool de temas LONG-FORM para TopRanking ES — Top-N en cuenta atrás narrada.

Cada tema es un ranking REAL y verificable (fuente + criterio explícitos). El
guion se construye como cuenta atrás del #N al #1 (ver prompts/ranking_system.md).
Interfaz compatible con channel_pipeline._pick_topic: `all_topics()` → list[dict]
con key/audiencia/categoria/titulo/hook/cifra_ancla.
"""
from __future__ import annotations

# categoria = agrupador temático · audiencia se usa para balancear variedad
TOPICS: list[dict] = [
    {"key": "top_futbolistas_pagados", "audiencia": "deporte", "categoria": "dinero",
     "titulo": "TOP 10: los futbolistas mejor pagados del mundo (Forbes 2025)",
     "hook": "el #1 gana más que los puestos 4, 5 y 6 juntos",
     "cifra_ancla": "ingresos anuales en millones de dólares · Forbes 2025"},

    {"key": "top_paises_ricos_pib", "audiencia": "economia", "categoria": "paises",
     "titulo": "TOP 10: los países más ricos del mundo por PIB per cápita",
     "hook": "ninguno de los 3 primeros es de los que la gente imagina",
     "cifra_ancla": "PIB per cápita en dólares · FMI 2025"},

    {"key": "top_peliculas_taquilleras", "audiencia": "cine", "categoria": "cultura",
     "titulo": "TOP 10: las películas más taquilleras de la historia",
     "hook": "el #1 recaudó más de 2.900 millones de dólares",
     "cifra_ancla": "recaudación mundial bruta · Box Office Mojo"},

    {"key": "top_hombres_ricos", "audiencia": "economia", "categoria": "dinero",
     "titulo": "TOP 10: las personas más ricas del planeta (Forbes 2025)",
     "hook": "la fortuna del #1 supera el PIB de países enteros",
     "cifra_ancla": "patrimonio neto en miles de millones · Forbes 2025"},

    {"key": "top_paises_poblados", "audiencia": "mundo", "categoria": "paises",
     "titulo": "TOP 10: los países más poblados del mundo (ONU 2025)",
     "hook": "el #1 y el #2 concentran más de 1 de cada 3 humanos",
     "cifra_ancla": "población total · División de Población de la ONU 2025"},

    {"key": "top_empresas_valiosas", "audiencia": "economia", "categoria": "empresas",
     "titulo": "TOP 10: las empresas más valiosas del mundo por capitalización",
     "hook": "el #1 vale más que la bolsa entera de muchos países",
     "cifra_ancla": "capitalización bursátil en billones de dólares · 2025"},

    {"key": "top_idiomas_hablados", "audiencia": "mundo", "categoria": "cultura",
     "titulo": "TOP 10: los idiomas más hablados del mundo (Ethnologue 2025)",
     "hook": "el español pelea por el pódium... ¿en qué puesto crees?",
     "cifra_ancla": "número total de hablantes · Ethnologue 2025"},

    {"key": "top_ciudades_pobladas", "audiencia": "mundo", "categoria": "paises",
     "titulo": "TOP 10: las ciudades más pobladas del mundo (área metropolitana)",
     "hook": "el #1 tiene más habitantes que toda España",
     "cifra_ancla": "población del área metropolitana · ONU 2025"},

    {"key": "top_paises_visitados", "audiencia": "mundo", "categoria": "paises",
     "titulo": "TOP 10: los países más visitados del mundo (OMT)",
     "hook": "España pelea el pódium mundial de turismo",
     "cifra_ancla": "llegadas de turistas internacionales · OMT"},

    {"key": "top_marcas_valiosas", "audiencia": "economia", "categoria": "empresas",
     "titulo": "TOP 10: las marcas más valiosas del mundo (Interbrand)",
     "hook": "el valor de la marca #1 supera los 500.000 millones",
     "cifra_ancla": "valor de marca en miles de millones · Interbrand 2025"},

    {"key": "top_estadios_grandes", "audiencia": "deporte", "categoria": "deporte",
     "titulo": "TOP 10: los estadios más grandes del mundo por aforo",
     "hook": "el #1 no está donde la mayoría cree",
     "cifra_ancla": "aforo oficial en número de asientos"},

    {"key": "top_animales_rapidos", "audiencia": "curioso", "categoria": "naturaleza",
     "titulo": "TOP 10: los animales más rápidos del planeta",
     "hook": "el #1 supera los 320 km/h en picado",
     "cifra_ancla": "velocidad máxima en km/h"},

    {"key": "top_esperanza_vida", "audiencia": "mundo", "categoria": "paises",
     "titulo": "TOP 10: los países con mayor esperanza de vida (OMS/ONU)",
     "hook": "España está entre los primeros del mundo",
     "cifra_ancla": "esperanza de vida al nacer en años · ONU 2025"},

    {"key": "top_youtubers_subs", "audiencia": "curioso", "categoria": "cultura",
     "titulo": "TOP 10: los canales de YouTube con más suscriptores",
     "hook": "el #1 lleva años imbatible pese a todo",
     "cifra_ancla": "número de suscriptores · datos públicos de YouTube 2025"},

    {"key": "top_selecciones_mundiales", "audiencia": "deporte", "categoria": "deporte",
     "titulo": "TOP 10: las selecciones con más Mundiales de fútbol",
     "hook": "solo 8 países han ganado la Copa del Mundo en la historia",
     "cifra_ancla": "número de Copas del Mundo ganadas · FIFA"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)
