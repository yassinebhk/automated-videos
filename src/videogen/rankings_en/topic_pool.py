"""Pool de rankings globales EN — canal #11 Global Rankings (bar chart race).

Reusa el generador de `ranking` vía `RankingBranding(lang="en", ...)`. Contenido
NUEVO en inglés (NO traducción del pool ES): rankings globales evergreen con
fuente pública citable. Schema idéntico al de ranking ES para reusar el generador.
YMYL excluido (sin salud/medicina/política/cripto/inversión). Cooldown 90 días.
"""
from __future__ import annotations


TOPICS = [
    {"key": "gdp_countries", "audiencia": "general", "categoria": "economy",
     "titulo": "Top 10 countries by GDP · 2000-2026",
     "fuente": "World Bank / IMF",
     "dataset_hint": "Nominal GDP in USD trillion, G20 top 10, China rise vs USA",
     "cifra_ancla": "USD trillion"},
    {"key": "population_countries", "audiencia": "general", "categoria": "demographics",
     "titulo": "Top 10 most populous countries · 1950-2026",
     "fuente": "UN Population Division",
     "dataset_hint": "Population in millions, India overtook China in 2023",
     "cifra_ancla": "million people"},
    {"key": "brand_value", "audiencia": "general", "categoria": "business",
     "titulo": "Top 10 most valuable brands · 2000-2026",
     "fuente": "Interbrand / Kantar BrandZ",
     "dataset_hint": "Apple/Microsoft/Google/Amazon rise vs Coca-Cola/IBM in 2000",
     "cifra_ancla": "USD billion brand value"},
    {"key": "megacities_2050", "audiencia": "general", "categoria": "demographics",
     "titulo": "Top 15 megacities in the world · 2050 projection",
     "fuente": "UN World Urbanization Prospects",
     "dataset_hint": "Tokyo, Delhi, Shanghai, Dhaka, Lagos, Mumbai projections",
     "cifra_ancla": "million urban residents"},
    {"key": "richest_people", "audiencia": "general", "categoria": "economy",
     "titulo": "Top 10 richest people in the world · 2000-2026",
     "fuente": "Forbes billionaires list",
     "dataset_hint": "Gates 2000s then Bezos/Musk/Arnault 2020s, yearly net worth",
     "cifra_ancla": "USD billion net worth"},
    {"key": "youtube_subscribers", "audiencia": "general", "categoria": "internet",
     "titulo": "Top 10 YouTube channels by subscribers · 2010-2026",
     "fuente": "Social Blade historical",
     "dataset_hint": "T-Series, MrBeast, PewDiePie, Cocomelon, Kids Diana",
     "cifra_ancla": "million subscribers"},
    {"key": "champions_scorers", "audiencia": "sports", "categoria": "football",
     "titulo": "Top 20 UEFA Champions League scorers · all-time",
     "fuente": "UEFA official statistics",
     "dataset_hint": "Ronaldo ~140, Messi ~129, Lewandowski 100+",
     "cifra_ancla": "Champions League goals"},
    {"key": "box_office_actors", "audiencia": "general", "categoria": "film",
     "titulo": "Top 15 highest-grossing actors · 2000-2026",
     "fuente": "Box Office Mojo",
     "dataset_hint": "Downey Jr, Scarlett Johansson, Samuel L. Jackson, Zoe Saldana",
     "cifra_ancla": "USD billion box office"},
    {"key": "best_selling_cars", "audiencia": "general", "categoria": "consumer",
     "titulo": "Top 15 best-selling cars of all time",
     "fuente": "Manufacturer reports + JATO",
     "dataset_hint": "Toyota Corolla 50M+, Ford F-Series, VW Golf/Beetle",
     "cifra_ancla": "million units"},
    {"key": "highest_grossing_films", "audiencia": "general", "categoria": "film",
     "titulo": "Top 20 highest-grossing films · all-time",
     "fuente": "Box Office Mojo",
     "dataset_hint": "Avatar, Avengers Endgame, Titanic, Star Wars, worldwide gross",
     "cifra_ancla": "USD billion box office"},
    {"key": "best_selling_artists", "audiencia": "general", "categoria": "music",
     "titulo": "Top 15 best-selling music artists · 1950-2026",
     "fuente": "IFPI / RIAA certifications",
     "dataset_hint": "Beatles, Elvis, Michael Jackson, Madonna, Taylor Swift",
     "cifra_ancla": "million records certified"},
    {"key": "olympic_medals", "audiencia": "sports", "categoria": "sports",
     "titulo": "Top 10 countries by Olympic medals · 1896-2026",
     "fuente": "IOC official history",
     "dataset_hint": "USA leads, USSR/Russia, China rise post-2000, GB, Germany",
     "cifra_ancla": "total medals"},
    {"key": "military_spending", "audiencia": "general", "categoria": "economy",
     "titulo": "Top 10 countries by military spending · 2000-2026",
     "fuente": "SIPRI",
     "dataset_hint": "USA far ahead, China rise, Russia, India, Saudi Arabia",
     "cifra_ancla": "USD billion"},
    {"key": "most_visited_countries", "audiencia": "general", "categoria": "travel",
     "titulo": "Top 10 most visited countries · 2000-2026",
     "fuente": "UN Tourism (UNWTO)",
     "dataset_hint": "France, Spain, USA, China, Italy — international arrivals",
     "cifra_ancla": "million international arrivals"},
    {"key": "smartphone_brands", "audiencia": "general", "categoria": "tech",
     "titulo": "Top 10 smartphone brands by market share · 2010-2026",
     "fuente": "IDC / Counterpoint Research",
     "dataset_hint": "Nokia/BlackBerry fall, Apple/Samsung/Xiaomi rise",
     "cifra_ancla": "percent global market share"},
    {"key": "richest_football_clubs", "audiencia": "sports", "categoria": "football",
     "titulo": "Top 10 richest football clubs · 2010-2026",
     "fuente": "Deloitte Football Money League",
     "dataset_hint": "Real Madrid, Man City, Barcelona, Man United, Bayern revenue",
     "cifra_ancla": "EUR million revenue"},
    {"key": "most_spoken_languages", "audiencia": "general", "categoria": "society",
     "titulo": "Top 15 most spoken languages in the world",
     "fuente": "Ethnologue",
     "dataset_hint": "English, Mandarin, Hindi, Spanish — total speakers",
     "cifra_ancla": "million speakers"},
    {"key": "tallest_buildings", "audiencia": "general", "categoria": "engineering",
     "titulo": "Top 15 tallest buildings in the world · 2000-2026",
     "fuente": "CTBUH",
     "dataset_hint": "Burj Khalifa, Merdeka 118, Shanghai Tower — height in meters",
     "cifra_ancla": "meters tall"},
    {"key": "most_followed_instagram", "audiencia": "general", "categoria": "internet",
     "titulo": "Top 10 most-followed Instagram accounts · 2015-2026",
     "fuente": "Instagram / Social Blade",
     "dataset_hint": "Instagram, Ronaldo, Messi, Selena Gomez — followers",
     "cifra_ancla": "million followers"},
    {"key": "car_manufacturers_sales", "audiencia": "general", "categoria": "business",
     "titulo": "Top 10 car manufacturers by sales · 2000-2026",
     "fuente": "OICA",
     "dataset_hint": "Toyota, VW Group, Hyundai-Kia, GM, Ford — units sold",
     "cifra_ancla": "million vehicles per year"},
    {"key": "biggest_companies_revenue", "audiencia": "general", "categoria": "business",
     "titulo": "Top 10 companies by revenue · 2000-2026",
     "fuente": "Fortune Global 500",
     "dataset_hint": "Walmart, Amazon, State Grid, Saudi Aramco, Apple",
     "cifra_ancla": "USD billion revenue"},
    {"key": "most_downloaded_apps", "audiencia": "general", "categoria": "tech",
     "titulo": "Top 10 most downloaded apps · 2015-2026",
     "fuente": "data.ai / Sensor Tower",
     "dataset_hint": "TikTok, Instagram, WhatsApp, Facebook — yearly downloads",
     "cifra_ancla": "million downloads"},
    {"key": "nba_scorers", "audiencia": "sports", "categoria": "sports",
     "titulo": "Top 15 NBA all-time scorers",
     "fuente": "NBA official statistics",
     "dataset_hint": "LeBron James, Kareem, Karl Malone, Kobe — career points",
     "cifra_ancla": "career points"},
    {"key": "most_streamed_spotify", "audiencia": "general", "categoria": "music",
     "titulo": "Top 10 most-streamed artists on Spotify · 2018-2026",
     "fuente": "Spotify Charts",
     "dataset_hint": "Bad Bunny, Taylor Swift, Drake, The Weeknd — total streams",
     "cifra_ancla": "billion streams"},
    {"key": "world_cup_winners", "audiencia": "sports", "categoria": "football",
     "titulo": "Top 10 countries by FIFA World Cup titles",
     "fuente": "FIFA official",
     "dataset_hint": "Brazil 5, Germany/Italy 4, Argentina 3 — titles over time",
     "cifra_ancla": "World Cup titles"},

    # ── Ampliación 28/09: +18 datasets evergreen verificables (no-YMYL) para que
    #    el canal no se agote (cooldown 90d). Cada dato lo genera+verifica el
    #    generador con fuente citada; aquí solo el spec del ranking.
    {"key": "highest_mountains", "audiencia": "general", "categoria": "geography",
     "titulo": "Top 10 highest mountains on Earth",
     "fuente": "Encyclopaedia Britannica / peakbagger",
     "dataset_hint": "Everest 8849, K2, Kangchenjunga, Lhotse, Makalu — height in metres",
     "cifra_ancla": "metres above sea level"},
    {"key": "longest_rivers", "audiencia": "general", "categoria": "geography",
     "titulo": "Top 10 longest rivers in the world",
     "fuente": "Encyclopaedia Britannica / USGS",
     "dataset_hint": "Nile, Amazon, Yangtze, Mississippi-Missouri — length in km",
     "cifra_ancla": "kilometres long"},
    {"key": "largest_countries_area", "audiencia": "general", "categoria": "geography",
     "titulo": "Top 10 largest countries by area",
     "fuente": "UN / CIA World Factbook",
     "dataset_hint": "Russia, Canada, USA, China, Brazil — area in million km²",
     "cifra_ancla": "million square kilometres"},
    {"key": "largest_lakes", "audiencia": "general", "categoria": "geography",
     "titulo": "Top 10 largest lakes in the world",
     "fuente": "Encyclopaedia Britannica",
     "dataset_hint": "Caspian Sea, Superior, Victoria, Huron — surface area",
     "cifra_ancla": "thousand square kilometres"},
    {"key": "grand_slams_men", "audiencia": "sports", "categoria": "tennis",
     "titulo": "Top 10 men's tennis Grand Slam titles · all-time",
     "fuente": "ATP / ITF official records",
     "dataset_hint": "Djokovic 24, Nadal 22, Federer 20 — singles majors",
     "cifra_ancla": "Grand Slam singles titles"},
    {"key": "grand_slams_women", "audiencia": "sports", "categoria": "tennis",
     "titulo": "Top 10 women's tennis Grand Slam titles · all-time",
     "fuente": "WTA / ITF official records",
     "dataset_hint": "Court 24, Graf 22, Serena Williams 23 — singles majors",
     "cifra_ancla": "Grand Slam singles titles"},
    {"key": "f1_race_wins", "audiencia": "sports", "categoria": "motorsport",
     "titulo": "Top 10 Formula 1 drivers by race wins",
     "fuente": "Formula1.com official statistics",
     "dataset_hint": "Hamilton, Schumacher, Verstappen, Vettel, Prost — Grand Prix wins",
     "cifra_ancla": "Grand Prix wins"},
    {"key": "nba_championships", "audiencia": "sports", "categoria": "sports",
     "titulo": "Top 10 NBA franchises by championships",
     "fuente": "NBA official records",
     "dataset_hint": "Celtics & Lakers 17+, Warriors, Bulls 6, Spurs 5 — titles",
     "cifra_ancla": "NBA championships"},
    {"key": "ballon_dor", "audiencia": "sports", "categoria": "football",
     "titulo": "Top 10 players by Ballon d'Or awards",
     "fuente": "France Football official",
     "dataset_hint": "Messi 8, Ronaldo 5, Platini/Cruyff/van Basten 3 — awards",
     "cifra_ancla": "Ballon d'Or awards"},
    {"key": "nobel_by_country", "audiencia": "general", "categoria": "society",
     "titulo": "Top 10 countries by Nobel Prizes",
     "fuente": "Nobel Foundation official",
     "dataset_hint": "USA, UK, Germany, France — total laureates by country",
     "cifra_ancla": "Nobel laureates"},
    {"key": "highest_paid_athletes", "audiencia": "sports", "categoria": "sports",
     "titulo": "Top 10 highest-paid athletes · recent year",
     "fuente": "Forbes highest-paid athletes",
     "dataset_hint": "Ronaldo, Messi, Mbappé, LeBron — annual earnings USD million",
     "cifra_ancla": "USD million per year"},
    {"key": "biggest_stadiums", "audiencia": "sports", "categoria": "sports",
     "titulo": "Top 10 biggest stadiums by capacity",
     "fuente": "Official stadium capacity records",
     "dataset_hint": "Rungrado 1st May, Narendra Modi, Michigan — seating capacity",
     "cifra_ancla": "seat capacity"},
    {"key": "expensive_transfers", "audiencia": "sports", "categoria": "football",
     "titulo": "Top 10 most expensive football transfers",
     "fuente": "Transfermarkt",
     "dataset_hint": "Neymar 222M, Mbappé, Coutinho, Dembélé — fee in EUR million",
     "cifra_ancla": "EUR million transfer fee"},
    {"key": "most_visited_museums", "audiencia": "general", "categoria": "culture",
     "titulo": "Top 10 most visited museums in the world",
     "fuente": "TEA / AECOM Museum Index",
     "dataset_hint": "Louvre, National Museum of China, Vatican, Met — annual visitors",
     "cifra_ancla": "million visitors per year"},
    {"key": "largest_airlines", "audiencia": "general", "categoria": "travel",
     "titulo": "Top 10 largest airlines by passengers",
     "fuente": "IATA / airline annual reports",
     "dataset_hint": "American, Delta, United, Ryanair, Southwest — passengers carried",
     "cifra_ancla": "million passengers per year"},
    {"key": "most_olympic_golds_athletes", "audiencia": "sports", "categoria": "sports",
     "titulo": "Top 10 Olympians by gold medals",
     "fuente": "IOC official history",
     "dataset_hint": "Michael Phelps 23, Latynina, Bjørndalen, Spitz — Olympic golds",
     "cifra_ancla": "Olympic gold medals"},
    {"key": "valuable_sports_teams", "audiencia": "sports", "categoria": "business",
     "titulo": "Top 10 most valuable sports teams",
     "fuente": "Forbes most valuable teams",
     "dataset_hint": "Cowboys, Warriors, Real Madrid, Yankees — valuation USD billion",
     "cifra_ancla": "USD billion valuation"},
    {"key": "longest_bridges", "audiencia": "general", "categoria": "engineering",
     "titulo": "Top 10 longest bridges in the world",
     "fuente": "Public engineering records",
     "dataset_hint": "Danyang–Kunshan, Changhua–Kaohsiung — total length in km",
     "cifra_ancla": "kilometres long"},
]


