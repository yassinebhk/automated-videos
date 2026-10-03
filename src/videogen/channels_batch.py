"""Catálogo de la tanda 02/10 — canales narrados nuevos (pre-cableados) sobre
`simple_channel`. Cada uno = 1 SimpleChannelConfig + su system prompt en prompts/.

Elegidos tras deep-research (3 estudios): encajan con faceless + coste cero +
veracidad + no-YMYL, y la purga de AI-slop premia la fuente citada. Todos ES salvo
nota (ES = menos competencia + infra propia). Geo-quiz (EN) va aparte (generador
propio). Ver [[stoic-mind-nuevo-canal]].
"""
from __future__ import annotations

from .simple_channel import SimpleChannelConfig

_SRC = "— cita SIEMPRE una fuente real y verificable en pantalla (el hecho concreto)."

# ───────────────────────── 1) Enigmas / misterios documentados (ES) ─────────────────────────
# Dedup DURO vs WaitWhy: NADA de crimen. Solo historia/arqueología/exploración/ciencia
# sin resolver, documentada. [[waitwhy-contaminacion-fallback-yt]]
MISTERIOS = SimpleChannelConfig(
    slug="misterios", prefix="YT_MISTERIOS", display_name="Enigmas sin Resolver",
    platform_key="youtube_misterios", lang="es", system_prompt_file="batch_es_system.md",
    tone="suspense documental, sobrio e intrigante; nunca sensacionalista ni pseudociencia",
    category_id="27", emoji="🗿", cross_teaser="🗿 Enigma sin resolver",
    theme_desc=("A Spanish faceless channel about REAL, documented unsolved mysteries of "
                "history, archaeology and exploration (NOT crime): lost cities, ancient "
                "artifacts, unexplained-but-sourced events, disappearances of expeditions."),
    veracity_rules=("- Only REAL documented cases with a citable source. NEVER invent details, "
                    "dates or 'facts'. If a popular theory is debunked, say so. No crime cases."),
    seed=[
        {"key": "antikythera", "titulo": "El mecanismo de Anticitera: un ordenador de hace 2000 años",
         "hook": "En un naufragio griego encontraron un engranaje imposible para su época.",
         "angle": "El mecanismo de Anticitera (~150-100 a.C.), calculaba posiciones astronómicas; fuente: Museo Arqueológico Nacional de Atenas / estudios Nature.",
         "visual": "engranajes de bronce corroídos, mar egeo, museo oscuro"},
        {"key": "gobekli_tepe", "titulo": "Göbekli Tepe: el templo que reescribió la historia",
         "hook": "Es 6000 años más antiguo que Stonehenge y no debería existir.",
         "angle": "Göbekli Tepe (~9600 a.C.) desafía la idea de que la agricultura precede a los templos; fuente: Instituto Arqueológico Alemán (DAI).",
         "visual": "pilares de piedra en T, excavación, atardecer en Anatolia"},
        {"key": "nazca", "titulo": "Las líneas de Nazca: ¿para quién se dibujaron?",
         "hook": "Solo se ven completas desde el cielo. Y nadie podía volar.",
         "angle": "Geoglifos de Nazca (~500 a.C.-500 d.C.), función aún debatida (agua/astronomía/ritual); fuente: UNESCO / líneas y geoglifos de Nazca.",
         "visual": "desierto peruano, geoglifo del colibrí, vista aérea"},
        {"key": "voynich", "titulo": "El manuscrito Voynich: el libro que nadie sabe leer",
         "hook": "600 años y ni los mejores criptógrafos lo han descifrado.",
         "angle": "Manuscrito Voynich (datado ~s.XV por carbono-14), idioma/sistema sin descifrar; fuente: Biblioteca Beinecke, Universidad de Yale.",
         "visual": "páginas de pergamino con escritura extraña, plantas dibujadas, biblioteca antigua"},
        {"key": "tunguska", "titulo": "Tunguska: la explosión que arrasó un bosque sin cráter",
         "hook": "En 1908 algo tumbó 80 millones de árboles. No dejó cráter.",
         "angle": "Evento de Tunguska (1908), probable explosión de un bólido en el aire; fuente: NASA / estudios sobre el evento.",
         "visual": "bosque siberiano derribado radialmente, cielo rojo, taiga"},
        {"key": "wow_signal", "titulo": "La señal Wow!: 72 segundos desde el espacio",
         "hook": "Un radiotelescopio captó una señal tan fuerte que el astrónomo escribió 'Wow!'.",
         "angle": "Señal Wow! (1977, telescopio Big Ear), origen aún no confirmado ni repetido; fuente: Universidad Estatal de Ohio / SETI.",
         "visual": "radiotelescopio nocturno, impresión con '6EQUJ5', cielo estrellado"},
        {"key": "mary_celeste", "titulo": "Mary Celeste: el barco hallado intacto y sin tripulación",
         "hook": "Comida en la mesa, carga intacta, y ni un alma a bordo.",
         "angle": "Mary Celeste (1872), tripulación desaparecida sin explicación confirmada; fuente: archivos marítimos / Smithsonian.",
         "visual": "velero a la deriva, mar en calma, camarote vacío"},
        {"key": "fawcett_z", "titulo": "La ciudad perdida de Z y la desaparición de Fawcett",
         "hook": "Un explorador entró en el Amazonas buscando una ciudad. No volvió.",
         "angle": "Percy Fawcett desapareció en 1925 buscando 'Z'; hallazgos recientes (Kuhikugu) sugieren urbanismo amazónico real; fuente: Royal Geographical Society.",
         "visual": "selva amazónica densa, mapa antiguo, niebla sobre el río"},
        {"key": "rapa_nui_moai", "titulo": "Moái de Pascua: cómo 'caminaron' estatuas de 80 toneladas",
         "hook": "Movieron estatuas gigantes sin ruedas ni grúas. ¿Cómo?",
         "angle": "Transporte de los moái de Rapa Nui; experimentos (Lipo/Hunt) muestran que pudieron 'caminar' balanceándolas con cuerdas; fuente: Journal of Archaeological Science.",
         "visual": "moáis en fila, cantera Rano Raraku, costa de Pascua"},
    ],
)

