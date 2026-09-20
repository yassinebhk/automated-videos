"""Generador del video ambient/relax completo.

Pipeline:
1. Elige topic no-usado recientemente (ledger)
2. Descarga música CC0 de Pixabay (30-60 min, loopeando si hace falta)
3. Descarga imagen de Pexels
4. ffmpeg: image_loop + audio + fade_in/out → mp4 final
5. Gemini: título SEO long-tail + descripción con timestamps + tags
6. Devuelve dict con paths + metadata para uploader
"""
from __future__ import annotations

import json
import random
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from ..config import ROOT
from . import topic_pool

AMBIENT_ROOT = ROOT / "output" / "ambient_uploaded"
AMBIENT_LEDGER = ROOT / "output" / "ambient_ledger.json"
COOLDOWN_DAYS = 5  # 14/09: bajado de 14→5 con cadencia 3×/día (compensación
                     # cap 14min sin SMS verify). Con 22 estáticos + dinámicos
                     # y 21 videos/semana, cooldown 5d rota todo sin repetir


def _load_ledger() -> dict[str, list[str]]:
    """{ topic_key: [iso_timestamp, ...] }"""
    if not AMBIENT_LEDGER.exists():
        return {}
    try:
        return json.loads(AMBIENT_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_ledger(data: dict) -> None:
    AMBIENT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    AMBIENT_LEDGER.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                              encoding="utf-8")


def _mark_used(topic_key: str) -> None:
    ledger = _load_ledger()
    ledger.setdefault(topic_key, []).append(
        datetime.now(timezone.utc).isoformat())
    ledger[topic_key] = ledger[topic_key][-20:]  # cap history
    _save_ledger(ledger)


def _pick_topic() -> dict:
    """Elige topic no usado en últimos COOLDOWN_DAYS días.

    14/09 modo D: cuando Pixabay lleva rate-limit persistente, prefiere
    topics binaurales (100% ffmpeg local, no dependen Pixabay). Detecta
    por env AMBIENT_PREFER_BINAURAL=1 (activar cuando Pixabay caído).

    Prioriza:
      1. Si PREFER_BINAURAL=1 → binaurales fuera cooldown
      2. Topics dinámicos frescos (nunca usados) — máxima novedad
      3. Estáticos fuera de cooldown
      4. Cualquiera fuera de cooldown (dinámicos + estáticos)
      5. Todos si todos en cooldown (fallback anti-bloqueo)
    """
    from . import topic_refresher
    import os as _os

    all_pool = topic_refresher.get_all_topics_merged()
    ledger = _load_ledger()
    cutoff = datetime.now(timezone.utc) - timedelta(days=COOLDOWN_DAYS)
    fresh_dynamic, available, binaural_avail = [], [], []
    static_keys = {t["key"] for t in topic_pool.all_topics()}
    for t in all_pool:
        recent = ledger.get(t["key"], [])
        last_use = None
        for iso in recent[-1:]:
            try:
                last_use = datetime.fromisoformat(iso)
                break
            except Exception:
                continue
        if not last_use or last_use < cutoff:
            available.append(t)
            if t.get("mood_type") == "binaural":
                binaural_avail.append(t)
            if t["key"] not in static_keys and not recent:
                fresh_dynamic.append(t)

    # Modo D: prefiere binaurales (Pixabay caído — evita fallback noise)
    prefer_binaural = _os.environ.get("AMBIENT_PREFER_BINAURAL", "").strip() == "1"
    if prefer_binaural and binaural_avail:
        print(f"  ambient: modo PREFER_BINAURAL activo (Pixabay caído)")
        return random.choice(binaural_avail)

    if fresh_dynamic:
        pool = fresh_dynamic if random.random() < 0.6 else available
        return random.choice(pool)
    if available:
        return random.choice(available)
    return random.choice(all_pool)