# ─────────────────────── refresher dinámico (LLM) ───────────────────────
# Los 25+18 fijos se agotan (cooldown 90d). El refresher pide a Gemini SPECS de
# rankings nuevos evergreen (NO datos — los datos los genera+verifica el generador
# al construir el vídeo). ACUMULA en disco (no sobrescribe) → el pool crece solo.
from datetime import datetime, timezone, timedelta  # noqa: E402
import json  # noqa: E402

from ..config import ROOT  # noqa: E402

DYNAMIC_PATH = ROOT / "output" / "dynamic_topics_rankings_en.json"
REFRESH_INTERVAL_DAYS = 7
MAX_DYNAMIC = 200  # cap del pool acumulado


def _load_dynamic() -> dict:
    if not DYNAMIC_PATH.exists():
        return {"generated_at": None, "topics": []}
    try:
        return json.loads(DYNAMIC_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"generated_at": None, "topics": []}


def _save_dynamic(data: dict) -> None:
    DYNAMIC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DYNAMIC_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _refresh_due() -> bool:
    gen = _load_dynamic().get("generated_at")
    if not gen:
        return True
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(gen)) > timedelta(days=REFRESH_INTERVAL_DAYS)
    except Exception:
        return True


def refresh_dynamic(n: int = 15) -> list[dict] | None:
    """Pide a Gemini N specs de rankings evergreen NUEVOS y los ACUMULA (dedup).

    Solo specs (key/titulo/fuente/dataset_hint/cifra_ancla). La veracidad de los
    NÚMEROS la garantiza el generador (fuente citada por dato + rechazo si no es
    verificable). Aquí exigimos: evergreen, fuente pública real, NO-YMYL.
    """
    existing = TOPICS + _load_dynamic().get("topics", [])
    existing_keys = {t.get("key") for t in existing}
    existing_titles = [" ".join((t.get("titulo") or "").split()) for t in existing if t.get("titulo")]
    avoid = "\n".join(f"- {t[:70]}" for t in existing_titles[:80])
    try:
        from google import genai
        from google.genai import types
        from ..config import gemini_key
        key = gemini_key()
        if not key:
            return None
        client = genai.Client(api_key=key)
        schema = {
            "type": "object",
            "properties": {"topics": {"type": "array", "items": {"type": "object", "properties": {
                "key": {"type": "string"}, "titulo": {"type": "string"},
                "categoria": {"type": "string"}, "audiencia": {"type": "string"},
                "fuente": {"type": "string"}, "dataset_hint": {"type": "string"},
                "cifra_ancla": {"type": "string"},
            }, "required": ["key", "titulo", "fuente", "dataset_hint", "cifra_ancla"]}}},
            "required": ["topics"],
        }
        prompt = (
            f"Propose {n} NEW ideas for an English 'bar chart race' ranking channel "
            f"(Top 10/15 evergreen global rankings).\n\n"
            f"STRICT RULES:\n"
            f"- Each ranking MUST have a real, citable PUBLIC source (World Bank, UN, IMF, "
            f"Forbes, FIFA, IOC, UEFA, ATP, Box Office Mojo, Statista, Britannica, official "
            f"federations/records). Name it in 'fuente'.\n"
            f"- Evergreen and factual only. NO YMYL: no health, medicine, politics/elections, "
            f"crypto, investing advice, or anything defamatory.\n"
            f"- Prefer rankings whose numbers are widely published and stable.\n"
            f"- Do NOT repeat or closely resemble these existing rankings:\n{avoid}\n\n"
            f"For each output: key (snake_case, unique), titulo (English, e.g. "
            f"'Top 10 ... · <year range>'), categoria (one word), audiencia ('general' or 'sports'), "
            f"fuente (the real source), dataset_hint (5-8 concrete example entries + the metric), "
            f"cifra_ancla (the unit, e.g. 'USD billion', 'metres', 'titles')."
        )
        resp = client.models.generate_content(
            model="gemini-3.5-flash-lite", contents=prompt,
            config=types.GenerateContentConfig(temperature=1.0, max_output_tokens=6000,
                                               response_mime_type="application/json", response_schema=schema),
        )
        got = json.loads((resp.text or "").strip()).get("topics", [])
        # dedup por key + por título (semántico) contra lo existente
        fresh: list[dict] = []
        try:
            from .. import dedup_common
            _isrep = lambda t: dedup_common.title_is_repeat(  # noqa: E731
                " ".join((t.get("titulo") or "").split()), existing_titles)
        except Exception:
            _isrep = lambda t: False  # noqa: E731
        seen = set(existing_keys)
        for t in got:
            k = (t.get("key") or "").strip()
            if not k or k in seen or not t.get("titulo") or not t.get("fuente"):
                continue
            if _isrep(t):
                continue
            seen.add(k)
            fresh.append(t)
        if not fresh:
            print("  rankings-en topics: 0 specs nuevos válidos")
            return None
        acc = (_load_dynamic().get("topics", []) + fresh)[-MAX_DYNAMIC:]
        _save_dynamic({"generated_at": datetime.now(timezone.utc).isoformat(), "topics": acc})
        print(f"  rankings-en topics: ✅ +{len(fresh)} specs (pool dinámico={len(acc)})")
        return fresh
    except Exception as e:
        print(f"  rankings-en topics refresh fail: {type(e).__name__}: {e}")
        return None


def all_topics() -> list[dict]:
    """Pool completo (25+18 fijos + dinámicos acumulados). Auto-refresca cada 7d."""
    if _refresh_due():
        refresh_dynamic()
    static = list(TOPICS)
    seen = {t["key"] for t in static}
    dyn = [t for t in _load_dynamic().get("topics", []) if t.get("key") and t["key"] not in seen]
    return static + dyn


def by_key(key: str) -> dict | None:
    for t in all_topics():
        if t["key"] == key:
            return t
    return None