# ───────────────────────── 2) Sesgos cognitivos / modelos mentales (ES) ─────────────────────────
SESGOS = SimpleChannelConfig(
    slug="sesgos", prefix="YT_SESGOS", display_name="Mente Racional",
    platform_key="youtube_sesgos", lang="es", system_prompt_file="batch_es_system.md",
    tone="didáctico, claro y cercano; como un amigo listo que te revela cómo te engaña tu mente",
    category_id="27", emoji="🧠", cross_teaser="🧠 Sesgo cognitivo",
    to_tiktok=True, to_ig=True,  # user 03/10: shorts también a IG + TikTok
    ig_hashtags=["psicologia", "sesgoscognitivos", "mente", "aprende", "curiosidades", "shorts"],
    theme_desc=("A Spanish faceless channel explaining ONE cognitive bias / mental model per "
                "video, grounded in real behavioral science (Kahneman, Tversky, Ariely, etc.)."),
    veracity_rules=("- Each bias MUST trace to named, real research (e.g. Kahneman & Tversky). "
                    "Cite it. NO pop-psychology, NO 'dark psychology', NO manipulation claims, "
                    "NO unfalsifiable 'facts'."),
    seed=[
        {"key": "anchoring", "titulo": "El efecto ancla: por qué el primer número te manipula",
         "hook": "Te enseñan un precio altísimo primero… y ya has caído.",
         "angle": "Anclaje (Tversky & Kahneman, 1974): la primera cifra sesga estimaciones posteriores; cómo contrarrestarlo.",
         "visual": "balanza, etiquetas de precio, cerebro ilustrado minimal"},
        {"key": "loss_aversion", "titulo": "Aversión a la pérdida: perder duele el doble que ganar",
         "hook": "Perder 100€ duele más de lo que alegra ganarlos. No es casualidad.",
         "angle": "Aversión a la pérdida (Kahneman & Tversky, teoría prospectiva, 1979): las pérdidas pesan ~2x; ejemplos cotidianos.",
         "visual": "balanza desnivelada, billetes, gráfico de utilidad"},
        {"key": "sunk_cost", "titulo": "La falacia del coste hundido: por qué no sabes rendirte",
         "hook": "Sigues con algo malo solo porque ya invertiste en ello.",
         "angle": "Falacia del coste hundido: decidir por lo ya gastado en vez del valor futuro; cómo detectarla.",
         "visual": "entrada de cine rota, reloj, persona dudando"},
        {"key": "confirmation", "titulo": "Sesgo de confirmación: solo ves lo que ya crees",
         "hook": "Tu cerebro busca pruebas de lo que ya piensas e ignora el resto.",
         "angle": "Sesgo de confirmación (Wason, 1960): buscamos info que confirma creencias; cómo romperlo.",
         "visual": "lupa, burbuja, piezas de puzzle que no encajan"},
        {"key": "dunning_kruger", "titulo": "Dunning-Kruger: por qué los que menos saben se creen expertos",
         "hook": "Cuanto menos sabes de algo, más crees que lo dominas.",
         "angle": "Efecto Dunning-Kruger (1999): baja competencia → sobreestimación; y el reverso en expertos.",
         "visual": "montaña con pico y valle, gráfico confianza vs conocimiento"},
        {"key": "availability", "titulo": "Heurística de disponibilidad: por qué temes lo improbable",
         "hook": "Temes al avión y no al coche. Tu memoria te engaña.",
         "angle": "Heurística de disponibilidad (Tversky & Kahneman): juzgamos probabilidad por lo fácil que viene a la mente.",
         "visual": "titulares de prensa, avión, cerebro con focos"},
        {"key": "survivorship", "titulo": "Sesgo del superviviente: los aviones de la Segunda Guerra",
         "hook": "Reforzaron los aviones donde NO tenían agujeros. ¿Por qué acertaron?",
         "angle": "Sesgo del superviviente (Abraham Wald, SRG): solo vemos a los que 'sobreviven'; el caso de los bombarderos.",
         "visual": "diagrama de bombardero con impactos, hangar, blueprint"},
        {"key": "halo_effect", "titulo": "Efecto halo: por qué lo guapo te parece competente",
         "hook": "Si alguien es atractivo, le atribuyes talento sin pruebas.",
         "angle": "Efecto halo (Thorndike, 1920): un rasgo positivo contamina el juicio global; en entrevistas y marcas.",
         "visual": "retrato con halo de luz, currículums, foco"},
        {"key": "framing", "titulo": "Efecto marco: '90% sin grasa' vs '10% de grasa'",
         "hook": "Es el mismo dato. Pero uno te lo compras y el otro no.",
         "angle": "Efecto marco (Tversky & Kahneman): la forma de presentar la info cambia la decisión; ejemplos de salud y compra.",
         "visual": "dos etiquetas idénticas con texto distinto, carrito, cerebro"},
    ],
)

