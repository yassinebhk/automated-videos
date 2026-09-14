"""Pool de temas para AI Tools Weekly EN — Shorts formato "Top 5 AI tools for X".

Cada topic = 1 short de lista con 5 herramientas IA REALES (campo `tools`).
Suministrar las herramientas explícitamente ancla la veracidad: el guionista
usa exactamente esas (todas existen en 2026), no inventa nombres/features.

Campos (compatibles con topic_refresher para el merge dinámico):
- key         : slug único snake_case
- audiencia   : creators | developers | marketers | students | business | designers | general
- categoria   : writing | image | video | coding | audio | productivity | research |
                marketing | design | presentations | meetings | automation | agents |
                data | seo | study | careers | social | email | notes | spreadsheets |
                youtube | free | transcription | translation
- titulo      : "Top 5 AI tools for X" (EN, 45-70 chars)
- hook        : gancho EN 0-3s
- cifra_ancla : ancla VERIFICABLE y suave (ej. "all have free tiers") — nunca stat inventado
- tools       : lista de 5 herramientas reales (solo pool estático; los dinámicos las eligen
                bajo las reglas de veracidad del system prompt)

Rotación: ledger output/aitools_ledger.json (cooldown 90 días) + refresh dinámico
quincenal (ai_tools.topic_refresher) — anti-repetition del algoritmo YT 2026.
"""
from __future__ import annotations


