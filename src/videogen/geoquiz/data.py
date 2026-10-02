"""Datos del canal GeoQuiz (EN) — países verificables (ISO2 + nombre + capital).

100% verificable (banderas/capitales son hechos públicos). Banderas desde flagcdn.com
(dominio público, sin API key). Lista curada de países reconocibles (mix fácil/medio)
para que el quiz enganche sin ser imposible. Ver [[tanda-canales-02-10]].
"""
from __future__ import annotations

# (iso2, nombre EN, capital, tier)  tier: 1=fácil 2=medio 3=difícil
COUNTRIES: list[tuple[str, str, str, int]] = [
    ("fr", "France", "Paris", 1), ("de", "Germany", "Berlin", 1),
    ("it", "Italy", "Rome", 1), ("es", "Spain", "Madrid", 1),
    ("gb", "United Kingdom", "London", 1), ("pt", "Portugal", "Lisbon", 1),
    ("us", "United States", "Washington, D.C.", 1), ("ca", "Canada", "Ottawa", 1),
    ("br", "Brazil", "Brasília", 1), ("ar", "Argentina", "Buenos Aires", 1),
    ("mx", "Mexico", "Mexico City", 1), ("jp", "Japan", "Tokyo", 1),
    ("cn", "China", "Beijing", 1), ("in", "India", "New Delhi", 1),
    ("au", "Australia", "Canberra", 1), ("ru", "Russia", "Moscow", 1),
    ("za", "South Africa", "Pretoria", 2), ("eg", "Egypt", "Cairo", 1),
    ("gr", "Greece", "Athens", 1), ("tr", "Turkey", "Ankara", 2),
    ("nl", "Netherlands", "Amsterdam", 1), ("se", "Sweden", "Stockholm", 1),
    ("no", "Norway", "Oslo", 1), ("fi", "Finland", "Helsinki", 2),
    ("pl", "Poland", "Warsaw", 2), ("ch", "Switzerland", "Bern", 2),
    ("at", "Austria", "Vienna", 2), ("be", "Belgium", "Brussels", 2),
    ("ie", "Ireland", "Dublin", 2), ("dk", "Denmark", "Copenhagen", 2),
    ("kr", "South Korea", "Seoul", 2), ("th", "Thailand", "Bangkok", 2),
    ("vn", "Vietnam", "Hanoi", 2), ("id", "Indonesia", "Jakarta", 2),
    ("ph", "Philippines", "Manila", 2), ("sa", "Saudi Arabia", "Riyadh", 2),
    ("ae", "United Arab Emirates", "Abu Dhabi", 2), ("il", "Israel", "Jerusalem", 2),
    ("ng", "Nigeria", "Abuja", 2), ("ke", "Kenya", "Nairobi", 2),
    ("ma", "Morocco", "Rabat", 2), ("cl", "Chile", "Santiago", 2),
    ("co", "Colombia", "Bogotá", 2), ("pe", "Peru", "Lima", 2),
    ("cu", "Cuba", "Havana", 2), ("nz", "New Zealand", "Wellington", 2),
    ("ua", "Ukraine", "Kyiv", 2), ("cz", "Czechia", "Prague", 2),
    ("hu", "Hungary", "Budapest", 2), ("ro", "Romania", "Bucharest", 3),
    ("pk", "Pakistan", "Islamabad", 2), ("bd", "Bangladesh", "Dhaka", 3),
    ("iq", "Iraq", "Baghdad", 2), ("ir", "Iran", "Tehran", 2),
    ("dz", "Algeria", "Algiers", 3), ("et", "Ethiopia", "Addis Ababa", 3),
    ("gh", "Ghana", "Accra", 3), ("ve", "Venezuela", "Caracas", 2),
    ("uy", "Uruguay", "Montevideo", 3), ("py", "Paraguay", "Asunción", 3),
    ("is", "Iceland", "Reykjavík", 2), ("hr", "Croatia", "Zagreb", 3),
    ("rs", "Serbia", "Belgrade", 3), ("sk", "Slovakia", "Bratislava", 3),
    ("bg", "Bulgaria", "Sofia", 3), ("my", "Malaysia", "Kuala Lumpur", 2),
    ("sg", "Singapore", "Singapore", 2), ("qa", "Qatar", "Doha", 3),
]


def flag_url(iso2: str, width: int = 1280) -> str:
    return f"https://flagcdn.com/w{width}/{iso2.lower()}.png"
