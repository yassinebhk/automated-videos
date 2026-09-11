"""Pool POV histórico ES — semillas verificables (personajes/eventos reales).
Cada POV está basado en HECHO histórico documentado. Cero ficción pura."""
from __future__ import annotations


TOPICS = [
    # ─── SIGLO XX ESPAÑA ───
    {"key": "pov_gc_1936_madrid", "audiencia": "general", "categoria": "sxx",
     "titulo": "POV: eres madrileño el 18 julio 1936 · empieza la Guerra Civil",
     "hook": "Radio Unión anuncia sublevación · calles vacías al mediodía",
     "cifra_ancla": "18 julio 1936", "personaje": "civil madrileño",
     "epoca": "Madrid 1936"},

    {"key": "pov_transicion_23f", "audiencia": "general", "categoria": "sxx",
     "titulo": "POV: eres diputado en el Congreso el 23-F 1981 · Tejero entra",
     "hook": "Ruido tacones · gritos ¡al suelo! · disparos al techo",
     "cifra_ancla": "23 febrero 1981 18:23h", "personaje": "diputado",
     "epoca": "Congreso España 1981"},

    {"key": "pov_bombardeo_guernica", "audiencia": "general", "categoria": "sxx",
     "titulo": "POV: vecino de Guernica el 26 abril 1937 · bombas alemanas",
     "hook": "Aviación Cóndor · 3h bombardeo día mercado · 26 abril",
     "cifra_ancla": "26 abril 1937", "personaje": "vecino Guernica",
     "epoca": "Guernica 1937"},

    # ─── SIGLO XIX ESPAÑA ───
    {"key": "pov_trafalgar_1805", "audiencia": "general", "categoria": "sxix",
     "titulo": "POV: eres marinero español en Trafalgar · 21 octubre 1805",
     "hook": "Cabo Trafalgar amanece · flota franco-española 33 navíos vs 27 británicos",
     "cifra_ancla": "21 oct 1805", "personaje": "marinero armada española",
     "epoca": "Trafalgar 1805 buque"},

    {"key": "pov_dos_mayo_1808", "audiencia": "general", "categoria": "sxix",
     "titulo": "POV: eres madrileño el 2 mayo 1808 · el pueblo se levanta",
     "hook": "Puerta del Sol · tropas napoleónicas · Palafox · fusilamientos",
     "cifra_ancla": "2 mayo 1808", "personaje": "madrileño Puerta del Sol",
     "epoca": "Madrid 1808 levantamiento"},

    # ─── EDAD MODERNA ───
    {"key": "pov_conquista_tenochtitlan", "audiencia": "general", "categoria": "moderna",
     "titulo": "POV: acompañas a Cortés en Tenochtitlan · noviembre 1519",
     "hook": "Ver por primera vez la capital azteca · 200k habitantes · pirámides",
     "cifra_ancla": "8 nov 1519", "personaje": "soldado español Cortés",
     "epoca": "Tenochtitlan 1519 lago"},

    {"key": "pov_lepanto_1571", "audiencia": "general", "categoria": "moderna",
     "titulo": "POV: eres galeote en Lepanto · 7 octubre 1571 · Cervantes también",
     "hook": "Golfo Corinto amanece · 208 galeras cristianas vs 251 otomanas",
     "cifra_ancla": "7 oct 1571", "personaje": "soldado Marquesa",
     "epoca": "Lepanto 1571 galera"},

    {"key": "pov_armada_invencible", "audiencia": "general", "categoria": "moderna",
     "titulo": "POV: capitán de la Armada Invencible · agosto 1588 canal",
     "hook": "130 barcos rumbo Inglaterra · tormenta noche · brulotes ingleses",
     "cifra_ancla": "agosto 1588", "personaje": "capitán armada española",
     "epoca": "Canal Mancha 1588 galeón"},

    # ─── EDAD MEDIA ES ───
    {"key": "pov_peste_1348_barcelona", "audiencia": "general", "categoria": "medieval",
     "titulo": "POV: médico en Barcelona durante la peste negra · abril 1348",
     "hook": "Puerto contagio · 40% población muere · barbero-cirujano",
     "cifra_ancla": "abril 1348 · -40% población", "personaje": "físico medieval",
     "epoca": "Barcelona medieval 1348 hospital"},

    {"key": "pov_1492_granada", "audiencia": "general", "categoria": "medieval",
     "titulo": "POV: soldado castellano entrando en Granada · 2 enero 1492",
     "hook": "Alhambra entrega llaves · Boabdil sale · fin Reconquista",
     "cifra_ancla": "2 enero 1492", "personaje": "soldado Reyes Católicos",
     "epoca": "Granada 1492 Alhambra"},

    # ─── SIGLO XX GLOBAL ───
    {"key": "pov_titanic_1912", "audiencia": "general", "categoria": "sxx",
     "titulo": "POV: pasajero 3ª clase Titanic · noche 14 abril 1912",
     "hook": "Iceberg 23:40 · botes primero mujeres · agua -2ºC",
     "cifra_ancla": "14 abril 1912 23:40h", "personaje": "pasajero 3ª clase",
     "epoca": "Titanic cubierta 1912 noche"},

    {"key": "pov_pompeya_79", "audiencia": "general", "categoria": "antigua",
     "titulo": "POV: comerciante en Pompeya · 24 agosto año 79 · erupción",
     "hook": "Vesubio erupta 13:00 · cenizas 3m altura · 16 horas destrucción",
     "cifra_ancla": "24 ago 79 · 4-6h muerte", "personaje": "comerciante romano",
     "epoca": "Pompeya 79 dC foro"},

    {"key": "pov_hiroshima_1945", "audiencia": "general", "categoria": "sxx",
     "titulo": "POV: superviviente en Hiroshima · 6 agosto 1945 · 8:15h",
     "hook": "Bomba atómica · destello · 70k muertos instantes",
     "cifra_ancla": "6 ago 1945 8:15", "personaje": "civil japonés",
     "epoca": "Hiroshima 1945 antes bomba"},

    {"key": "pov_muro_berlin_1989", "audiencia": "general", "categoria": "sxx",
     "titulo": "POV: berlinés oriental cruzando el Muro · 9 noviembre 1989",
     "hook": "Rueda prensa 18:57 · 'ab sofort' · multitudes cruzan checkpoint",
     "cifra_ancla": "9 nov 1989", "personaje": "berlinés oriental",
     "epoca": "Berlín Este 1989 muro"},

    # ─── ANTIGÜEDAD ───
    {"key": "pov_hispania_romana", "audiencia": "general", "categoria": "antigua",
     "titulo": "POV: legionario romano en Hispania · Numancia 133 aC",
     "hook": "Sitio Escipión 15 meses · rendición · fin numantinos",
     "cifra_ancla": "133 aC · 15 meses sitio", "personaje": "legionario romano",
     "epoca": "Numancia 133aC campamento"},

    {"key": "pov_atapuerca_hunter", "audiencia": "general", "categoria": "prehistoria",
     "titulo": "POV: cazador Homo antecessor en Atapuerca · hace 850.000 años",
     "hook": "Sierra Atapuerca Burgos · caza ciervos · fuego dominado",
     "cifra_ancla": "850.000 años · +1.6m altura", "personaje": "Homo antecessor",
     "epoca": "Atapuerca prehistoria cazador"},

    # ─── ARTISTAS ES ───
    {"key": "pov_dali_1927", "audiencia": "general", "categoria": "sxx",
     "titulo": "POV: joven Dalí en Residencia de Estudiantes · Madrid 1927",
     "hook": "Buñuel, Lorca, Alberti · Generación 27 · vanguardia surrealista",
     "cifra_ancla": "1927 · 22 años", "personaje": "Salvador Dalí joven",
     "epoca": "Residencia Estudiantes 1927"},

    {"key": "pov_goya_2mayo", "audiencia": "general", "categoria": "sxix",
     "titulo": "POV: eres Goya pintando 'Los fusilamientos' · 1814",
     "hook": "6 años después evento · pintura política · linterna centro",
     "cifra_ancla": "1814 · óleo 268×347cm", "personaje": "Francisco de Goya",
     "epoca": "Madrid estudio Goya 1814"},

    # ─── EVENTOS RECIENTES ES ───
    {"key": "pov_11m_2004", "audiencia": "general", "categoria": "sxxi",
     "titulo": "POV: usuario cercanías Atocha · 7:39h · 11 marzo 2004",
     "hook": "10 explosiones 3 estaciones · 193 muertos · atentados yihadistas",
     "cifra_ancla": "11 mar 2004 7:39h", "personaje": "usuario Cercanías",
     "epoca": "Atocha 2004 andén"},

    # ─── CULTURA GENERAL ES ───
    {"key": "pov_camino_santiago_1180", "audiencia": "general", "categoria": "medieval",
     "titulo": "POV: peregrino francés hacia Santiago · año 1180",
     "hook": "5 semanas caminando · Roncesvalles · albergues Cluny",
     "cifra_ancla": "5 semanas · 800 km", "personaje": "peregrino medieval",
     "epoca": "Camino Santiago medieval 1180"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