TOPICS = [
    # ─── WRITING ───
    {"key": "writing_general", "audiencia": "creators", "categoria": "writing",
     "titulo": "Top 5 AI writing tools (all free to start)",
     "hook": "You are still writing everything from scratch? These 5 do it in seconds.",
     "cifra_ancla": "all have free tiers",
     "tools": ["ChatGPT", "Claude", "Jasper", "Grammarly", "Notion AI"]},

    # ─── IMAGE GENERATION ───
    {"key": "image_generation", "audiencia": "designers", "categoria": "image",
     "titulo": "Top 5 AI image generators in 2026",
     "hook": "Type a sentence, get a pro-level image. Here are the 5 best.",
     "cifra_ancla": "3 have free tiers",
     "tools": ["Midjourney", "DALL·E 3", "Stable Diffusion", "Leonardo AI", "Adobe Firefly"]},

    # ─── VIDEO GENERATION ───
    {"key": "video_generation", "audiencia": "creators", "categoria": "video",
     "titulo": "Top 5 AI video tools for creators",
     "hook": "Make videos without a camera. These 5 tools do the work.",
     "cifra_ancla": "free trials available",
     "tools": ["Runway", "Pika", "Synthesia", "HeyGen", "Descript"]},

    # ─── CODING ───
    {"key": "coding_assistants", "audiencia": "developers", "categoria": "coding",
     "titulo": "Top 5 AI coding assistants for developers",
     "hook": "These 5 AI tools write, fix and explain your code.",
     "cifra_ancla": "most have free tiers",
     "tools": ["GitHub Copilot", "Cursor", "Claude Code", "Codeium", "Tabnine"]},

    # ─── AUDIO / VOICE / MUSIC ───
    {"key": "audio_voice", "audiencia": "creators", "categoria": "audio",
     "titulo": "Top 5 AI audio & voice tools",
     "hook": "Clone a voice, make a song, clean up audio — 5 tools that do it.",
     "cifra_ancla": "free credits to start",
     "tools": ["ElevenLabs", "Murf", "Suno", "Udio", "Adobe Podcast"]},

    # ─── PRODUCTIVITY ───
    {"key": "productivity", "audiencia": "business", "categoria": "productivity",
     "titulo": "Top 5 AI productivity tools to save hours",
     "hook": "Stop doing busywork. These 5 AI tools plan your day for you.",
     "cifra_ancla": "free plans available",
     "tools": ["Notion AI", "Motion", "Reclaim AI", "Mem", "Todoist"]},

    # ─── RESEARCH ───
    {"key": "research", "audiencia": "students", "categoria": "research",
     "titulo": "Top 5 AI research tools (cite real sources)",
     "hook": "These 5 tools read papers and cite sources — no more guessing.",
     "cifra_ancla": "all free to try",
     "tools": ["Perplexity", "Elicit", "Consensus", "ChatPDF", "SciSpace"]},

    # ─── MARKETING ───
    {"key": "marketing", "audiencia": "marketers", "categoria": "marketing",
     "titulo": "Top 5 AI marketing tools that actually work",
     "hook": "Write ads, emails and posts on autopilot with these 5.",
     "cifra_ancla": "free trials available",
     "tools": ["Jasper", "Copy.ai", "HubSpot AI", "Surfer SEO", "Ocoya"]},

    # ─── DESIGN ───
    {"key": "design", "audiencia": "designers", "categoria": "design",
     "titulo": "Top 5 AI design tools for non-designers",
     "hook": "No design skills? These 5 AI tools make it look pro.",
     "cifra_ancla": "free tiers available",
     "tools": ["Canva Magic Studio", "Figma AI", "Framer AI", "Uizard", "Recraft"]},

    # ─── PRESENTATIONS ───
    {"key": "presentations", "audiencia": "business", "categoria": "presentations",
     "titulo": "Top 5 AI tools to build slides in minutes",
     "hook": "Turn one prompt into a full deck. These 5 do it fast.",
     "cifra_ancla": "free plans available",
     "tools": ["Gamma", "Tome", "Beautiful.ai", "Plus AI", "SlidesAI"]},

    # ─── MEETINGS ───
    {"key": "meetings", "audiencia": "business", "categoria": "meetings",
     "titulo": "Top 5 AI meeting assistants (auto notes)",
     "hook": "Never take meeting notes again. These 5 do it for you.",
     "cifra_ancla": "free tiers available",
     "tools": ["Otter.ai", "Fireflies", "Fathom", "tl;dv", "Krisp"]},

    # ─── AUTOMATION ───
    {"key": "automation", "audiencia": "business", "categoria": "automation",
     "titulo": "Top 5 AI automation tools (no code)",
     "hook": "Connect your apps and let AI run the busywork. Top 5 no-code tools.",
     "cifra_ancla": "free plans available",
     "tools": ["Zapier AI", "Make", "n8n", "Bardeen", "Relay.app"]},

    # ─── CHATBOTS / AGENTS ───
    {"key": "chatbots_agents", "audiencia": "general", "categoria": "agents",
     "titulo": "Top 5 AI chatbots compared in 2026",
     "hook": "ChatGPT vs the rest — which AI assistant actually wins?",
     "cifra_ancla": "all free to try",
     "tools": ["ChatGPT", "Claude", "Gemini", "Perplexity", "Poe"]},

    # ─── DATA / ANALYTICS ───
    {"key": "data_analysis", "audiencia": "business", "categoria": "data",
     "titulo": "Top 5 AI tools to analyze data (no formulas)",
     "hook": "Drop a spreadsheet, ask a question, get charts. These 5 do it.",
     "cifra_ancla": "free tiers available",
     "tools": ["Julius AI", "ChatGPT", "Rows", "Powerdrill", "Akkio"]},

    # ─── SEO ───
    {"key": "seo", "audiencia": "marketers", "categoria": "seo",
     "titulo": "Top 5 AI SEO tools to rank on Google",
     "hook": "These 5 AI tools tell you exactly what to write to rank.",
     "cifra_ancla": "free trials available",
     "tools": ["Surfer SEO", "Frase", "SE Ranking", "Clearscope", "NeuronWriter"]},

    # ─── STUDY / STUDENTS ───
    {"key": "study", "audiencia": "students", "categoria": "study",
     "titulo": "Top 5 AI study tools for students",
     "hook": "Study smarter, not longer — these 5 AI tools help you learn fast.",
     "cifra_ancla": "all free to start",
     "tools": ["ChatGPT", "NotebookLM", "Quizlet", "Grammarly", "Perplexity"]},

    # ─── CAREERS / RESUME ───
    {"key": "resume_jobs", "audiencia": "general", "categoria": "careers",
     "titulo": "Top 5 AI tools to land your next job",
     "hook": "Build a resume that beats the bots with these 5 AI tools.",
     "cifra_ancla": "free plans available",
     "tools": ["Teal", "Kickresume", "Rezi", "Enhancv", "LinkedIn AI"]},

    # ─── SOCIAL MEDIA ───
    {"key": "social_media", "audiencia": "creators", "categoria": "social",
     "titulo": "Top 5 AI tools to grow on social media",
     "hook": "Post every day without burning out — these 5 AI tools help.",
     "cifra_ancla": "free trials available",
     "tools": ["Ocoya", "Buffer AI", "Vista Social", "Predis.ai", "FeedHive"]},

    # ─── EMAIL ───
    {"key": "email", "audiencia": "business", "categoria": "email",
     "titulo": "Top 5 AI tools to master your inbox",
     "hook": "Clear your inbox in minutes with these 5 AI email tools.",
     "cifra_ancla": "free tiers available",
     "tools": ["Superhuman", "Shortwave", "Gmail Gemini", "Missive", "Flowrite"]},

    # ─── NOTE-TAKING ───
    {"key": "notes", "audiencia": "students", "categoria": "notes",
     "titulo": "Top 5 AI note-taking tools in 2026",
     "hook": "Turn messy notes into clear summaries with these 5 tools.",
     "cifra_ancla": "all free to start",
     "tools": ["NotebookLM", "Mem", "Notion AI", "Reflect", "Obsidian"]},

    # ─── SPREADSHEETS / EXCEL ───
    {"key": "spreadsheets", "audiencia": "business", "categoria": "spreadsheets",
     "titulo": "Top 5 AI tools for Excel & spreadsheets",
     "hook": "Never fight a formula again — these 5 AI tools write them for you.",
     "cifra_ancla": "free tiers available",
     "tools": ["ChatGPT", "Rows", "Formula Bot", "SheetAI", "Excel Copilot"]},

    # ─── YOUTUBE / THUMBNAILS ───
    {"key": "youtube_tools", "audiencia": "creators", "categoria": "youtube",
     "titulo": "Top 5 AI tools every YouTuber needs",
     "hook": "Titles, thumbnails, tags — these 5 AI tools do it all.",
     "cifra_ancla": "free plans available",
     "tools": ["VidIQ", "TubeBuddy", "Canva", "Pikzels", "Opus Clip"]},

    # ─── FREE TOOLS (NO SIGNUP) ───
    {"key": "free_no_signup", "audiencia": "general", "categoria": "free",
     "titulo": "Top 5 free AI tools (no credit card)",
     "hook": "The best AI tools that cost you nothing — no card needed.",
     "cifra_ancla": "100% free to use",
     "tools": ["ChatGPT", "Claude", "Perplexity", "Gemini", "Pollinations"]},

    # ─── TRANSCRIPTION ───
    {"key": "transcription", "audiencia": "creators", "categoria": "transcription",
     "titulo": "Top 5 AI transcription tools (audio to text)",
     "hook": "Turn any audio into text in seconds with these 5 tools.",
     "cifra_ancla": "free minutes to start",
     "tools": ["Whisper", "Otter.ai", "Descript", "Rev", "Notta"]},

    # ─── TRANSLATION ───
    {"key": "translation", "audiencia": "general", "categoria": "translation",
     "titulo": "Top 5 AI translation tools that beat Google",
     "hook": "Translate like a native with these 5 AI tools.",
     "cifra_ancla": "free tiers available",
     "tools": ["DeepL", "Google Translate", "ChatGPT", "DeepL Write", "Reverso"]},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str) -> dict | None:
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None


def by_categoria(cat: str) -> list[dict]:
    return [t for t in TOPICS if t.get("categoria") == cat]
