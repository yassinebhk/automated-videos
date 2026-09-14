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
COOLDOWN_DAYS = 14  # no repetir tema en 2 semanas


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

    Usa pool ESTÁTICO + DINÁMICO (Gemini refresca cada 14d con topics
    trending). Prioriza:
      1. Topics dinámicos frescos (nunca usados) — máxima novedad
      2. Estáticos fuera de cooldown
      3. Cualquiera fuera de cooldown (dinámicos + estáticos)
      4. Todos si todos en cooldown (fallback anti-bloqueo)
    """
    from . import topic_refresher
    all_pool = topic_refresher.get_all_topics_merged()

    ledger = _load_ledger()
    cutoff = datetime.now(timezone.utc) - timedelta(days=COOLDOWN_DAYS)
    fresh_dynamic, available = [], []
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
            if t["key"] not in static_keys and not recent:
                fresh_dynamic.append(t)

    if fresh_dynamic:
        # Da 60% preferencia a dinámicos nunca usados (variedad garantizada)
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
        print(f"  ambient: agotadas {len(queries)} queries Pixabay → fallback ffmpeg noise")
        # Fallback total: ruido generado con ffmpeg puro para el target
        # duration. Elige noise type según mood del topic:
        #   sleep/deep_sleep → brownian noise (grave, relajante)
        #   focus/study/relax → pink noise (más natural)
        #   yoga/zen/nature → pink noise
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


def _fetch_image(topic: dict, out_dir: Path) -> Path | None:
    """Descarga imagen HD de Pexels."""
    import os, requests
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        print("  ambient: falta PEXELS_API_KEY")
        return None
    q = topic["pexels_image_query"]
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": q, "per_page": 20, "orientation": "landscape"},
            timeout=30,
        )
        data = r.json()
    except Exception as e:
        print(f"  ambient: Pexels image fetch fail — {e}")
        return None
    photos = data.get("photos", [])
    if not photos:
        return None
    photo = random.choice(photos)
    url = (photo.get("src") or {}).get("original") or photo["src"]["large2x"]
    try:
        content = requests.get(url, timeout=30).content
    except Exception:
        return None
    p = out_dir / "cover.jpg"
    p.write_bytes(content)
    return p


def _build_video(image: Path, audio: Path, out_dir: Path,
                  duration_seconds: int) -> Path | None:
    """ffmpeg: image loop + audio → mp4 1920x1080. Fade in/out 3s."""
    output = out_dir / "video.mp4"
    # Optimizado para imagen estática 30-60min en runner 2-core:
    # - framerate 1fps (imagen no cambia — YT lo mostrará normal, no truco).
    #   Reduce load 30× vs 30fps default.
    # - preset ultrafast → prioriza velocidad sobre tamaño.
    # - -tune stillimage: optimizaciones específicas x264 para imagen fija.
    # - audio copy (ya es AAC binaural o mp3 pixabay convertido a aac out).
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "1", "-i", str(image),
        "-i", str(audio),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-preset", "ultrafast",
        "-r", "1",  # 1fps output
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-vf", (
            "scale=1920:1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080,"
            "fade=t=in:st=0:d=3,"
            f"fade=t=out:st={duration_seconds-3}:d=3"
        ),
        "-shortest",
        "-t", str(duration_seconds),
        str(output),
    ]
    # Timeout 40min max (60min video ambient tipo dormir requiere hasta ~2400s)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=2400)
    if r.returncode != 0:
        print(f"  ambient: ffmpeg video fail — {r.stderr[-400:]}")
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
            model="gemini-2.5-flash-lite",
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


def generate_ambient_video() -> dict[str, Any] | None:
    """Pipeline completo. Devuelve dict con metadata + paths, o None si falla."""
    topic = _pick_topic()
    duration_min = random.randint(
        topic["min_duration_minutes"], topic["max_duration_minutes"])
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

    # 2. Imagen
    image = _fetch_image(topic, work_dir)
    if not image:
        return None

    # 3. Video (image loop + audio + fade)
    video = _build_video(image, audio, work_dir, duration_sec)
    if not video:
        return None

    # 4. SEO metadata
    meta = _generate_seo_metadata(topic, duration_min)

    # 5. Marca ledger
    _mark_used(topic["key"])

    result = {
        "slug": slug,
        "topic_key": topic["key"],
        "duration_seconds": duration_sec,
        "video_path": str(video),
        "audio_path": str(audio),
        "image_path": str(image),
        "title": meta["title"],
        "description": meta["description"],
        "tags": meta["tags"],
    }
    # Persist para el uploader
    (work_dir / "metadata.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
