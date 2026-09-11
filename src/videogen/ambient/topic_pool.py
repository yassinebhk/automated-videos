"""Pool de temas ambient/relax MenteEnCalma — 4 estilos.

1. **Binaurales** (alpha/beta/gamma/theta/delta): generados en runtime
   con numpy/scipy (tonos puros — cero coste, cero fetch externo).
2. **Clásica**: Pixabay Music CC0 classical (fallback IMSLP dominio público).
3. **Naturaleza** (lluvia/océano/bosque/fuego): Pixabay Music CC0.
4. **Lofi/ambient**: Pixabay Music CC0 lofi/chill/ambient loops.

Reglas veracidad: SIN claims médicos falsos. Solo "acompaña", "relajante",
"para descansar". Nada de "cura", "trata", "reduce estrés medido".
"""
from __future__ import annotations

# key, mood_type, generator (binaural/pixabay), music_query o freq_hz,
# imagen query, base_keywords, modifiers, duración
TOPICS = [
    # ─── ONDAS BINAURALES (generadas en runtime) ───
    {
        "key": "alpha_8hz_focus", "mood_type": "binaural",
        "carrier_hz": 200, "beat_hz": 8, "wave": "alpha",
        "pixabay_music_query": None,
        "pexels_image_query": "abstract calm blue purple gradient meditation",
        "base_keywords": ["ondas alpha 8hz", "música focus estudio"],
        "modifiers": ["concentración profunda", "estudiar sin distracciones",
                       "trabajo productivo", "flow state", "leer un libro"],
        "mood": "focus",
        "min_duration_minutes": 30, "max_duration_minutes": 60,
    },
    {
        "key": "beta_15hz_alerta", "mood_type": "binaural",
        "carrier_hz": 250, "beat_hz": 15, "wave": "beta",
        "pixabay_music_query": None,
        "pexels_image_query": "energetic focused workspace productive vibrant",
        "base_keywords": ["ondas beta 15hz", "música despertar mental"],
        "modifiers": ["alerta mental", "reunión importante", "productividad máx",
                       "resolver problemas", "aprender rápido"],
        "mood": "alert",
        "min_duration_minutes": 30, "max_duration_minutes": 45,
    },
    {
        "key": "theta_6hz_dormir", "mood_type": "binaural",
        "carrier_hz": 150, "beat_hz": 6, "wave": "theta",
        "pixabay_music_query": None,
        "pexels_image_query": "deep space stars sleep night calm",
        "base_keywords": ["ondas theta 6hz", "música dormir profundo"],
        "modifiers": ["sueño profundo", "meditación profunda", "relajación total",
                       "insomnio", "descanso reparador"],
        "mood": "sleep",
        "min_duration_minutes": 60, "max_duration_minutes": 60,
    },
    {
        "key": "delta_2hz_regeneracion", "mood_type": "binaural",
        "carrier_hz": 100, "beat_hz": 2, "wave": "delta",
        "pixabay_music_query": None,
        "pexels_image_query": "soft dark deep sleep ocean floor calm",
        "base_keywords": ["ondas delta 2hz", "música sueño reparador"],
        "modifiers": ["sueño reparador", "regeneración celular", "descanso profundo",
                       "meditación avanzada", "sanación"],
        "mood": "deep_sleep",
        "min_duration_minutes": 60, "max_duration_minutes": 60,
    },
    {
        "key": "gamma_40hz_memoria", "mood_type": "binaural",
        "carrier_hz": 300, "beat_hz": 40, "wave": "gamma",
        "pixabay_music_query": None,
        "pexels_image_query": "vibrant neural network brain synapses colorful",
        "base_keywords": ["ondas gamma 40hz", "música memoria concentración"],
        "modifiers": ["memoria activa", "aprendizaje intenso", "creatividad máxima",
                       "resolver exámenes", "productividad extrema"],
        "mood": "gamma_focus",
        "min_duration_minutes": 30, "max_duration_minutes": 45,
    },

    # ─── MÚSICA CLÁSICA (Pixabay CC0 classical) ───
    {
        "key": "clasica_bach_estudiar", "mood_type": "pixabay",
        "pixabay_music_query": "bach classical piano",
        "pexels_image_query": "elegant piano candlelight vintage warm study",
        "base_keywords": ["Bach para estudiar", "clásica concentración"],
        "modifiers": ["concentrarse en el trabajo", "leer literatura",
                       "programar en calma", "escribir con foco"],
        "mood": "classical_focus",
        "min_duration_minutes": 45, "max_duration_minutes": 60,
    },
    {
        "key": "clasica_mozart_relax", "mood_type": "pixabay",
        "pixabay_music_query": "mozart classical orchestra",
        "pexels_image_query": "grand piano hall classical warm sunset elegant",
        "base_keywords": ["Mozart relajante", "clásica descansar"],
        "modifiers": ["descansar tras trabajo", "leer novela",
                       "sobremesa tranquila", "meditación clásica"],
        "mood": "classical_relax",
        "min_duration_minutes": 45, "max_duration_minutes": 60,
    },
    {
        "key": "clasica_chopin_noche", "mood_type": "pixabay",
        "pixabay_music_query": "chopin nocturne piano solo",
        "pexels_image_query": "moonlight window piano quiet night warm lamp",
        "base_keywords": ["Chopin nocturnos", "piano noche relax"],
        "modifiers": ["dormir en calma", "leer antes de dormir",
                       "tarde de invierno", "reflexión personal"],
        "mood": "classical_night",
        "min_duration_minutes": 45, "max_duration_minutes": 60,
    },

    # ─── SONIDOS NATURALEZA ───
    {
        "key": "lluvia_dormir", "mood_type": "pixabay",
        "pixabay_music_query": "rain thunderstorm relax",
        "pexels_image_query": "rain window night calm cozy warm",
        "base_keywords": ["lluvia para dormir", "sonido lluvia relajante"],
        "modifiers": ["dormir profundo", "insomnio nocturno", "meditación",
                       "descanso profundo", "leer con lluvia"],
        "mood": "rain",
        "min_duration_minutes": 60, "max_duration_minutes": 60,
    },
    {
        "key": "oceano_meditar", "mood_type": "pixabay",
        "pixabay_music_query": "ocean waves calm sea",
        "pexels_image_query": "calm ocean sunset horizon warm colors peaceful",
        "base_keywords": ["olas mar meditación", "océano relajante"],
        "modifiers": ["meditar en playa", "yoga acompañado", "spa masaje",
                       "sueño profundo", "descanso tras trabajo"],
        "mood": "ocean",
        "min_duration_minutes": 30, "max_duration_minutes": 60,
    },
    {
        "key": "bosque_amanecer", "mood_type": "pixabay",
        "pixabay_music_query": "forest birds morning nature",
        "pexels_image_query": "misty forest morning sun rays green peaceful",
        "base_keywords": ["bosque relajante amanecer", "pájaros naturaleza"],
        "modifiers": ["meditación matutina", "yoga suave", "dormir bebé",
                       "leer con té", "descansar tras trabajo"],
        "mood": "forest",
        "min_duration_minutes": 30, "max_duration_minutes": 45,
    },
    {
        "key": "chimenea_invierno", "mood_type": "pixabay",
        "pixabay_music_query": "fireplace crackle fire cozy",
        "pexels_image_query": "cozy fireplace cabin winter warm blanket dim",
        "base_keywords": ["chimenea crepitando", "fuego relajante"],
        "modifiers": ["invierno acogedor", "leer con té", "dormir tranquilo",
                       "relajarse en casa", "atmósfera cálida"],
        "mood": "fireplace",
        "min_duration_minutes": 45, "max_duration_minutes": 60,
    },

    # ─── LOFI / AMBIENT ELECTRÓNICO ───
    {
        "key": "lofi_estudio", "mood_type": "pixabay",
        "pixabay_music_query": "lofi chill study",
        "pexels_image_query": "lofi anime aesthetic night city warm neon window",
        "base_keywords": ["lofi para estudiar", "beats chill estudio"],
        "modifiers": ["exámenes finales", "trabajo largo", "café mañana",
                       "programar código", "escribir tesis"],
        "mood": "lofi_study",
        "min_duration_minutes": 45, "max_duration_minutes": 60,
    },
    {
        "key": "lofi_trabajo", "mood_type": "pixabay",
        "pixabay_music_query": "lofi hip hop chill beats",
        "pexels_image_query": "cozy workspace desk warm lofi vibes coffee",
        "base_keywords": ["lofi trabajar", "música oficina relajada"],
        "modifiers": ["trabajo remoto", "creatividad calma", "planificar día",
                       "diseñar en calma", "escribir emails"],
        "mood": "lofi_work",
        "min_duration_minutes": 45, "max_duration_minutes": 60,
    },
    {
        "key": "ambient_espacial", "mood_type": "pixabay",
        "pixabay_music_query": "ambient space cosmic synth",
        "pexels_image_query": "space nebula stars cosmic vibrant colors deep",
        "base_keywords": ["ambient espacial", "música cósmica"],
        "modifiers": ["meditación profunda", "sueño lúcido", "ciencia ficción",
                       "creatividad", "reflexión filosófica"],
        "mood": "cosmic",
        "min_duration_minutes": 45, "max_duration_minutes": 60,
    },
    {
        "key": "ambient_zen", "mood_type": "pixabay",
        "pixabay_music_query": "zen meditation ambient calm",
        "pexels_image_query": "zen stones balance minimalist water reflection",
        "base_keywords": ["música meditación zen", "ambient relajante"],
        "modifiers": ["mindfulness", "respiración consciente", "yoga suave",
                       "estrés cotidiano", "reiki calma"],
        "mood": "zen",
        "min_duration_minutes": 30, "max_duration_minutes": 45,
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
