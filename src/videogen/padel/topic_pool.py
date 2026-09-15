"""Pool de consejos de pádel (guion curado + jugada animada). Guion escrito a mano
= coste LLM cero + veracidad controlada (técnica correcta, consejo general).
Coordenadas de jugada en metros (pista 10 ancho x 20 largo; red en y=10)."""
from __future__ import annotations


TOPICS = [
    {"key": "bajada_pared", "titulo": "La bajada de pared",
     "narracion": "La bajada de pared es el golpe que separa a un jugador de nivel. "
                  "Deja que la bola pase, bote, toque el cristal y baje. "
                  "Espera con paciencia, colócate de lado y acompaña la bola hacia el fondo rival. "
                  "Ni prisa ni fuerza: control. Sígueme para más pádel.",
     "play": {"ball": [(5, 17), (5, 19.3), (5, 15)], "players": [(4, 3), (6.5, 3.5), (5, 16.5)]}},
    {"key": "la_vibora", "titulo": "La víbora",
     "narracion": "La víbora es una volea cortada y agresiva que sale disparada y bota bajo. "
                  "Golpea a la altura del hombro, con la muñeca firme y efecto cortado. "
                  "Busca la esquina para que la bola muera pegada al cristal. Sígueme para más.",
     "play": {"ball": [(5, 11), (8.5, 4), (9.5, 2)], "players": [(4, 6), (5.5, 12), (7.5, 3)]}},
    {"key": "el_globo", "titulo": "El globo defensivo",
     "narracion": "Cuando te superan en la red, el globo te salva. "
                  "Levanta la bola alta y profunda para que caiga junto a la pared del fondo. "
                  "Ganas tiempo, recuperas la red y le das la vuelta al punto. Sígueme para más pádel.",
     "play": {"ball": [(3, 4), (5, 13), (5, 18.5)], "players": [(3, 4.5), (6, 5), (4, 8), (6.5, 8.5)]}},
    {"key": "posicion", "titulo": "Posición: moveos como uno",
     "narracion": "En pádel se juega en pareja, no en solitario. "
                  "Moveos siempre juntos, como unidos por una cuerda de cinco metros. "
                  "Si tu compañero va a por la bola, tú acompañas. Huecos cerrados, punto ganado. Sígueme.",
     "play": {"ball": [(2, 10), (8, 10)], "players": [(3, 6), (6, 6.5), (4.5, 14), (7.5, 14.5)]}},
    {"key": "remate_x3", "titulo": "El remate por tres metros",
     "narracion": "El por tres es el remate estrella: haces botar la bola con fuerza para que salga por encima del cristal. "
                  "Golpea arriba y hacia abajo con muñeca rápida. Si sale de la pista, punto directo. Sígueme para más.",
     "play": {"ball": [(5, 12), (5, 4), (5, 21)], "players": [(4.5, 7), (3, 15), (7, 15)]}},
    {"key": "la_dejada", "titulo": "La dejada",
     "narracion": "La dejada rompe el ritmo del rival. Con las manos blandas, amortigua la bola para que caiga corta, "
                  "justo detrás de la red. Úsala cuando el rival está lejos, en el fondo. Sorpresa total. Sígueme.",
     "play": {"ball": [(5, 15), (5, 11), (4.5, 9)], "players": [(4, 4), (6.5, 4.5), (5, 14)]}},
    {"key": "defensa_paredes", "titulo": "Defender la doble pared",
     "narracion": "La doble pared asusta, pero tiene truco. Ábrete, deja espacio y sigue la bola con la mirada: "
                  "primero pared de fondo, luego lateral. Espera a que salga y empújala con calma al centro. Sígueme para más pádel.",
     "play": {"ball": [(5, 18), (2, 19.3), (5, 16)], "players": [(4, 5), (6, 5), (5.5, 16.5)]}},
    {"key": "saque", "titulo": "El saque inteligente",
     "narracion": "El saque no es para ganar el punto, es para ganar la red. "
                  "Saca cruzado y buscando la pared lateral, para complicar la devolución. "
                  "En cuanto sacas, sube a la red con tu compañero. Sígueme para más consejos.",
     "play": {"ball": [(3, 8), (7, 12), (8.5, 14)], "players": [(3, 7), (6, 7.5), (4, 13), (7, 13.5)]}},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