# ───────────────────────── 3) Filosofía profunda (ES) — distinta de Stoic Mind ─────────────────────────
FILOSOFIA = SimpleChannelConfig(
    slug="filosofia", prefix="YT_FILOSOFIA", display_name="Abismo",
    platform_key="youtube_filosofia", lang="es", system_prompt_file="batch_es_system.md",
    tone="contemplativo, profundo y cinematográfico; nada de autoayuda barata ni frases de calendario",
    category_id="27", emoji="🕯️", cross_teaser="🕯️ Filosofía",
    theme_desc=("A Spanish faceless channel on DEPTH philosophy — Jung, Nietzsche, Schopenhauer, "
                "Camus, Kierkegaard, Plato — applied to the human condition. DISTINCT from a "
                "stoicism channel: focus on depth-psychology and existentialism, not Stoic quotes."),
    veracity_rules=("- Attribute ideas to the right philosopher and their real work (e.g. Jung "
                    "'Aion', Nietzsche 'Thus Spoke Zarathustra'). Explain the idea in your own "
                    "words; do NOT fabricate verbatim quotes. No self-help pseudoscience."),
    seed=[
        {"key": "jung_shadow", "titulo": "La sombra de Jung: lo que escondes te gobierna",
         "hook": "Lo que más odias en otros suele ser lo que niegas en ti.",
         "angle": "La 'sombra' de Jung: los rasgos reprimidos del inconsciente; integrarla, no negarla (obra: Aion).",
         "visual": "silueta y sombra, espejo oscuro, figura entre niebla"},
        {"key": "nietzsche_eternal", "titulo": "El eterno retorno de Nietzsche: ¿repetirías tu vida?",
         "hook": "¿Y si tuvieras que vivir tu vida idéntica, infinitas veces?",
         "angle": "El eterno retorno (Nietzsche, 'La gaya ciencia'): prueba para vivir de forma que aceptarías repetirlo todo.",
         "visual": "reloj circular, desierto infinito, estrellas en bucle"},
        {"key": "schopenhauer_desire", "titulo": "Schopenhauer: por qué conseguir lo que quieres no te llena",
         "hook": "Logras lo que deseabas… y a los días vuelves a estar vacío.",
         "angle": "Schopenhauer ('El mundo como voluntad y representación'): el deseo oscila entre dolor y aburrimiento.",
         "visual": "péndulo, habitación vacía, mar gris"},
        {"key": "camus_sisyphus", "titulo": "Camus y Sísifo: cómo ser feliz en lo absurdo",
         "hook": "Empuja una roca que siempre vuelve a caer. Y aun así sonríe.",
         "angle": "Camus ('El mito de Sísifo'): el absurdo no se resuelve, se rebela uno viviéndolo plenamente.",
         "visual": "figura empujando roca montaña, atardecer, cumbre"},
        {"key": "plato_cave", "titulo": "La caverna de Platón: ¿y si solo ves sombras?",
         "hook": "Encadenados desde niños, creen que las sombras son el mundo.",
         "angle": "La alegoría de la caverna (Platón, 'La República'): percepción vs realidad; el precio de salir.",
         "visual": "cueva con fuego, sombras en la pared, luz cegadora en la salida"},
        {"key": "kierkegaard_anxiety", "titulo": "Kierkegaard: la angustia es el vértigo de la libertad",
         "hook": "La angustia no es miedo a algo: es el vértigo de poder elegir.",
         "angle": "Kierkegaard ('El concepto de la angustia'): la libertad genera angustia; qué hacer con ella.",
         "visual": "borde de acantilado, encrucijada, cielo abierto"},
        {"key": "nietzsche_become", "titulo": "'Llega a ser el que eres' — Nietzsche explicado",
         "hook": "No eres una copia. Pero vives como si lo fueras.",
         "angle": "Nietzsche ('Así habló Zaratustra'): convertirse en uno mismo frente al rebaño; autosuperación.",
         "visual": "figura ascendiendo, águila, montaña al amanecer"},
        {"key": "jung_persona", "titulo": "La 'persona' de Jung: la máscara que crees que eres",
         "hook": "Enseñas una máscara tantas horas que olvidas quitártela.",
         "angle": "La 'persona' de Jung: la máscara social; el peligro de identificarte con ella.",
         "visual": "máscara teatral, rostro difuminado, foco de escenario"},
    ],
)