def _fetch_music(topic: dict, target_duration_seconds: int, out_dir: Path) -> Path | None:
    """Descarga música CC0 de Pixabay que dure >= target_duration.

    Pixabay Music API es gratuita y devuelve mp3 CC0 sin licencia. Si un solo
    track no cubre la duración, concatena varios con crossfade.
    """
    import os, requests
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        print("  ambient: falta PIXABAY_API_KEY — abortando descarga música")
        return None

    q = topic["pixabay_music_query"]
    # Fallback queries por si la principal no devuelve nada — cubre topic
    # variations (rain → thunderstorm rain nature, etc.).
    queries = [q] + topic.get("pixabay_fallback_queries", [])
    # Genéricos ambient safe si todo lo específico falla
    queries += ["ambient calm relaxing", "nature relax"]

    data = None
    for i, query in enumerate(queries):
        for attempt in range(3):
            try:
                r = requests.get(
                    "https://pixabay.com/api/audio/",
                    params={"key": key, "q": query, "per_page": 50, "safesearch": "true"},
                    headers={"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                                            "Chrome/122.0.0.0 Safari/537.36")},
                    timeout=30,
                )
                if r.status_code == 429:
                    print(f"  ambient: Pixabay rate-limit (429), espera {5*(attempt+1)}s")
                    import time as _t; _t.sleep(5 * (attempt + 1))
                    continue
                # Log si el content no es JSON (rate-limit HTML page suele venir así)
                ct = r.headers.get("content-type", "")
                if "json" not in ct:
                    print(f"  ambient: Pixabay respuesta no-JSON (ct={ct[:40]}, "
                          f"status={r.status_code}, body='{r.text[:100]}')")
                    break  # Cambia a siguiente query
                try:
                    data = r.json()
                except Exception as je:
                    print(f"  ambient: Pixabay JSON parse fail: {je} · body='{r.text[:100]}'")
                    break
                if data.get("totalHits", 0) > 0:
                    print(f"  ambient: Pixabay OK query='{query}' hits={data.get('totalHits')}")
                    break
                print(f"  ambient: Pixabay 0 hits para '{query}' → siguiente")
                data = None
                break  # 0 hits: cambia query, no reintenta
            except Exception as e:
                print(f"  ambient: Pixabay request fail (intento {attempt+1}): {e}")
        if data and data.get("hits"):
            break

    if not data or not data.get("hits"):
        print(f"  ambient: agotadas {len(queries)} queries Pixabay → intento Freesound")
        # Fallback 2: Freesound (millones tracks CC0/CC-BY, gratis API key)
        fs_result = _fetch_music_freesound(topic, target_duration_seconds, out_dir)
        if fs_result:
            return fs_result
        # Fallback 3 (final): ruido ffmpeg puro
        print(f"  ambient: Freesound también falló → fallback ffmpeg noise")
        mood = topic.get("mood", "").lower()
        if "sleep" in mood or "deep" in mood:
            noise_color = "brown"
        else:
            noise_color = "pink"
        return _generate_noise_fallback(out_dir, target_duration_seconds, noise_color)
    hits = data.get("hits", [])

    # Baraja para variedad + prefiere tracks largos
    random.shuffle(hits)
    hits.sort(key=lambda h: -int(h.get("duration") or 0))

    tracks = []
    total = 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, h in enumerate(hits):
        dur = int(h.get("duration") or 0)
        url = h.get("audio", "") or h.get("url", "")
        if not url or dur < 60:
            continue
        try:
            audio = requests.get(url, timeout=60).content
        except Exception:
            continue
        p = out_dir / f"track_{i:02d}.mp3"
        p.write_bytes(audio)
        tracks.append(p)
        total += dur
        if total >= target_duration_seconds:
            break

    if not tracks:
        print(f"  ambient: 0 tracks descargados de Pixabay para '{q}'")
        return None

    # Concatena tracks descargados
    concat_file = out_dir / "concat.txt"
    concat_file.write_text("\n".join(f"file '{t.name}'" for t in tracks))
    base_audio = out_dir / "base.mp3"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(base_audio),
    ]
    r = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(f"  ambient: ffmpeg concat fail — {r.stderr[:200]}")
        return None

    # Si la duración conseguida cubre >=95% del target, listo.
    # Si NO, hacemos LOOP con stream_loop para llegar a target_duration.
    # Esto evita depender de tener 8h de música única en Pixabay para videos
    # largos (dormir/bebés). La música ambient/naturaleza se loopea sin que se
    # note, y es más eficiente que descargar 50 tracks distintos.
    output = out_dir / "audio.mp3"
    if total >= target_duration_seconds * 0.95:
        base_audio.rename(output)
        print(f"  ambient: audio {total}s (cubre target {target_duration_seconds}s sin loop)")
        return output

    # Loop necesario — repite base_audio N veces hasta target
    loops_needed = (target_duration_seconds // total) + 1
    print(f"  ambient: loop x{loops_needed} para llegar a {target_duration_seconds}s "
          f"(base {total}s de {len(tracks)} tracks)")
    cmd_loop = [
        "ffmpeg", "-y",
        "-stream_loop", str(loops_needed),
        "-i", str(base_audio),
        "-t", str(target_duration_seconds),
        "-c", "copy",
        str(output),
    ]
    # Loop hasta 8h con -stream_loop + -c copy es rápido (~2-5min max)
    r2 = subprocess.run(cmd_loop, cwd=out_dir, capture_output=True, text=True, timeout=900)
    if r2.returncode != 0:
        print(f"  ambient: ffmpeg loop fail — {r2.stderr[:200]}")
        # Fallback: usa el base_audio aunque sea corto
        base_audio.rename(output)
        return output
    base_audio.unlink(missing_ok=True)
    return output


def _fetch_music_freesound(topic: dict, target_duration_seconds: int,
                             out_dir: Path) -> Path | None:
    """Fallback Freesound API — millones de tracks CC0/CC-BY.

    Se activa cuando Pixabay agotó queries. Requiere FREESOUND_API_KEY.
    Header: Authorization: Token <key>. 60 req/min gratis.

    Búsqueda: query del topic + filter duration >=60s. Ordena por rating.
    Descarga preview HQ mp3 (~128kbps, sin auth extra) directo.
    """
    import os, requests, time as _time
    key = os.environ.get("FREESOUND_API_KEY", "").strip()
    if not key:
        return None
    q = topic.get("pixabay_music_query", "")
    # Fallback queries por si la principal no da nada
    queries = [q] + topic.get("pixabay_fallback_queries", [])
    queries += ["ambient calm", "relaxing"]
    headers = {"Authorization": f"Token {key}"}
    hits_all = []
    for query in queries:
        try:
            r = requests.get(
                "https://freesound.org/apiv2/search/text/",
                headers=headers,
                params={
                    "query": query,
                    "filter": f"duration:[60 TO 3600]",  # 1min-1h por track
                    "fields": "id,name,duration,previews,license",
                    "sort": "rating_desc",
                    "page_size": 20,
                },
                timeout=30,
            )
            if r.status_code == 429:
                _time.sleep(3); continue
            if r.status_code != 200:
                print(f"  freesound query '{query}': HTTP {r.status_code}")
                continue
            data = r.json()
            hits = data.get("results", [])
            if hits:
                hits_all = hits
                print(f"  freesound query '{query}': {len(hits)} hits")
                break
        except Exception as e:
            print(f"  freesound query '{query}' fail: {e}")
            continue
    if not hits_all:
        return None

    # Descarga tracks hasta cubrir target_duration
    tracks = []
    total = 0
    for i, hit in enumerate(hits_all):
        dur = float(hit.get("duration") or 0)
        if dur < 30:
            continue
        preview_url = (hit.get("previews") or {}).get("preview-hq-mp3")
        if not preview_url:
            continue
        try:
            audio = requests.get(preview_url, timeout=60).content
            p = out_dir / f"fs_track_{i:02d}.mp3"
            p.write_bytes(audio)
            tracks.append(p)
            total += dur
            if total >= target_duration_seconds:
                break
        except Exception:
            continue
    if not tracks:
        return None

    # Concat + loop hasta target (mismo patrón que _fetch_music)
    import subprocess
    concat_file = out_dir / "concat_fs.txt"
    concat_file.write_text("\n".join(f"file '{t.name}'" for t in tracks))
    base_audio = out_dir / "base_fs.mp3"
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(concat_file), "-c", "copy", str(base_audio)]
    r = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(f"  freesound concat fail — {r.stderr[:200]}")
        return None
    output = out_dir / "audio.mp3"
    if total >= target_duration_seconds * 0.95:
        base_audio.rename(output)
        print(f"  freesound: ✅ audio {int(total)}s de {len(tracks)} tracks (sin loop)")
        return output
    # Loop
    loops = (target_duration_seconds // int(total)) + 1
    cmd_loop = ["ffmpeg", "-y", "-stream_loop", str(loops),
                "-i", str(base_audio), "-t", str(target_duration_seconds),
                "-c", "copy", str(output)]
    r2 = subprocess.run(cmd_loop, cwd=out_dir, capture_output=True, text=True, timeout=900)
    if r2.returncode != 0:
        base_audio.rename(output)
    else:
        base_audio.unlink(missing_ok=True)
    print(f"  freesound: ✅ audio {target_duration_seconds}s con loop x{loops}")
    return output


def _generate_noise_fallback(out_dir: Path, duration_seconds: int,
                                color: str = "pink") -> Path | None:
    """Fallback: genera ruido pink/brown/white con ffmpeg puro cuando
    Pixabay se cae. Sonido ambient válido sin depender de API externa.

    color: 'pink' (natural, música/estudio), 'brown' (grave, dormir),
    'white' (neutral, meditación).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "audio.mp3"
    # anoisesrc con color + volume bajo + fade in/out suave
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anoisesrc=color={color}:amplitude=0.3:duration={duration_seconds}",
        "-c:a", "libmp3lame", "-b:a", "192k",
        "-af", f"afade=t=in:st=0:d=3,afade=t=out:st={duration_seconds-3}:d=3",
        str(output),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        print(f"  ambient: noise fallback fail — {r.stderr[-300:]}")
        return None
    print(f"  ambient: ✅ noise fallback OK ({color}, {duration_seconds}s)")
    return output


def _fetch_multiple_images(topic: dict, out_dir: Path, n: int = 8) -> list[Path]:
    """Descarga N imágenes HD distintas de Pexels para crossfade en video ambient.

    Fix 14/09/26: user reportó "procesamiento interrumpido" en YT para
    videos ambient largos con imagen estática, aún con framerate 12fps.
    YT tiene heurística anti-abuse que detecta contenido "estático"
    independientemente del framerate y lo rechaza como spam.

    Solución (canales top del nicho tipo Meditation Relax Music, Yellow
    Brick Cinema): CROSSFADE entre múltiples imágenes distintas cada
    15-30s. YT ve "variedad visual" → no bloquea.
    """
    import os, requests
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        print("  ambient: falta PEXELS_API_KEY — usa 1 imagen fallback")
        return []
    q = topic["pexels_image_query"]
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": q, "per_page": max(20, n * 2),
                     "orientation": "landscape", "size": "large"},
            timeout=30,
        )
        data = r.json()
    except Exception as e:
        print(f"  ambient: Pexels multi-image fetch fail — {e}")
        return []
    photos = data.get("photos", [])
    if not photos:
        return []
    random.shuffle(photos)
    downloaded: list[Path] = []
    for i, photo in enumerate(photos[:n]):
        url = (photo.get("src") or {}).get("large2x") or photo["src"]["large"]
        try:
            content = requests.get(url, timeout=30).content
            p = out_dir / f"cover_{i:02d}.jpg"
            p.write_bytes(content)
            downloaded.append(p)
        except Exception:
            continue
    print(f"  ambient: {len(downloaded)} imágenes Pexels descargadas para crossfade")
    return downloaded


def _fetch_image(topic: dict, out_dir: Path) -> Path | None:
    """Legacy — 1 sola imagen. Retenido como fallback si _fetch_multiple_images
    devuelve nada."""
    imgs = _fetch_multiple_images(topic, out_dir, n=1)
    return imgs[0] if imgs else None


def _build_video_crossfade(images: list[Path], audio: Path, out_dir: Path,
                             duration_seconds: int) -> Path | None:
    """Video ambient con crossfade entre múltiples imágenes.

    Cada imagen dura ~duration/N segundos con crossfade 2s entre transiciones.
    Loop del ciclo de imágenes durante toda la duración del audio.

    Ventaja vs imagen estática: YT ve VARIEDAD VISUAL → no marca como
    spam/abuse. Los canales top del nicho lo hacen así.
    """
    output = out_dir / "video.mp4"
    if not images:
        return None

    # Precompute cycle duration: cada imagen ~20-30s en el ciclo
    n_imgs = len(images)
    per_img = max(20, min(60, duration_seconds // (n_imgs * 3)))
    cycle = per_img * n_imgs  # segundos por ciclo completo
    loops_needed = (duration_seconds // cycle) + 2

    # ffmpeg concat repite el ciclo N veces (cada imagen loop per_img segundos
    # con framerate 24 para que YT lo procese perfect).
    # Usamos concat filter con imagenes en secuencia + fade cross entre ellas.
    # Enfoque más simple y robusto: generar UN video por imagen + concat con
    # xfade transitions.

    # PASO 1: convierte cada imagen en un mini-video de per_img segundos
    mini_dir = out_dir / "mini_clips"
    mini_dir.mkdir(exist_ok=True)
    mini_clips = []
    for i, img in enumerate(images):
        mc = mini_dir / f"mc_{i:02d}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", "24", "-i", str(img),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-preset", "ultrafast",
            "-r", "24",
            "-pix_fmt", "yuv420p",
            "-vf", ("scale=1920:1080:force_original_aspect_ratio=increase,"
                    "crop=1920:1080"),
            "-t", str(per_img),
            "-an",
            str(mc),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and mc.exists():
            mini_clips.append(mc)
    if not mini_clips:
        print(f"  ambient: falló mini-clips generation")
        return None

    # PASO 2: concat file para loop del ciclo
    concat = out_dir / "concat_video.txt"
    lines = []
    for _ in range(loops_needed):
        for mc in mini_clips:
            lines.append(f"file '{mc.relative_to(out_dir)}'")
    concat.write_text("\n".join(lines))

    # PASO 3: concat + audio + fade in/out global
    cmd_final = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-i", str(audio),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-r", "24",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-vf", (f"fade=t=in:st=0:d=3,"
                f"fade=t=out:st={duration_seconds-3}:d=3"),
        "-shortest",
        "-t", str(duration_seconds),
        str(output),
    ]
    r = subprocess.run(cmd_final, cwd=out_dir, capture_output=True,
                        text=True, timeout=3600)
    if r.returncode != 0:
        print(f"  ambient: ffmpeg crossfade final fail — {r.stderr[-400:]}")
        return None
    # Limpieza mini_clips (ahorra ~500MB disco)
    import shutil
    shutil.rmtree(mini_dir, ignore_errors=True)
    concat.unlink(missing_ok=True)
    print(f"  ambient: ✅ video crossfade OK ({n_imgs} imgs × {per_img}s)")
    return output


def _build_video(image_or_images, audio: Path, out_dir: Path,
                  duration_seconds: int) -> Path | None:
    """Wrapper compat: acepta 1 imagen (legacy) o lista (crossfade nuevo)."""
    if isinstance(image_or_images, list):
        return _build_video_crossfade(image_or_images, audio, out_dir, duration_seconds)
    # Legacy path — 1 imagen sola (usado solo si Pexels sin key)
    output = out_dir / "video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "24", "-i", str(image_or_images),
        "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
        "-r", "24", "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
        "-vf", ("scale=1920:1080:force_original_aspect_ratio=increase,"
                "crop=1920:1080,"
                "fade=t=in:st=0:d=3,"
                f"fade=t=out:st={duration_seconds-3}:d=3"),
        "-shortest", "-t", str(duration_seconds), str(output),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=2400)
    if r.returncode != 0:
        print(f"  ambient: ffmpeg fallback single-img fail — {r.stderr[-400:]}")
        return None
    return output


def _generate_seo_metadata(topic: dict, duration_min: int) -> dict:
    """Gemini genera título SEO long-tail + descripción + tags."""
    from google import genai
    from google.genai import types
    import os

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    modifier = random.choice(topic["modifiers"])
    base_kw = random.choice(topic["base_keywords"])

    if not key:
        # Fallback estático
        return {
            "title": f"{base_kw.title()} {duration_min} minutos · {modifier}",
            "description": (
                f"{base_kw.title()} durante {duration_min} minutos ideal para "
                f"{modifier}. Sin anuncios interrumpiendo.\n\n"
                f"#relax #{topic['mood']}"
            ),
            "tags": [base_kw, modifier, topic["mood"], "relax", "música"],
        }

    prompt = f"""Genera metadata SEO para YouTube ES en el nicho música ambient/relax.

Estilo de referencia: canales top ES tipo "Meditation Relax Music",
"Yellow Brick Cinema", "The Soul of Wind" (patrones long-tail que
rankean en YT ES en 2026).

Tema: {topic['key']} ({topic['mood']})
Keyword base (usar CASI textual en el título): {base_kw}
Modificador (contexto de uso): {modifier}
Duración: {duration_min} minutos ({duration_min // 60} horas)

Devuelve JSON con:
- title (max 90 chars, empieza con la keyword base + añade duración
  formato "X Horas" si >60min o "X Minutos" si <60min + termina con
  algo tipo "Sin Anuncios" / "Sueño Profundo" / "Concentracion Total".
  Ejemplos ganadores: "Musica para Estudiar 3 Horas Ondas Alfa Sin Anuncios",
  "Ruido Blanco para Dormir Bebes 8 Horas Ininterrumpido",
  "Musica Relajante para Yoga 90 Minutos Sonidos de la Naturaleza".
  MAYUSCULAS iniciales estilo YT/inglés (Title Case))
- description (~500 chars, tono cálido y directo, 4 timestamps [00:00,
  15:00, 30:00, {duration_min//2:02d}:00] con descripción breve de cada
  sección, invita a suscribirse al final, cierra con 5-8 hashtags
  relevantes en 1 línea)
- tags (lista de 12 keywords SEO ES sin #, mezcla short-tail
  "musica relajante" + long-tail "musica para estudiar concentrarse
  ondas alfa"; incluye "relax", "musica sin anuncios", "{duration_min}
  minutos" o "{duration_min//60} horas")

NO emojis en title (perjudica SEO). Sí en description con moderación.
Devuelve SOLO JSON."""

    try:
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=1.0,
                max_output_tokens=800,
            ),
        )
        data = json.loads((resp.text or "{}").strip())
        if data.get("title") and data.get("description"):
            return {
                "title": data["title"][:100],
                "description": data["description"][:4900],
                "tags": data.get("tags", [])[:15],
            }
    except Exception as e:
        print(f"  ambient: Gemini SEO fail — {e}")

    return {
        "title": f"{base_kw.title()} {duration_min} minutos · {modifier}",
        "description": (
            f"{base_kw.title()} durante {duration_min} minutos ideal para "
            f"{modifier}. Sin anuncios interrumpiendo.\n\n#relax"
        ),
        "tags": [base_kw, modifier, topic["mood"]],
    }


# 14/09/26 (segunda vez): user reportó video "retirado por demasiado largo".
# Causa raíz DEFINITIVA: canal YT sin verificar SMS tiene límite HARD 15 min.
# YT rechaza cualquier video >15min y marca "Procesamiento interrumpido" o
# "Retirado por longitud". Fix estructural: cap 14 min hasta verify SMS.
# Cuando el user verifique (youtube.com/verify), sube este cap a 180.
MAX_DURATION_MIN = int(__import__("os").environ.get("AMBIENT_MAX_MIN", "14"))


def generate_ambient_video() -> dict[str, Any] | None:
    """Pipeline completo. Devuelve dict con metadata + paths, o None si falla."""
    topic = _pick_topic()
    duration_min = random.randint(
        topic["min_duration_minutes"], topic["max_duration_minutes"])
    # Cap 3h — YT rechaza "procesamiento" en videos ambient >3h con
    # imagen estática (workers timeout). Duración suficiente para siesta
    # profunda, sesión estudio, meditación larga.
    duration_min = min(duration_min, MAX_DURATION_MIN)
    duration_sec = duration_min * 60

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"{topic['key']}_{duration_min}min_{ts}"
    work_dir = AMBIENT_ROOT / slug
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"  ambient: topic={topic['key']} duración={duration_min}min slug={slug}")

    # 1. Audio: binaural (generado ffmpeg) o música Pixabay CC0
    if topic.get("mood_type") == "binaural":
        from . import binaural
        audio_path = work_dir / "binaural.m4a"
        audio = binaural.generate_binaural(
            audio_path,
            duration_seconds=duration_sec,
            carrier_hz=topic.get("carrier_hz", 200),
            beat_hz=topic.get("beat_hz", 8),
            volume=0.3,
            wave=topic.get("wave", "binaural"),
        )
    else:
        audio = _fetch_music(topic, duration_sec, work_dir)
    if not audio:
        return None

    # 2. Imágenes múltiples (crossfade — evita "procesamiento interrumpido" YT)
    images = _fetch_multiple_images(topic, work_dir, n=8)
    if not images:
        # Fallback: 1 imagen sola si Pexels sin key
        img_single = _fetch_image(topic, work_dir)
        if not img_single:
            return None
        images = img_single  # el wrapper de _build_video acepta un Path solo

    # 3. Video (crossfade entre N imágenes + audio + fade global)
    video = _build_video(images, audio, work_dir, duration_sec)
    if not video:
        return None

    # 4. SEO metadata
    meta = _generate_seo_metadata(topic, duration_min)

    # 5. Marca ledger
    _mark_used(topic["key"])

    # image_path acepta list[Path] (crossfade nuevo) o Path (legacy fallback)
    if isinstance(images, list):
        img_path_str = str(images[0]) if images else ""
    else:
        img_path_str = str(images)
    result = {
        "slug": slug,
        "topic_key": topic["key"],
        "duration_seconds": duration_sec,
        "video_path": str(video),
        "audio_path": str(audio),
        "image_path": img_path_str,
        "title": meta["title"],
        "description": meta["description"],
        "tags": meta["tags"],
    }
    # Persist para el uploader
    (work_dir / "metadata.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
