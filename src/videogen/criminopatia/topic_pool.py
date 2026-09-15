"""Pool Criminopatía ES — casos forenses/criminológicos RESUELTOS (sentencia firme).
Formato lista Top N. Foco en el método (ADN, huella, perfil, pericia), no en el morbo.
Schema compatible con topic_refresher. Cooldown 90d.
"""
from __future__ import annotations


TOPICS = [
    {"key": "forense_resueltos", "audiencia": "general", "categoria": "forense",
     "titulo": "5 crímenes resueltos por la ciencia forense",
     "hook": "Un solo pelo bastó para condenarlo",
     "cifra_ancla": "casos con sentencia firme"},
    {"key": "detalle_delato", "audiencia": "general", "categoria": "casos",
     "titulo": "5 asesinos a los que un pequeño detalle delató",
     "hook": "Cometieron el error más tonto posible",
     "cifra_ancla": "detalle clave probado"},
    {"key": "adn_decadas", "audiencia": "general", "categoria": "forense",
     "titulo": "5 crímenes resueltos DÉCADAS después por ADN",
     "hook": "Creían haberse librado. 30 años después, no",
     "cifra_ancla": "resueltos con ADN"},
    {"key": "cambio_investigacion", "audiencia": "general", "categoria": "criminologia",
     "titulo": "5 casos que cambiaron la investigación criminal para siempre",
     "hook": "Sin ellos, la ciencia forense sería otra",
     "cifra_ancla": "hito forense"},
    {"key": "psicologia_atrapo", "audiencia": "general", "categoria": "psicologia",
     "titulo": "5 casos donde el perfil criminal atrapó al culpable",
     "hook": "Lo describieron sin haberlo visto nunca",
     "cifra_ancla": "perfil validado en juicio"},
    {"key": "errores_asesinos", "audiencia": "general", "categoria": "casos",
     "titulo": "5 errores que delataron a asesinos",
     "hook": "El crimen perfecto no existe por esto",
     "cifra_ancla": "error probado en juicio"},
    {"key": "juicios_famosos", "audiencia": "general", "categoria": "juicios",
     "titulo": "5 juicios que marcaron la historia (y su veredicto)",
     "hook": "El veredicto que nadie esperaba",
     "cifra_ancla": "sentencia + tribunal"},
    {"key": "pruebas_condenaron", "audiencia": "general", "categoria": "forense",
     "titulo": "5 pruebas forenses que sentenciaron a un asesino",
     "hook": "La prueba que no pudo negar",
     "cifra_ancla": "prueba pericial"},
    {"key": "huellas", "audiencia": "general", "categoria": "forense",
     "titulo": "5 crímenes resueltos por una sola huella",
     "hook": "Una huella entre millones lo cazó",
     "cifra_ancla": "huella dactilar"},
    {"key": "entomologia_forense", "audiencia": "general", "categoria": "forense",
     "titulo": "5 casos resueltos por insectos (entomología forense)",
     "hook": "Los insectos delataron la hora de la muerte",
     "cifra_ancla": "entomología forense"},
    {"key": "rastro_digital", "audiencia": "general", "categoria": "criminologia",
     "titulo": "5 asesinos cazados por su móvil o rastro digital",
     "hook": "Su propio teléfono los condenó",
     "cifra_ancla": "prueba digital"},
    {"key": "coartadas_falsas", "audiencia": "general", "categoria": "casos",
     "titulo": "5 coartadas 'perfectas' que se derrumbaron",
     "hook": "Parecían intocables hasta que...",
     "cifra_ancla": "coartada desmontada"},
    {"key": "peritos_clave", "audiencia": "general", "categoria": "forense",
     "titulo": "5 veces que un perito resolvió el caso",
     "hook": "El experto que vio lo que nadie vio",
     "cifra_ancla": "peritaje decisivo"},
    {"key": "tecnologia_criminologia", "audiencia": "general", "categoria": "criminologia",
     "titulo": "5 tecnologías que revolucionaron la criminología",
     "hook": "Antes de esto, se libraban",
     "cifra_ancla": "avance técnico"},
    {"key": "casos_espana", "audiencia": "general", "categoria": "casos",
     "titulo": "5 casos españoles resueltos contra todo pronóstico",
     "hook": "En España también hay ciencia forense de récord",
     "cifra_ancla": "sentencia firme (España)"},
    {"key": "confesiones_clave", "audiencia": "general", "categoria": "juicios",
     "titulo": "5 confesiones que resolvieron casos abiertos",
     "hook": "Hablaron cuando ya no había vuelta atrás",
     "cifra_ancla": "confesión + condena"},
    {"key": "ciencia_de_crimenes", "audiencia": "general", "categoria": "criminologia",
     "titulo": "5 avances científicos que nacieron de crímenes reales",
     "hook": "La ciencia forense les debe todo a estos casos",
     "cifra_ancla": "avance documentado"},
    {"key": "toxicologia", "audiencia": "general", "categoria": "forense",
     "titulo": "5 envenenadores atrapados por la toxicología",
     "hook": "Creían que el veneno no deja rastro",
     "cifra_ancla": "análisis toxicológico"},
    {"key": "balistica", "audiencia": "general", "categoria": "forense",
     "titulo": "5 casos resueltos por balística forense",
     "hook": "La bala habla más que cualquier testigo",
     "cifra_ancla": "peritaje balístico"},
    {"key": "moviles_increibles", "audiencia": "general", "categoria": "psicologia",
     "titulo": "5 móviles de crimen más increíbles (casos reales)",
     "hook": "Mataron por el motivo más absurdo",
     "cifra_ancla": "móvil probado en juicio"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