# ───────────────────────── 4) ¿Qué pasaría si? / curiosidades (ES) ─────────────────────────
CURIOSIDADES = SimpleChannelConfig(
    slug="curiosidades", prefix="YT_CURIOSIDADES", display_name="¿Qué Pasaría Si?",
    platform_key="youtube_curiosidades", lang="es", system_prompt_file="batch_es_system.md",
    tone="curioso y energético, divulgativo; asombro con rigor científico",
    category_id="27", emoji="🤔", cross_teaser="🤔 ¿Qué pasaría si…",
    theme_desc=("A Spanish faceless channel of 'what if' hypotheticals and surprising facts, "
                "GROUNDED IN REAL SCIENCE (physics, biology, astronomy). The hypothetical is the "
                "hook; the payoff is real science."),
    veracity_rules=("- The scenario can be hypothetical, but the SCIENCE explaining it must be real "
                    "and citable. NEVER present fiction as fact. Non-YMYL (no medical scenarios "
                    "framed as advice)."),
    seed=[
        {"key": "earth_stop", "titulo": "¿Qué pasaría si la Tierra dejara de girar?",
         "hook": "Si la Tierra se parase de golpe, seguirías moviéndote a 1600 km/h.",
         "angle": "Inercia: a 0° la superficie gira ~1670 km/h; parada súbita = catástrofe; física real (NASA).",
         "visual": "Tierra desde el espacio, vientos huracanados, atmósfera"},
        {"key": "no_moon", "titulo": "¿Qué pasaría si desapareciera la Luna?",
         "hook": "Sin Luna, los días se acortarían y el eje de la Tierra bailaría.",
         "angle": "La Luna estabiliza el eje terrestre y genera mareas; su ausencia alteraría clima y rotación (fuente: NASA).",
         "visual": "luna llena, mareas, eje terrestre inclinado"},
        {"key": "everyone_jump", "titulo": "¿Qué pasaría si todos saltáramos a la vez?",
         "hook": "8000 millones saltando juntos… ¿movemos la Tierra?",
         "angle": "La masa humana es ínfima frente a la Tierra: el efecto es despreciable; cálculo físico real.",
         "visual": "multitud saltando, planeta, flechas de fuerza"},
        {"key": "black_hole_fall", "titulo": "¿Qué pasaría si cayeras en un agujero negro?",
         "hook": "Te estirarías como un espagueti. Tiene nombre científico.",
         "angle": "'Espaguetización' por gradiente de marea; dilatación temporal cerca del horizonte (relatividad general).",
         "visual": "agujero negro, disco de acreción, estrellas curvadas"},
        {"key": "light_speed", "titulo": "¿Qué pasaría si viajaras a la velocidad de la luz?",
         "hook": "Para ti el tiempo casi se detendría frente al resto del universo.",
         "angle": "Dilatación del tiempo (relatividad especial); por qué ningún objeto con masa la alcanza.",
         "visual": "nave estelar, estrellas en líneas, reloj deformado"},
        {"key": "sun_disappear", "titulo": "¿Qué pasaría si el Sol desapareciera ahora?",
         "hook": "Lo verías 8 minutos más. La gravedad también tardaría.",
         "angle": "La luz del Sol tarda ~8 min 20 s; la Tierra saldría despedida en línea recta (fuente: NASA).",
         "visual": "sol, sistema solar, oscuridad progresiva"},
        {"key": "no_insects", "titulo": "¿Qué pasaría si desaparecieran los insectos?",
         "hook": "Sin insectos, la cadena alimentaria se derrumba en meses.",
         "angle": "Polinización y descomposición dependen de insectos; colapso ecológico documentado (estudios de biodiversidad).",
         "visual": "abeja en flor, campo, ecosistema"},
        {"key": "deepest_hole", "titulo": "¿Qué pasaría si cavaras hasta el centro de la Tierra?",
         "hook": "El pozo más profundo jamás cavado no llega ni al 0,2% del camino.",
         "angle": "Kola Superdeep (~12,2 km) vs radio terrestre (~6371 km); calor y presión lo impiden (fuente: proyecto Kola).",
         "visual": "corte de la Tierra por capas, taladro, magma"},
    ],
)

