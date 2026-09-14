"""Pool de temas ambient/relax MenteEnCalma — optimizado SEO YT ES.

4 estilos + búsquedas long-tail reales que la gente escribe en YT.
Referencias de canales top ES: The Soul of Wind ES, Yellow Brick,
Meditation Relax Music, Jason Stephenson.

1. **Binaurales** (alpha/beta/gamma/theta/delta): generados runtime
   con ffmpeg sinusoidal (cero coste, cero fetch externo).
2. **Clásica**: Pixabay Music CC0 classical.
3. **Naturaleza** (lluvia/océano/bosque/fuego): Pixabay Music CC0.
4. **Lofi/ambient**: Pixabay Music CC0 lofi/chill/ambient loops.
5. **NUEVOS 14/09/26**: ruido blanco bebés, 528Hz, 432Hz, cuencos
   tibetanos, música yoga, música leer, música oficina.

Reglas veracidad: SIN claims médicos falsos. Solo "acompaña",
"relajante", "para descansar". Nada de "cura", "trata", "reduce
estrés medido".

Keywords base optimizados a búsquedas reales YT ES (Google Trends
+ TubeBuddy long-tail — septiembre 2026).
"""
from __future__ import annotations


TOPICS = [
    # ═══════════════════════════════════════════════════════════
    # ONDAS BINAURALES (generadas runtime ffmpeg — sin dep externa)
    # ═══════════════════════════════════════════════════════════
    {
        "key": "alpha_8hz_estudiar", "mood_type": "binaural",
        "carrier_hz": 200, "beat_hz": 8, "wave": "alpha",
        "pixabay_music_query": None,
        "pixabay_fallback_queries": ["ambient calm", "relaxing"],
        "pexels_image_query": "student desk warm lamp study concentrated books",
        "base_keywords": [
            "Musica para Estudiar y Concentrarse Ondas Alfa 8Hz",
            "Ondas Alfa 8Hz Concentracion Maxima",
            "Musica Binaural para Estudiar Sin Distracciones",
        ],
        "modifiers": ["estudiar concentrado", "leer con foco",
                       "trabajo mental profundo", "flow state estudio"],
        "mood": "focus",
        "min_duration_minutes": 60, "max_duration_minutes": 180,
    },
    {
        "key": "beta_15hz_alerta", "mood_type": "binaural",
        "carrier_hz": 250, "beat_hz": 15, "wave": "beta",
        "pixabay_music_query": None,
        "pixabay_fallback_queries": ["ambient upbeat", "energetic ambient"],
        "pexels_image_query": "morning coffee laptop bright energetic productivity",
        "base_keywords": [
            "Ondas Beta 15Hz para Alerta Mental",
            "Musica para Despertar el Cerebro Ondas Beta",
            "Frecuencia Beta Concentracion Alerta Maxima",
        ],
        "modifiers": ["alerta mental máxima", "aprendizaje intenso",
                       "reunión importante", "resolver problemas complejos"],
        "mood": "alert",
        "min_duration_minutes": 45, "max_duration_minutes": 90,
    },
    {
        "key": "theta_6hz_dormir_profundo", "mood_type": "binaural",
        "carrier_hz": 150, "beat_hz": 6, "wave": "theta",
        "pixabay_music_query": None,
        "pixabay_fallback_queries": ["deep sleep ambient", "meditation deep"],
        "pexels_image_query": "starry night deep space calm dark peaceful",
        "base_keywords": [
            "Musica para Dormir Profundo Ondas Theta 8 Horas",
            "Ondas Theta 6Hz Sueño Profundo Reparador",
            "Musica Binaural para Insomnio Dormir Rapido",
        ],
        "modifiers": ["dormir profundo toda la noche", "combatir insomnio",
                       "meditación profunda", "descanso reparador 8h"],
        "mood": "sleep",
        "min_duration_minutes": 180, "max_duration_minutes": 480,
    },
    {
        "key": "delta_2hz_sueno_reparador", "mood_type": "binaural",
        "carrier_hz": 100, "beat_hz": 2, "wave": "delta",
        "pixabay_music_query": None,
        "pixabay_fallback_queries": ["deep sleep drone", "ambient sleep"],
        "pexels_image_query": "deep dark peaceful abstract soft blue night",
        "base_keywords": [
            "Ondas Delta 2Hz Sueño Reparador 8 Horas",
            "Musica para Dormir Toda la Noche Ondas Delta",
            "Frecuencia Delta Regeneracion Cerebro Dormir",
        ],
        "modifiers": ["sueño reparador 8h completas", "regeneración celular",
                       "meditación avanzada nivel profundo",
                       "descanso reparador máximo"],
        "mood": "deep_sleep",
        "min_duration_minutes": 240, "max_duration_minutes": 480,
    },
    {
        "key": "gamma_40hz_memoria", "mood_type": "binaural",
        "carrier_hz": 300, "beat_hz": 40, "wave": "gamma",
        "pixabay_music_query": None,
        "pixabay_fallback_queries": ["ambient focus", "brain music"],
        "pexels_image_query": "neural network brain vibrant colorful synapses",
        "base_keywords": [
            "Ondas Gamma 40Hz para Mejorar la Memoria",
            "Musica Binaural Gamma Aprender Rapido",
            "Frecuencia Gamma Estimula el Cerebro Estudiar",
        ],
        "modifiers": ["memorizar temario examen", "aprender rápido",
                       "creatividad máxima", "resolver problemas complejos"],
        "mood": "gamma_focus",
        "min_duration_minutes": 45, "max_duration_minutes": 90,
    },

    # ═══════════════════════════════════════════════════════════
    # FRECUENCIAS SOLFEGGIO (NUEVO — nicho muy buscado, no médico)
    # ═══════════════════════════════════════════════════════════
    {
        "key": "hz_528_meditar", "mood_type": "binaural",
        "carrier_hz": 528, "beat_hz": 4, "wave": "solfeggio",
        "pixabay_music_query": None,
        "pixabay_fallback_queries": ["healing meditation", "spiritual ambient"],
        "pexels_image_query": "golden light spiritual meditation aura serene",
        "base_keywords": [
            "Frecuencia 528 Hz para Meditar y Relajarse",
            "528 Hz Musica para Meditacion Profunda",
            "Frecuencia del Amor 528 Hz",
        ],
        "modifiers": ["meditación profunda", "relajación total",
                       "yoga en silencio", "conexión interior"],
        "mood": "solfeggio_528",
        "min_duration_minutes": 60, "max_duration_minutes": 180,
    },
    {
        "key": "hz_432_calma", "mood_type": "binaural",
        "carrier_hz": 432, "beat_hz": 4, "wave": "solfeggio",
        "pixabay_music_query": None,
        "pixabay_fallback_queries": ["healing ambient calm", "spiritual peace"],
        "pexels_image_query": "peaceful nature soft morning light zen tranquil",
        "base_keywords": [
            "Musica 432 Hz Relajante para Meditar",
            "Frecuencia 432 Hz Calma y Serenidad",
            "432 Hz Sonido Natural del Universo",
        ],
        "modifiers": ["relajarse tras el trabajo", "calma en momento estrés",
                       "meditación diaria", "descansar mente"],
        "mood": "solfeggio_432",
        "min_duration_minutes": 60, "max_duration_minutes": 180,
    },

    # ═══════════════════════════════════════════════════════════
    # RUIDO BLANCO/ROSA/MARRÓN (NUEVO — nicho grande bebés + estudio)
    # ═══════════════════════════════════════════════════════════
    {
        "key": "ruido_blanco_bebe", "mood_type": "binaural",
        "carrier_hz": 0, "beat_hz": 0, "wave": "noise_white",
        "pixabay_music_query": None,
        "pixabay_fallback_queries": ["white noise baby", "shush baby sleep"],
        "pexels_image_query": "sleeping baby crib soft calm nursery peaceful",
        "base_keywords": [
            "Ruido Blanco para Dormir Bebes 10 Horas",
            "Sonido para Dormir Bebes Recien Nacidos",
            "Ruido Blanco Bebe Calmar Llanto",
        ],
        "modifiers": ["dormir bebés toda la noche", "calmar llanto bebé",
                       "dormir siesta bebé", "shushing sound recién nacidos"],
        "mood": "white_noise_baby",
        "min_duration_minutes": 240, "max_duration_minutes": 480,
    },
    {
        "key": "ruido_marron_dormir", "mood_type": "binaural",
        "carrier_hz": 0, "beat_hz": 0, "wave": "noise_brown",
        "pixabay_music_query": None,
        "pixabay_fallback_queries": ["brown noise", "deep noise sleep"],
        "pexels_image_query": "dark warm cozy blanket night peaceful sleep",
        "base_keywords": [
            "Ruido Marron para Dormir Profundo 8 Horas",
            "Brown Noise para Dormir y Concentrarse",
            "Ruido Marron TDAH Concentracion",
        ],
        "modifiers": ["dormir profundo grave", "concentrarse TDAH ADHD",
                       "estudiar sin distracciones", "meditar en profundidad"],
        "mood": "brown_noise",
        "min_duration_minutes": 180, "max_duration_minutes": 480,
    },
    {
        "key": "ruido_rosa_relax", "mood_type": "binaural",
        "carrier_hz": 0, "beat_hz": 0, "wave": "noise_pink",
        "pixabay_music_query": None,
        "pixabay_fallback_queries": ["pink noise", "calming noise"],
        "pexels_image_query": "soft pink pastel calm minimal serene abstract",
        "base_keywords": [
            "Ruido Rosa para Estudiar y Concentrarse",
            "Pink Noise Musica para Trabajo Foco",
            "Ruido Rosa Memoria Aprendizaje",
        ],
        "modifiers": ["estudiar con concentración", "trabajar sin distracciones",
                       "leer con foco", "memorizar información"],
        "mood": "pink_noise",
        "min_duration_minutes": 90, "max_duration_minutes": 180,
    },

    # ═══════════════════════════════════════════════════════════
    # MÚSICA CLÁSICA (Pixabay CC0 classical)
    # ═══════════════════════════════════════════════════════════
    {
        "key": "clasica_bach_estudiar", "mood_type": "pixabay",
        "pixabay_music_query": "bach classical piano",
        "pixabay_fallback_queries": ["classical piano relaxing", "baroque piano"],
        "pexels_image_query": "elegant piano candlelight warm library books study",
        "base_keywords": [
            "Musica Clasica de Bach para Estudiar Sin Anuncios",
            "Bach Piano Concentracion Estudio Trabajo",
            "Musica Barroca para Concentrarse y Leer",
        ],
        "modifiers": ["estudiar y concentrarse", "leer literatura clásica",
                       "programar en calma", "escribir con foco"],
        "mood": "classical_focus",
        "min_duration_minutes": 60, "max_duration_minutes": 180,
    },
    {
        "key": "clasica_mozart_estudiar", "mood_type": "pixabay",
        "pixabay_music_query": "mozart classical orchestra",
        "pixabay_fallback_queries": ["mozart piano relax", "classical orchestral"],
        "pexels_image_query": "grand piano orchestra classical warm concert hall",
        "base_keywords": [
            "Musica de Mozart para Estudiar y Relajarse",
            "Mozart Efecto Concentracion Estudio",
            "Musica Clasica para Bebes Mozart Efecto",
        ],
        "modifiers": ["estudiar con calma", "leer novela", "bebés y niños relax",
                       "descansar tras trabajo"],
        "mood": "classical_relax",
        "min_duration_minutes": 60, "max_duration_minutes": 120,
    },
    {
        "key": "clasica_chopin_dormir", "mood_type": "pixabay",
        "pixabay_music_query": "chopin nocturne piano solo",
        "pixabay_fallback_queries": ["piano nocturne calm", "romantic piano night"],
        "pexels_image_query": "moonlight window piano warm lamp cozy night",
        "base_keywords": [
            "Chopin Nocturnos para Dormir Piano Relajante",
            "Musica de Piano para Dormir Profundamente",
            "Chopin Piano Romantico para Descansar",
        ],
        "modifiers": ["dormir en calma toda la noche", "leer antes de dormir",
                       "tarde de invierno acogedora", "reflexión personal"],
        "mood": "classical_night",
        "min_duration_minutes": 120, "max_duration_minutes": 240,
    },

    # ═══════════════════════════════════════════════════════════
    # SONIDOS NATURALEZA (Pixabay CC0)
    # ═══════════════════════════════════════════════════════════
    {
        "key": "lluvia_dormir", "mood_type": "pixabay",
        "pixabay_music_query": "rain thunderstorm relax",
        "pixabay_fallback_queries": ["rain sound sleep", "heavy rain"],
        "pexels_image_query": "rain window night dark cozy warm indoor",
        "base_keywords": [
            "Sonido de Lluvia para Dormir 8 Horas Sin Truenos",
            "Lluvia Suave para Dormir Profundamente",
            "Sonido de Lluvia y Truenos para Relajarse",
        ],
        "modifiers": ["dormir profundo toda la noche", "combatir insomnio",
                       "meditar con lluvia", "leer con lluvia ambient"],
        "mood": "rain",
        "min_duration_minutes": 180, "max_duration_minutes": 480,
    },
    {
        "key": "oceano_yoga_meditar", "mood_type": "pixabay",
        "pixabay_music_query": "ocean waves calm sea",
        "pixabay_fallback_queries": ["sea waves relax", "beach ocean sound"],
        "pexels_image_query": "calm ocean sunset horizon warm peaceful beach",
        "base_keywords": [
            "Sonido de Olas del Mar para Meditar y Yoga",
            "Olas del Mar para Dormir y Relajarse",
            "Musica de Playa para Yoga y Spa",
        ],
        "modifiers": ["meditación en playa mental", "yoga sesión completa",
                       "spa masaje relajante", "dormir profundo con olas"],
        "mood": "ocean",
        "min_duration_minutes": 90, "max_duration_minutes": 180,
    },
    {
        "key": "bosque_yoga_amanecer", "mood_type": "pixabay",
        "pixabay_music_query": "forest birds morning nature",
        "pixabay_fallback_queries": ["nature sounds birds", "forest ambient"],
        "pexels_image_query": "misty forest morning sun rays green nature",
        "base_keywords": [
            "Sonidos de la Naturaleza para Relajarse Bosque",
            "Musica para Yoga Bosque Pajaros",
            "Sonidos de Pajaros para Despertar Relajado",
        ],
        "modifiers": ["yoga matutino suave", "meditación al despertar",
                       "leer con té por la mañana", "descansar en naturaleza"],
        "mood": "forest",
        "min_duration_minutes": 60, "max_duration_minutes": 120,
    },
    {
        "key": "chimenea_invierno_leer", "mood_type": "pixabay",
        "pixabay_music_query": "fireplace crackle fire cozy",
        "pixabay_fallback_queries": ["fireplace sound", "crackling fire"],
        "pexels_image_query": "cozy fireplace cabin winter warm blanket book",
        "base_keywords": [
            "Sonido de Chimenea Crepitando para Leer y Dormir",
            "Chimenea de Leña para Relajarse en Invierno",
            "Sonido de Fuego para Dormir Ambiente Acogedor",
        ],
        "modifiers": ["leer libro con té", "invierno acogedor cozy",
                       "dormir con ambiente cálido", "relajarse en casa"],
        "mood": "fireplace",
        "min_duration_minutes": 120, "max_duration_minutes": 240,
    },
    {
        "key": "rio_yoga_meditar", "mood_type": "pixabay",
        "pixabay_music_query": "river stream water flowing",
        "pixabay_fallback_queries": ["water sounds flowing", "stream nature"],
        "pexels_image_query": "peaceful river stream forest zen mossy stones",
        "base_keywords": [
            "Sonido de Rio para Meditar y Relajarse",
            "Sonido de Agua Corriente para Yoga",
            "Musica de Rio Zen para Dormir",
        ],
        "modifiers": ["meditación junto al río", "yoga acompañado",
                       "dormir con agua", "relajarse tras trabajo"],
        "mood": "river",
        "min_duration_minutes": 90, "max_duration_minutes": 180,
    },

    # ═══════════════════════════════════════════════════════════
    # INSTRUMENTOS ESPIRITUALES (NUEVO — nicho yoga/meditación grande)
    # ═══════════════════════════════════════════════════════════
    {
        "key": "cuencos_tibetanos", "mood_type": "pixabay",
        "pixabay_music_query": "tibetan singing bowls meditation",
        "pixabay_fallback_queries": ["singing bowls", "meditation gong"],
        "pexels_image_query": "tibetan singing bowls incense zen meditation altar",
        "base_keywords": [
            "Cuencos Tibetanos para Meditar y Sanacion",
            "Sonido de Cuencos Tibetanos Relajacion Profunda",
            "Meditacion Cuencos Tibetanos para Chakras",
        ],
        "modifiers": ["meditación profunda tibetana", "sesión reiki",
                       "yoga acompañado cuencos", "sanación energética"],
        "mood": "tibetan",
        "min_duration_minutes": 60, "max_duration_minutes": 120,
    },
    {
        "key": "flauta_india_yoga", "mood_type": "pixabay",
        "pixabay_music_query": "indian flute meditation bansuri",
        "pixabay_fallback_queries": ["flute meditation", "spiritual flute"],
        "pexels_image_query": "yoga meditation indian temple sunset spiritual",
        "base_keywords": [
            "Musica India para Yoga y Meditar Flauta",
            "Flauta India Bansuri Relajante Yoga",
            "Musica Hindu para Meditacion Espiritual",
        ],
        "modifiers": ["yoga vinyasa suave", "meditación hindú",
                       "relajarse ambiente oriental", "sesión mindfulness"],
        "mood": "indian_flute",
        "min_duration_minutes": 60, "max_duration_minutes": 120,
    },

    # ═══════════════════════════════════════════════════════════
    # LOFI / AMBIENT ELECTRÓNICO
    # ═══════════════════════════════════════════════════════════
    {
        "key": "lofi_estudiar", "mood_type": "pixabay",
        "pixabay_music_query": "lofi chill study",
        "pixabay_fallback_queries": ["lofi beats", "chill hop"],
        "pexels_image_query": "lofi anime aesthetic night city warm neon window",
        "base_keywords": [
            "Musica Lofi para Estudiar y Concentrarse",
            "Lofi Hip Hop para Estudiar Sin Anuncios",
            "Chill Beats para Estudio Universidad",
        ],
        "modifiers": ["estudiar exámenes finales", "trabajar en calma",
                       "programar código", "escribir tesis"],
        "mood": "lofi_study",
        "min_duration_minutes": 90, "max_duration_minutes": 180,
    },
    {
        "key": "lofi_trabajar", "mood_type": "pixabay",
        "pixabay_music_query": "lofi hip hop chill beats",
        "pixabay_fallback_queries": ["lofi work", "chill office music"],
        "pexels_image_query": "cozy workspace desk coffee laptop warm lofi vibes",
        "base_keywords": [
            "Musica Lofi para Trabajar en Casa Sin Anuncios",
            "Chill Beats para Oficina Trabajo Remoto",
            "Musica de Fondo para Productividad Trabajo",
        ],
        "modifiers": ["trabajo remoto en casa", "productividad oficina",
                       "planificar día concentrado", "diseñar en calma"],
        "mood": "lofi_work",
        "min_duration_minutes": 90, "max_duration_minutes": 180,
    },
    {
        "key": "ambient_espacial_dormir", "mood_type": "pixabay",
        "pixabay_music_query": "ambient space cosmic synth",
        "pixabay_fallback_queries": ["ambient drone", "space music"],
        "pexels_image_query": "space nebula stars cosmic deep peaceful vibrant",
        "base_keywords": [
            "Musica Ambient Espacial para Dormir Profundo",
            "Sonidos del Espacio para Meditar",
            "Musica Cosmica Relajante para Sueño Lucido",
        ],
        "modifiers": ["dormir con música cósmica", "meditación profunda",
                       "sueño lúcido inducido", "reflexión filosófica"],
        "mood": "cosmic",
        "min_duration_minutes": 90, "max_duration_minutes": 240,
    },
    {
        "key": "ambient_zen_yoga", "mood_type": "pixabay",
        "pixabay_music_query": "zen meditation ambient calm",
        "pixabay_fallback_queries": ["zen music", "spa meditation"],
        "pexels_image_query": "zen stones balance water reflection minimalist",
        "base_keywords": [
            "Musica Zen para Yoga y Meditacion",
            "Musica de Spa Relajante Zen",
            "Musica Mindfulness Respiracion Consciente",
        ],
        "modifiers": ["yoga suave sesión completa", "mindfulness diario",
                       "respiración consciente", "reiki calma total"],
        "mood": "zen",
        "min_duration_minutes": 45, "max_duration_minutes": 120,
    },
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None


def binaural_topics() -> list[dict]:
    return [t for t in TOPICS if t.get("mood_type") == "binaural"]
