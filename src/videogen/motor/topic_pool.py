"""Pool motor 2ª mano ES. Comparativas, fallos comunes, precios, guía compra."""
from __future__ import annotations


TOPICS = [
    # ─── TOP MODELOS BARATOS ───
    {"key": "top_5000", "audiencia": "compradores", "categoria": "top",
     "titulo": "TOP 5 coches 2ª mano por menos de €5.000 en 2026",
     "hook": "Fiat Panda, Renault Clio II, Ford Fiesta, Opel Corsa, Toyota Aygo",
     "cifra_ancla": "<€5.000"},

    {"key": "top_10000", "audiencia": "compradores", "categoria": "top",
     "titulo": "TOP 5 coches 2ª mano por menos de €10.000 (fiables)",
     "hook": "Toyota Auris, Mazda 3, Ford Focus, Honda Civic, Kia Ceed",
     "cifra_ancla": "<€10.000"},

    {"key": "top_familiar", "audiencia": "compradores", "categoria": "top",
     "titulo": "TOP 5 monovolúmenes 2ª mano familia numerosa <€12.000",
     "hook": "7 plazas, maletero grande, consumo bajo, fiabilidad",
     "cifra_ancla": "<€12.000 · 7 plazas"},

    # ─── DIESEL / HÍBRIDO / ELÉCTRICO ───
    {"key": "diesel_ban_2035", "audiencia": "compradores", "categoria": "guia",
     "titulo": "Diesel 2ª mano 2026: ¿vale la pena o va al desguace?",
     "hook": "ETIQUETA ambiental, Madrid Central, ZBE ciudades, 2035 UE",
     "cifra_ancla": "prohibido 2035 UE"},

    {"key": "hibrido_precio", "audiencia": "compradores", "categoria": "guia",
     "titulo": "TOP 5 híbridos 2ª mano <€15.000 en 2026",
     "hook": "Toyota Prius, Auris, Yaris, Honda Insight, Hyundai Ioniq",
     "cifra_ancla": "<€15.000 · etiqueta ECO"},

    {"key": "electrico_usado", "audiencia": "compradores", "categoria": "guia",
     "titulo": "Coche eléctrico 2ª mano: 3 cosas que TIENES que revisar",
     "hook": "Salud batería (SoH), garantía batería, actualizaciones OTA",
     "cifra_ancla": "SoH >80% obligatorio"},

    # ─── FALLOS COMUNES POR MODELO ───
    {"key": "fallo_audi_a3", "audiencia": "propietarios", "categoria": "fallos",
     "titulo": "3 fallos comunes Audi A3 2.0 TDI que TE arruinan",
     "hook": "Volante bimasa, EGR, inyectores — coste medio",
     "cifra_ancla": "€1.500-€3.000 reparación"},

    {"key": "fallo_bmw", "audiencia": "propietarios", "categoria": "fallos",
     "titulo": "3 fallos BMW diesel 320d año 2010-2015 caros",
     "hook": "Cadena distribución, turbo, EGR — precio taller oficial",
     "cifra_ancla": "€2k-€5k reparación"},

    {"key": "fallo_renault", "audiencia": "propietarios", "categoria": "fallos",
     "titulo": "TOP 3 fallos Renault Megane que te dejan tirado",
     "hook": "Válvula EGR, embrague, cristal quemacocos",
     "cifra_ancla": "€800-€2.500 taller"},

    # ─── COMPRAR / NEGOCIAR ───
    {"key": "compra_5_pasos", "audiencia": "compradores", "categoria": "guia",
     "titulo": "TOP 5 pasos para comprar 2ª mano SIN engaños en 2026",
     "hook": "Peritaje independiente, historial DGT, ITV, contrato, transfer",
     "cifra_ancla": "€60-€150 peritaje ahorra €1000+"},

    {"key": "compra_particular_vs", "audiencia": "compradores", "categoria": "guia",
     "titulo": "Compra particular vs concesionario: diferencias reales",
     "hook": "Garantía, IVA, precio, procedimiento tras venta",
     "cifra_ancla": "1 año garantía profesional"},

    {"key": "compra_km0", "audiencia": "compradores", "categoria": "guia",
     "titulo": "Coche KM0 en 2026: ventaja o trampa comercial",
     "hook": "Matriculación previa, descuento 15-25%, revalorización",
     "cifra_ancla": "15-25% descuento vs nuevo"},

    # ─── MANTENIMIENTO ───
    {"key": "mant_revisiones", "audiencia": "propietarios", "categoria": "mantenimiento",
     "titulo": "TOP 5 revisiones que TE OBLIGAN cada X km",
     "hook": "Aceite, filtros, distribución, embrague, frenos",
     "cifra_ancla": "€300-€1.500 revisión completa"},

    {"key": "mant_aceite", "audiencia": "propietarios", "categoria": "mantenimiento",
     "titulo": "Cambio aceite: cada 15.000km oficial vs cada 8k real 2ª mano",
     "hook": "Diferencia diesel/gasolina, riesgo saltarse, coste medio",
     "cifra_ancla": "€60-€120 cambio"},

    {"key": "mant_distribucion", "audiencia": "propietarios", "categoria": "mantenimiento",
     "titulo": "Correa distribución: si se rompe, motor destrozado",
     "hook": "Cambio 60-120k km, cadena vs correa, coste",
     "cifra_ancla": "€300-€800 · motor €5k si rompe"},

    # ─── ITV Y LEGAL ───
    {"key": "itv_fallos", "audiencia": "propietarios", "categoria": "legal",
     "titulo": "TOP 5 fallos que TE tiran la ITV 2026",
     "hook": "Luces, frenos, gases, holguras, sospechosos manipulación",
     "cifra_ancla": "€60 reITV en 2 meses"},

    {"key": "impuesto_circ", "audiencia": "propietarios", "categoria": "legal",
     "titulo": "Impuesto circulación 2026: por qué en Madrid pagas 5× más que en Melilla",
     "hook": "Ayuntamiento fija, tramos CV, cambio empadronamiento",
     "cifra_ancla": "€25-€250/año según municipio"},

    # ─── PRECIOS DE MERCADO ───
    {"key": "precio_mercado", "audiencia": "compradores", "categoria": "guia",
     "titulo": "3 webs GRATIS para saber si un 2ª mano está caro 2026",
     "hook": "Coches.net valorador, Ganvam, portal DGT",
     "cifra_ancla": "diferencia €500-€3.000 vs mercado"},

    {"key": "coches_venden_rapido", "audiencia": "vendedores", "categoria": "guia",
     "titulo": "TOP 5 coches 2ª mano que se venden en <15 días 2026",
     "hook": "SUV compactos, japoneses fiables, híbridos, precio ajustado",
     "cifra_ancla": "<15 días venta media"},

    # ─── FINANCIACIÓN 2ª MANO ───
    {"key": "fin_financiar", "audiencia": "compradores", "categoria": "guia",
     "titulo": "Financiar 2ª mano en 2026: TAE 8-12% típico",
     "hook": "Bancos vs concesionario vs cooperativas, cuota, entrada",
     "cifra_ancla": "8-12% TAE"},

    # ─── COCHES ELÉCTRICOS USADOS PRO ───
    {"key": "electr_tesla_usado", "audiencia": "compradores", "categoria": "guia",
     "titulo": "Tesla Model 3 usado 2026: precios y qué revisar",
     "hook": "Autopilot vs FSD, SoH batería, coste servicio",
     "cifra_ancla": "€22.000-€35.000 usado"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