# ───────────────────────── 5) Espacio / universo (ES) ─────────────────────────
ESPACIO = SimpleChannelConfig(
    slug="espacio", prefix="YT_ESPACIO", display_name="Cosmos",
    platform_key="youtube_espacio", lang="es", system_prompt_file="batch_es_system.md",
    tone="asombro cósmico, evocador y divulgativo; datos reales que dejan sin palabras",
    category_id="27", emoji="🪐", cross_teaser="🪐 Cosmos",
    theme_desc=("A Spanish faceless channel of astronomy & space facts — scale of the universe, "
                "stars, black holes, planets — using real data and NASA/ESA public-domain imagery."),
    veracity_rules=("- Only real, current astronomy from citable sources (NASA, ESA, peer-reviewed). "
                    "No astrology, no aliens-as-fact, no speculation presented as established."),
    seed=[
        {"key": "neutron_star", "titulo": "Una cucharada de estrella de neutrones pesa como una montaña",
         "hook": "Una cucharadita de esta estrella pesaría mil millones de toneladas.",
         "angle": "Densidad de las estrellas de neutrones (~10^17 kg/m³); restos de supernovas (fuente: NASA).",
         "visual": "estrella de neutrones, púlsar girando, campo estelar"},
        {"key": "venus_day", "titulo": "En Venus, un día dura más que un año",
         "hook": "Venus gira tan lento que su día supera a su año.",
         "angle": "Rotación de Venus ~243 días terrestres vs órbita ~225 días (fuente: NASA planetary fact sheet).",
         "visual": "Venus nublado, órbita, sol"},
        {"key": "voyager", "titulo": "La Voyager 1: el objeto humano más lejano",
         "hook": "Lanzada en 1977, ya está fuera del sistema solar.",
         "angle": "Voyager 1 en el espacio interestelar desde 2012, a >24.000 millones de km (fuente: NASA/JPL).",
         "visual": "sonda Voyager, disco dorado, espacio profundo"},
        {"key": "olympus_mons", "titulo": "Olympus Mons: un volcán 3 veces el Everest",
         "hook": "El volcán más alto conocido está en Marte y es colosal.",
         "angle": "Olympus Mons ~22 km de altura (~2,5x Everest); fuente: NASA/USGS Marte.",
         "visual": "Marte rojo, volcán gigante, superficie marciana"},
        {"key": "scream_space", "titulo": "¿Por qué no se puede gritar en el espacio?",
         "hook": "En el espacio nadie te oiría. Y hay una razón física.",
         "angle": "El sonido necesita un medio; el vacío no propaga ondas sonoras (física básica, fuente: NASA).",
         "visual": "astronauta en el vacío, ondas, estrellas"},
        {"key": "light_delay_sun", "titulo": "El Sol que ves es el Sol de hace 8 minutos",
         "hook": "Si el Sol se apagara, lo seguirías viendo 8 minutos.",
         "angle": "La luz tarda ~8 min 20 s en llegar del Sol; para estrellas lejanas, años (fuente: NASA).",
         "visual": "sol, rayo de luz, reloj, Tierra"},
        {"key": "universe_scale", "titulo": "Si el Sol fuera una pelota, la Tierra sería un grano",
         "hook": "La escala del universo es tan brutal que el cerebro no la procesa.",
         "angle": "Escala del sistema solar y distancias (años luz); comparación a escala (fuente: NASA).",
         "visual": "modelo a escala planetas, vía láctea, cosmos"},
        {"key": "rogue_planets", "titulo": "Planetas errantes: mundos sin estrella vagando a oscuras",
         "hook": "Hay planetas que no orbitan ninguna estrella. Vagan solos.",
         "angle": "Planetas errantes expulsados de sus sistemas, miles de millones posibles (fuente: NASA/estudios).",
         "visual": "planeta oscuro solitario, campo estelar, nebulosa"},
    ],
)


BATCH: list[SimpleChannelConfig] = [MISTERIOS, SESGOS, FILOSOFIA, CURIOSIDADES, ESPACIO]


def by_slug(slug: str) -> SimpleChannelConfig | None:
    for c in BATCH:
        if c.slug == slug:
            return c
    return None
