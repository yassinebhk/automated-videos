"""Canal AI Tools Weekly EN — canal #10 (primer canal en inglés).

Nicho: reviews/tutorials de herramientas IA (CPM $12-25 EN vs $2-4 ES).
Formato: 1 Short/día "Top 5 AI tools for X" + 1 long-form semanal (~8 min).

Reusa 100% la infraestructura pesada de WaitWhy (service.generate/publish/
generate_long/publish_long, voice, compose, thumbnails) vía env overrides:
- SCRIPT_SYSTEM_PROMPT_FILE=ai_tools_en_system.md → guion en inglés, nicho AI tools
- YT_CHANNEL_PREFIX=YT_AITOOLS → creds YT_AITOOLS_REFRESH_TOKEN etc
- EDGE_VOICE_EN_AITOOLS=en-US-GuyNeural → voz tech con autoridad

Diferencias clave respecto a los canales ES (por diseño):
- Idioma = EN (langs=("en",)) — contenido nuevo desde cero, NUNCA traducción ES→EN.
- NO cross-postea a las RRSS ES (Bluesky/Mastodon/Threads/IG son marca ES/true crime).
  Solo YT + MP4 a Telegram para subida manual a TikTok (@interest_stuff).
- Pool rotativo con refresh dinámico propio (anti-repetition algoritmo YT 2026).

100% gratuito: Edge TTS (gratis, ilimitado) + Pollinations (hero IA gratis).
Veracidad: solo herramientas REALES existentes 2026, sin inventar features/precios,
disclaimer en descripción (ver prompts/ai_tools_en_system.md).
"""
