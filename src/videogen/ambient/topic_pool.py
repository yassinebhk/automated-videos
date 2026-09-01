"""Pool de temas ambient con variantes SEO long-tail.

Estrategia: keywords high-volume (base) × modificadores (uso, duración,
sensación) = títulos long-tail difíciles de competir por canales grandes
pero fáciles de rankear para uno pequeño.

Nichos y mood tags controlan qué música/imagen buscar en Pixabay/Pexels.
"""
from __future__ import annotations

# Cada tema define query para Pixabay Music, keywords SEO base, imagen a buscar
# y sensación transmitida.
TOPICS = [
    {
        "key": "lluvia_dormir",
        "pixabay_music_query": "rain sleep",
        "pexels_image_query": "rain window night calm",
        "base_keywords": ["música para dormir", "sonido lluvia dormir"],
        "modifiers": ["8 horas sin anuncios", "profundo relax", "insomnio",
                       "bebés dormir", "descanso profundo"],
        "mood": "sleep",
        "min_duration_minutes": 30,
        "max_duration_minutes": 60,
    },
    {
        "key": "piano_concentracion",
        "pixabay_music_query": "piano study",
        "pexels_image_query": "cozy desk warm light book",
        "base_keywords": ["música para concentrarse", "piano estudiar"],
        "modifiers": ["trabajar productivo", "leer sin distracciones",
                       "focus profundo", "estudio universidad", "programar"],
        "mood": "focus",
        "min_duration_minutes": 30,
        "max_duration_minutes": 45,
    },
    {
        "key": "lofi_estudio",
        "pixabay_music_query": "lofi chill",
        "pexels_image_query": "lofi anime aesthetic night city",
        "base_keywords": ["lofi para estudiar", "beats chill relax"],
        "modifiers": ["exámenes finales", "trabajo largo", "café mañana",
                       "tarde de sábado", "programar en casa"],
        "mood": "study",
        "min_duration_minutes": 40,
        "max_duration_minutes": 60,
    },
    {
        "key": "oceano_relax",
        "pixabay_music_query": "ocean waves",
        "pexels_image_query": "calm ocean sunset horizon",
        "base_keywords": ["sonido del mar", "olas para relajarse"],
        "modifiers": ["meditación", "yoga en casa", "spa masaje",
                       "sueño profundo", "ansiedad tranquilidad"],
        "mood": "relax",
        "min_duration_minutes": 30,
        "max_duration_minutes": 45,
    },
    {
        "key": "bosque_relax",
        "pixabay_music_query": "forest birds calm",
        "pexels_image_query": "misty forest morning green",
        "base_keywords": ["sonidos naturaleza", "bosque relajante"],
        "modifiers": ["meditación guiada", "dormir bebé", "ansiedad",
                       "leer un libro", "descansar"],
        "mood": "nature",
        "min_duration_minutes": 30,
        "max_duration_minutes": 45,
    },
    {
        "key": "meditacion_ambient",
        "pixabay_music_query": "meditation ambient",
        "pexels_image_query": "zen stones balance minimalist",
        "base_keywords": ["música meditación", "ambient relax"],
        "modifiers": ["mindfulness", "respiración consciente", "yoga suave",
                       "ansiedad", "reiki"],
        "mood": "meditation",
        "min_duration_minutes": 30,
        "max_duration_minutes": 45,
    },
    {
        "key": "chimenea_invierno",
        "pixabay_music_query": "fireplace crackle",
        "pexels_image_query": "cozy fireplace cabin winter",
        "base_keywords": ["sonido chimenea", "fuego crepitando"],
        "modifiers": ["invierno noche", "leer con té", "dormir tranquilo",
                       "relajarse en casa", "acogedor"],
        "mood": "cozy",
        "min_duration_minutes": 45,
        "max_duration_minutes": 60,
    },
    {
        "key": "cafe_mañana",
        "pixabay_music_query": "jazz cafe morning",
        "pexels_image_query": "coffee cup morning window light",
        "base_keywords": ["música café mañana", "jazz relax café"],
        "modifiers": ["desayuno", "café con leche", "leer periódico",
                       "trabajar en casa", "fin de semana"],
        "mood": "morning",
        "min_duration_minutes": 30,
        "max_duration_minutes": 45,
    },
    {
        "key": "musica_bebes",
        "pixabay_music_query": "lullaby baby sleep",
        "pexels_image_query": "baby crib soft light peaceful",
        "base_keywords": ["música para bebés", "canción cuna dormir"],
        "modifiers": ["dormir rápido", "recién nacido", "siesta bebé",
                       "sueño profundo", "calmar llanto"],
        "mood": "lullaby",
        "min_duration_minutes": 45,
        "max_duration_minutes": 60,
    },
    {
        "key": "ambient_espacial",
        "pixabay_music_query": "space ambient synth",
        "pexels_image_query": "space nebula stars cosmic",
        "base_keywords": ["ambient espacial", "música cósmica"],
        "modifiers": ["meditación profunda", "sueño lúcido", "ciencia ficción",
                       "programar código", "creatividad"],
        "mood": "cosmic",
        "min_duration_minutes": 30,
        "max_duration_minutes": 60,
    },
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
