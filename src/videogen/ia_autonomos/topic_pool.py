"""Pool de temas 'IA para autónomos ES' — Shorts <60s.

Categorías: automatización, marketing, admin, atención al cliente,
finanzas. Datos verificables con herramientas gratuitas o freemium
(cero suscripción obligatoria — coherente con veracidad + coste cero).

Rotación: ledger `output/ia_autonomos_ledger.json` marca usados;
cooldown 90 días para revisitar con dato actualizado.
"""
from __future__ import annotations


TOPICS = [
    # ─── AUTOMATIZACIÓN TRABAJO REPETITIVO ───
    {"key": "auto_facturas_pdf_a_excel", "audiencia": "autonomos",
     "categoria": "automatizacion",
     "titulo": "Extrae datos de 100 facturas PDF a Excel en 2 min con IA (gratis)",
     "hook": "ChatGPT + Data Analyst / Claude / Gemini con vision — proceso mensual sin gestoría",
     "cifra_ancla": "2h → 2 min"},

    {"key": "auto_email_borradores", "audiencia": "autonomos",
     "categoria": "automatizacion",
     "titulo": "IA responde 80% de tus emails en <30s — el truco de las plantillas",
     "hook": "Gmail Smart Compose + ChatGPT Custom Instructions para tu tono",
     "cifra_ancla": "15h/mes ahorradas"},

    {"key": "auto_transcripcion_reuniones", "audiencia": "autonomos",
     "categoria": "automatizacion",
     "titulo": "Transcribe cualquier reunión gratis (Whisper local o Google Meet Notes)",
     "hook": "Whisper OpenAI open-source o Google Meet transcripción nativa gratuita",
     "cifra_ancla": "€0 en 5 min"},

    {"key": "auto_agendar_citas_ia", "audiencia": "autonomos",
     "categoria": "automatizacion",
     "titulo": "Bot IA agenda tus citas por WhatsApp mientras duermes (Cal.com gratis)",
     "hook": "Cal.com free + integración WhatsApp Business API + IA para respuestas",
     "cifra_ancla": "24/7 sin coste"},

    # ─── MARKETING Y VENTAS ───
    {"key": "mkt_5_ideas_contenido_dia", "audiencia": "autonomos",
     "categoria": "marketing",
     "titulo": "Genera 5 ideas de contenido para RRSS/día con IA gratis (proceso 10 min)",
     "hook": "Prompt template + Google Trends + Gemini/Claude free",
     "cifra_ancla": "5 ideas · 10 min"},

    {"key": "mkt_seo_articulos_gratis", "audiencia": "autonomos",
     "categoria": "marketing",
     "titulo": "Escribe 4 artículos SEO/mes gratis con IA — mejor que agencia €500/mes",
     "hook": "Claude/Gemini con brief SEO + investigación keywords Google + validación real",
     "cifra_ancla": "€500/mes ahorrados"},

    {"key": "mkt_video_shorts_ia", "audiencia": "autonomos",
     "categoria": "marketing",
     "titulo": "Crea Shorts profesionales sin editar — Runway free + CapCut IA",
     "hook": "Runway free tier 125 créditos + CapCut IA (recorte + subs auto) — todo gratis",
     "cifra_ancla": "0€ · 10 Shorts/día"},

    {"key": "mkt_traducir_todo_gratis", "audiencia": "autonomos",
     "categoria": "marketing",
     "titulo": "Traduce tu web a 20 idiomas gratis (calidad humana) con DeepL/Gemini",
     "hook": "DeepL free 500k chars/mes + Gemini para revisión localizada",
     "cifra_ancla": "20 idiomas · €0"},

    # ─── ADMINISTRACIÓN Y CONTABILIDAD ───
    {"key": "admin_ia_leer_contratos", "audiencia": "autonomos",
     "categoria": "administracion",
     "titulo": "Sube tu contrato a Claude y detecta cláusulas abusivas en 30s",
     "hook": "Upload PDF a Claude/Gemini + prompt específico jurídico → señala riesgos",
     "cifra_ancla": "30s · €0"},

    {"key": "admin_ia_hojas_calculo", "audiencia": "autonomos",
     "categoria": "administracion",
     "titulo": "Google Sheets + Gemini = analista de datos automático (fórmulas y gráficos)",
     "hook": "Menú Extensiones → Gemini nativo en Sheets/Docs — gratis con cuenta Google",
     "cifra_ancla": "0€ integrado"},

    {"key": "admin_ia_conciliacion_bancaria", "audiencia": "autonomos",
     "categoria": "administracion",
     "titulo": "IA concilia extractos bancarios con tus facturas en 5 min (proceso mensual)",
     "hook": "Export CSV banco + prompt Claude/Gemini para match automático",
     "cifra_ancla": "3h → 5 min"},

    # ─── ATENCIÓN AL CLIENTE ───
    {"key": "cs_chatbot_web_gratis", "audiencia": "autonomos",
     "categoria": "atencion_cliente",
     "titulo": "Chatbot IA en tu web en 15 min sin código (Chatbase free / Tidio)",
     "hook": "Chatbase free 30 msg/mes + tu URL como fuente = FAQ automática",
     "cifra_ancla": "15 min setup"},

    {"key": "cs_respuestas_reseñas_ia", "audiencia": "autonomos",
     "categoria": "atencion_cliente",
     "titulo": "Responde 50 reseñas Google en 10 min con IA (sin sonar robótico)",
     "hook": "Copiar reseña + prompt personalizado tu tono → respuesta única cada vez",
     "cifra_ancla": "5h → 10 min"},

    # ─── FINANZAS Y ANÁLISIS ───
    {"key": "fin_prever_ingresos_ia", "audiencia": "autonomos",
     "categoria": "finanzas",
     "titulo": "IA predice tus ingresos del próximo trimestre con tus datos históricos",
     "hook": "Sube tu Excel de facturación a Claude → forecast con estacionalidad",
     "cifra_ancla": "±10% precisión"},

    {"key": "fin_analizar_gastos_ia", "audiencia": "autonomos",
     "categoria": "finanzas",
     "titulo": "Sube extracto bancario a IA y descubre dónde se te van €500/mes",
     "hook": "PDF/CSV bancario → Gemini analiza patrones + señala fugas",
     "cifra_ancla": "€500/mes detectados"},

    {"key": "fin_optimizar_precios_ia", "audiencia": "autonomos",
     "categoria": "finanzas",
     "titulo": "Ajusta tus precios con IA — cuánto puedes subir sin perder clientes",
     "hook": "Prompt con margen actual + competencia + elasticidad → recomendación",
     "cifra_ancla": "+12% margen medio"},

    # ─── PYMES (audiencia secundaria) ───
    {"key": "pyme_ia_rrhh_cvs", "audiencia": "pymes",
     "categoria": "administracion",
     "titulo": "Filtra 200 CVs en 10 min con IA (LinkedIn + Claude/Gemini)",
     "hook": "Exportar CVs a texto + prompt criterios objetivos → top 10 ranked",
     "cifra_ancla": "200 CVs · 10 min"},

    {"key": "pyme_ia_generar_landings", "audiencia": "pymes",
     "categoria": "marketing",
     "titulo": "Crea landing pages profesionales con IA en 20 min (Framer/Wix free)",
     "hook": "Framer AI free / Wix ADI + copy IA → landing lista sin diseñador",
     "cifra_ancla": "20 min · €0"},

    {"key": "pyme_ia_atender_llamadas", "audiencia": "pymes",
     "categoria": "atencion_cliente",
     "titulo": "IA atiende tus llamadas fuera de horario en español (Vapi free tier)",
     "hook": "Vapi free 10 min/mes + voz natural español + integración con CRM",
     "cifra_ancla": "24/7 · €0 inicial"},

    {"key": "pyme_documentar_procesos_ia", "audiencia": "pymes",
     "categoria": "administracion",
     "titulo": "Documenta procesos internos con Loom + IA — onboarding 3× más rápido",
     "hook": "Loom free 25 vids + transcripción → IA convierte en manual paso a paso",
     "cifra_ancla": "3× más rápido"},
]


def all_topics() -> list[dict]:
    return list(TOPICS)
