# videogen

Pipeline automatizado para generar videos de "curiosidades" con IA y publicarlos en YouTube Shorts + TikTok (versión ES y EN del mismo prompt).

## Flujo

```
$ videogen create "¿Por qué los pulpos tienen 3 corazones?"
  → Claude genera script bilingüe (hook + body + cta) en JSON
  → ElevenLabs sintetiza voz ES + EN con timestamps por palabra
  → Pexels descarga B-roll matching visual_keywords
  → ffmpeg compone 9:16 (Shorts/TikTok) y opcional 16:9 (YT long)
  → Output en output/pending_review/<slug>/

$ videogen review <slug>
  → Abre la carpeta para previsualizar los MP4

$ videogen publish <slug> --platform youtube,tiktok --lang es,en
  → YouTube: upload automático vía Data API v3
  → TikTok: abre el desktop uploader con el archivo listo
```

## Prerequisitos

- Python 3.11+
- **ffmpeg** instalado (`brew install ffmpeg` en macOS)
- API keys (ver `.env.example`):
  - Anthropic (script)
  - ElevenLabs (voz)
  - Pexels (B-roll, gratis)
  - Google Cloud OAuth credentials (YouTube)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # rellena las keys
mkdir -p secrets
# Descarga youtube_client_secret.json del Google Cloud Console → ./secrets/
```

## Estrategia del canal

- **Nicho**: paraguas de curiosidades ("¿Por qué...?", "¿Cómo funciona...?", "¿Qué pasa si...?")
- **Formato**: 60s vertical 9:16, captions word-by-word burned-in, voz IA con personalidad consistente
- **Cadencia**: 1 video/día por idioma (no más — patrón anti-AI-slop)
- **Defensa contra crackdown**: cada video tiene revisión humana antes de subir, prompt único, ángulo editorial visible
