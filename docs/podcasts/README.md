# WaitWhy — Estafas Españolas (Podcast)

Feed RSS de podcast generado automáticamente a partir de los long-form del canal YouTube [@waitwhy_ybb](https://youtube.com/@waitwhy_ybb).

- **Feed URL público:** `https://yassinebhk.github.io/automated-videos/podcasts/feed.xml`
- **Cover art:** `cover.jpg` (1400×1400, requisito Apple/Spotify)
- **Episodios:** `<slug>.mp3` + `<slug>.json` (metadata)

## Alta en plataformas — one-time setup (30 min total)

### 1. Activar GitHub Pages (2 min)

En GitHub: `Settings` → `Pages` → Source: `Deploy from a branch` → Branch: `main`, folder: `/docs`. Guarda. La URL pública será `https://yassinebhk.github.io/automated-videos/podcasts/feed.xml` en <5 min.

Verifica que carga: `curl https://yassinebhk.github.io/automated-videos/podcasts/feed.xml` debe devolver XML.

### 2. Spotify Podcasters (10 min)

1. Ve a [podcasters.spotify.com](https://podcasters.spotify.com) → *Get started* → *Import RSS feed*.
2. Pega la Feed URL del paso 1.
3. Rellena categoría: **True Crime**. Idioma: **Español (España)**.
4. Verifica el email `waitwhy.podcast@gmail.com` (o cambia el email en `PODCAST_META` de `podcast_feed.py` a uno que uses).
5. Send for review. Aprobación: 24-72h.

### 3. Apple Podcasts Connect (10 min)

1. Ve a [podcastsconnect.apple.com](https://podcastsconnect.apple.com) (requiere Apple ID — gratis).
2. Click `+` → *Add RSS Feed URL*.
3. Pega la Feed URL. Verifica.
4. Rellena metadata (categoría iTunes: **True Crime**, idioma: **Spanish (Spain)**).
5. Submit. Aprobación: 3-10 días.

### 4. Google Podcasts / YouTube Music (bonus, 5 min)

- Google Podcasts está sunset desde 2024 → sus feeds migraron a YouTube Music.
- YouTube Music ya distribuye podcasts automáticamente si el canal está monetizado. Nada que hacer.

### 5. iVoox (opcional, 5 min) — audiencia española

- iVoox es el líder de podcast en España. [iVoox Creators](https://www.ivoox.com/podcast/soypodcaster).
- Import RSS feed + subir cover art. Aprobación instantánea.

## Cómo funciona el sistema

- Cada domingo/miércoles el long-form genera → publica en YT → **automáticamente añade el episodio a este feed** (voz Kokoro TTS + metadata judicial).
- El commit del workflow `videogen-bot` pushea el nuevo `<slug>.mp3` + `<slug>.json` + `feed.xml` actualizado.
- Spotify/Apple hacen polling del feed cada ~6-12h y publican los episodios nuevos sin intervención.

## Cambiar el cover / metadata del podcast

- Edita `src/videogen/podcast_feed.py` → `PODCAST_META`.
- Sustituye `cover.jpg` por una imagen 1400×1400 (o mayor, cuadrada) en JPG/PNG.
- Commit + push. Spotify recoge el cambio en 24h.
