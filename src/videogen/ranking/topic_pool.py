"""Pool rankings evolutivos — todos con fuente pública citable.

Cada topic define un DATASET real (o instrucciones para que Gemini
sepa qué datos generar SIEMPRE verificables).
"""
from __future__ import annotations


TOPICS = [
    {"key": "pib_paises_2000_2026", "audiencia": "general", "categoria": "economia",
     "titulo": "TOP 10 países por PIB · 2000-2026",
     "fuente": "World Bank / IMF",
     "dataset_hint": "PIB nominal en billones USD, países G20 top 10",
     "cifra_ancla": "USD trillion"},

    {"key": "poblacion_paises_evolucion", "audiencia": "general", "categoria": "demografia",
     "titulo": "TOP 10 países más poblados · 1950-2026",
     "fuente": "UN Population Division",
     "dataset_hint": "Población en millones · India superó China 2023",
     "cifra_ancla": "millones habitantes"},

    {"key": "top_marcas_valor_2000_2026", "audiencia": "general", "categoria": "empresas",
     "titulo": "TOP 10 marcas más valiosas del mundo · 2000-2026",
     "fuente": "Interbrand / Kantar BrandZ",
     "dataset_hint": "Apple/Microsoft/Google/Amazon vs Coca-Cola/GM 2000",
     "cifra_ancla": "USD billion brand value"},

    {"key": "ciudades_mas_pobladas_2050", "audiencia": "general", "categoria": "demografia",
     "titulo": "TOP 15 megaciudades del mundo · previsión 2050",
     "fuente": "UN World Urbanization",
     "dataset_hint": "Tokyo, Delhi, Shanghai, Lagos, Mumbai proyecciones",
     "cifra_ancla": "millones habitantes urbanos"},

    {"key": "paises_felices_index", "audiencia": "general", "categoria": "sociedad",
     "titulo": "TOP 15 países más felices · 2015-2026",
     "fuente": "World Happiness Report",
     "dataset_hint": "Finlandia lidera 7 años, España posición 32-36",
     "cifra_ancla": "score 0-10"},

    {"key": "goleadores_champions_historia", "audiencia": "deporte", "categoria": "futbol",
     "titulo": "TOP 20 goleadores Champions League · histórico",
     "fuente": "UEFA official stats",
     "dataset_hint": "Cristiano 140 · Messi 129 · Lewandowski 105",
     "cifra_ancla": "goles Champions"},

    {"key": "actores_taquilla_2000_2026", "audiencia": "general", "categoria": "cine",
     "titulo": "TOP 15 actores más taquilleros · 2000-2026",
     "fuente": "Box Office Mojo",
     "dataset_hint": "Downey Jr, Scarlett Johansson, Samuel L. Jackson",
     "cifra_ancla": "USD billion box office"},

    {"key": "canales_yt_subs_evolucion", "audiencia": "general", "categoria": "internet",
     "titulo": "TOP 10 canales YouTube por subs · 2010-2026",
     "fuente": "SocialBlade histórico",
     "dataset_hint": "T-Series, MrBeast, PewDiePie, Cocomelon, Kids Diana",
     "cifra_ancla": "millones subs"},

    {"key": "ricos_forbes_2000_2026", "audiencia": "general", "categoria": "economia",
     "titulo": "TOP 10 más ricos del mundo · evolución 2000-2026",
     "fuente": "Forbes billionaires list",
     "dataset_hint": "Gates 2000 → Musk 2020 → cambios anuales",
     "cifra_ancla": "USD billion patrimonio"},

    {"key": "coches_mas_vendidos_2026_historia", "audiencia": "motor", "categoria": "consumo",
     "titulo": "TOP 15 coches más vendidos historia mundial",
     "fuente": "Manufacturers reports + JATO",
     "dataset_hint": "Toyota Corolla 50M+ · Ford F-Series · VW Golf/Beetle",
     "cifra_ancla": "millones unidades"},

    {"key": "peliculas_taquilla_historia", "audiencia": "general", "categoria": "cine",
     "titulo": "TOP 20 películas más taquilleras · histórico (inflación)",
     "fuente": "Box Office Mojo adjusted",
     "dataset_hint": "Avatar, Titanic, Star Wars, Avengers ajustado inflación",
     "cifra_ancla": "USD billion taquilla ajustada"},

    {"key": "musicos_ventas_historia", "audiencia": "general", "categoria": "musica",
     "titulo": "TOP 15 artistas musicales más vendidos · 1950-2026",
     "fuente": "IFPI / RIAA certifications",
     "dataset_hint": "Beatles, Elvis, Michael Jackson, Madonna, Rihanna",
     "cifra_ancla": "millones discos certificados"},

    {"key": "medallas_olimpiadas_paises", "audiencia": "deporte", "categoria": "deporte",
     "titulo": "TOP 10 países más medallas olímpicas · 1896-2026",
     "fuente": "COI oficial histórico",
     "dataset_hint": "USA lidera, URSS/Rusia, China ascenso 2000+",
     "cifra_ancla": "medallas totales"},

    {"key": "esperanza_vida_paises_2000_2026", "audiencia": "general", "categoria": "salud",
     "titulo": "TOP 15 países con MAYOR esperanza de vida · 2000-2026",
     "fuente": "OMS / World Bank",
     "dataset_hint": "Japón, Suiza, Singapur, España top 5",
     "cifra_ancla": "años esperanza vida"},

    {"key": "consumo_energia_paises_2000_2026", "audiencia": "general", "categoria": "energia",
     "titulo": "TOP 10 países mayor consumo energético · 2000-2026",
     "fuente": "IEA World Energy Balances",
     "dataset_hint": "China superó USA 2010, India creciendo, EU decrece",
     "cifra_ancla": "TWh consumo total"},

    # ─── ESPAÑA CENTRIC ───
    {"key": "provincias_es_poblacion", "audiencia": "general", "categoria": "españa",
     "titulo": "TOP 15 provincias españolas MÁS pobladas · 1900-2026",
     "fuente": "INE histórico",
     "dataset_hint": "Madrid, Barcelona, Valencia, Sevilla · Soria en declive",
     "cifra_ancla": "habitantes"},

    {"key": "sueldo_medio_ccaa", "audiencia": "general", "categoria": "españa",
     "titulo": "TOP 10 CCAA por sueldo medio · 2010-2026",
     "fuente": "INE Encuesta Estructura Salarial",
     "dataset_hint": "País Vasco, Madrid, Navarra top · Canarias/Extremadura bottom",
     "cifra_ancla": "€ salario medio bruto anual"},

    {"key": "clubes_liga_titulos", "audiencia": "deporte", "categoria": "españa",
     "titulo": "TOP 10 clubes de LaLiga por títulos · histórico",
     "fuente": "RFEF / LaLiga oficial",
     "dataset_hint": "Real Madrid 35 · Barça 27 · Athletic 8 · Atleti 11",
     "cifra_ancla": "títulos LaLiga"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
