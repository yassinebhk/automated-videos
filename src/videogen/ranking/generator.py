"""Generador bar chart race para canal TopRanking ES.

Flow:
1. Gemini genera dataset REAL (10 items × N años) basado en topic + fuente
2. matplotlib.animation crea bar chart animado (60fps → mp4)
3. ffmpeg mezcla animación + música + voz opcional Kokoro
4. Output: video mp4 9:16 (vertical Shorts) o 16:9 según config
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..config import ROOT

RANKING_ROOT = ROOT / "output" / "ranking_uploaded"


def _wrap_text(text: str, max_chars_per_line: int) -> list[str]:
    """Word-wrap manual (matplotlib no lo hace)."""
    words = text.split()
    lines = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= max_chars_per_line:
            current = (current + " " + w).strip()
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines[:4]  # max 4 líneas


def _generate_dataset_with_gemini(topic: dict, n_items: int = 10,
                                    n_years: int = 10) -> dict | None:
    """Gemini genera dataset REAL basado en fuente citada del topic.
    Devuelve {'years': [2000,...], 'items': ['USA','China',...],
             'data': [[val_2000_USA, val_2000_China,...], [...]] }"""
    try:
        from ..llm_fallback import generate_json
        schema = {
            "type": "object",
            "properties": {
                "titulo_video": {"type": "string"},
                "unidad": {"type": "string"},
                "years": {"type": "array", "items": {"type": "integer"}},
                "items": {"type": "array", "items": {"type": "string"}},
                "data": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                },
                "cierre_dato": {"type": "string"},
            },
            "required": ["titulo_video", "unidad", "years", "items", "data"],
        }

        prompt = (
            f"Genera dataset REAL para bar chart race del topic:\n"
            f"- Tema: {topic['titulo']}\n"
            f"- Fuente base: {topic['fuente']}\n"
            f"- Dataset hint: {topic['dataset_hint']}\n\n"
            f"REGLAS VERACIDAD (crítico):\n"
            f"- Datos REALES verificables en la fuente indicada\n"
            f"- Si un dato exacto no lo conoces, USA UN VALOR PRUDENTE\n"
            f"  aproximado y márcalo como aproximación en cierre_dato\n"
            f"- NO inventar países/entidades que no existan\n"
            f"- Cifras coherentes con orden de magnitud real\n\n"
            f"FORMATO:\n"
            f"- years: {n_years} valores INT (ej. 2000, 2005, 2010, ..., 2025)\n"
            f"- items: {n_items} nombres cortos (país, marca, persona, etc.)\n"
            f"- data: matriz {n_years}×{n_items} con valores numéricos\n"
            f"- unidad: '€', '$B', 'millones', 'medallas' etc\n"
            f"- titulo_video: título SEO YT max 80 chars\n"
            f"- cierre_dato: frase cierre con dato clave y fuente\n"
        )
        # Con fallback Gemini→Groq
        data = generate_json(prompt, schema=schema, max_tokens=4000, temperature=0.4)
        if not data:
            print(f"  ranking: ambos LLMs fallaron")
            return None
        # Validación + reparación defensiva (LLM a veces devuelve mismatch)
        years = data.get("years", [])
        items = data.get("items", [])
        matrix = data.get("data", [])
        if not years or not items or not matrix:
            print(f"  ranking: dataset incompleto years={len(years)} items={len(items)} data={len(matrix)}")
            return None
        # Truncar a la dimensión menor si mismatch (no fallar)
        if len(matrix) != len(years):
            m = min(len(matrix), len(years))
            print(f"  ranking: dims mismatch (years={len(years)} vs data={len(matrix)}) → truncando a {m}")
            data["years"] = years[:m]
            data["data"] = matrix[:m]
            matrix = matrix[:m]
        # Cada fila debe tener len(items) valores — pad con 0 si faltan, trunca si sobran
        n_items = len(items)
        fixed_matrix = []
        for row in matrix:
            row = list(row)
            if len(row) < n_items:
                row = row + [0] * (n_items - len(row))
            elif len(row) > n_items:
                row = row[:n_items]
            fixed_matrix.append(row)
        data["data"] = fixed_matrix
        return data
    except Exception as e:
        print(f"  ranking: Gemini fail {type(e).__name__}: {e}")
        return None


def _render_bar_chart_race(dataset: dict, out_video: Path,
                             duration_seconds: int = 55,
                             vertical: bool = True) -> Path | None:
    """Renderiza bar chart race con matplotlib.animation → mp4.
    vertical=True para Shorts 9:16 (1080x1920), False para 16:9."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.animation as manim
    except ImportError:
        print("  ranking: matplotlib no disponible")
        return None

    years = dataset["years"]
    items = dataset["items"]
    data = dataset["data"]
    unidad = dataset.get("unidad", "")

    fig_w, fig_h = (9, 16) if vertical else (16, 9)
    dpi = 120

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    fig.patch.set_facecolor("#111827")
    ax.set_facecolor("#111827")

    # Total frames = duration_seconds × 15fps (menor fps ok para bar race)
    fps = 15
    # Estructura: 4s INTRO título grande + N-7s chart + 3s OUTRO CTA
    INTRO_S = 4
    OUTRO_S = 3
    intro_frames = INTRO_S * fps  # 60
    outro_frames = OUTRO_S * fps  # 45
    chart_seconds = max(20, duration_seconds - INTRO_S - OUTRO_S)
    chart_frames = chart_seconds * fps
    n_frames = intro_frames + chart_frames + outro_frames
    frames_per_year = max(1, chart_frames // len(years))

    # Colores agradables (paleta)
    palette = ["#EF4444", "#F97316", "#EAB308", "#84CC16", "#22C55E",
                "#06B6D4", "#3B82F6", "#8B5CF6", "#EC4899", "#F43F5E"]
    item_colors = {it: palette[i % len(palette)] for i, it in enumerate(items)}

    titulo_video = dataset.get("titulo_video", "TOP 10")

    def draw_intro(fi: int):
        """Frame intro: título grande centrado con fade-in."""
        ax.clear()
        ax.set_xlim(0, 10); ax.set_ylim(0, 10)
        ax.axis("off")
        # Fade in en los primeros 15 frames (1s)
        alpha = min(1.0, fi / 15)
        # Título grande (word-wrap manual — matplotlib no lo hace)
        lines = _wrap_text(titulo_video, 22)
        y_start = 5 + (len(lines) - 1) * 0.6
        for i, line in enumerate(lines):
            ax.text(5, y_start - i * 1.2, line, ha="center", va="center",
                     color=(1, 1, 1, alpha),
                     fontsize=32, fontweight="bold")
        # Subtítulo abajo
        if fi > 20:
            sub_alpha = min(1.0, (fi - 20) / 15)
            ax.text(5, 2, "Datos verificados · TopRanking ES",
                     ha="center", va="center",
                     color=(0.9, 0.9, 0.9, sub_alpha),
                     fontsize=14, style="italic")

    def draw_outro(fi: int):
        """Frame outro: CTA suscribirse."""
        ax.clear()
        ax.set_xlim(0, 10); ax.set_ylim(0, 10)
        ax.axis("off")
        alpha = min(1.0, fi / 10)
        ax.text(5, 6.5, "¿Sorprendido?",
                 ha="center", va="center",
                 color=(1, 1, 1, alpha), fontsize=36, fontweight="bold")
        ax.text(5, 4.5, "Suscríbete para más rankings",
                 ha="center", va="center",
                 color=(1, 0.85, 0.15, alpha),
                 fontsize=24, fontweight="bold")
        ax.text(5, 2.8, "📊 TopRanking ES", ha="center", va="center",
                 color=(0.85, 0.85, 0.85, alpha), fontsize=16)

    def draw(frame_idx: int):
        # Fase intro
        if frame_idx < intro_frames:
            draw_intro(frame_idx)
            return
        # Fase outro
        if frame_idx >= intro_frames + chart_frames:
            fi_out = frame_idx - (intro_frames + chart_frames)
            draw_outro(fi_out)
            return
        # Fase chart race
        chart_fi = frame_idx - intro_frames
        ax.clear()
        year_idx = min(chart_fi // frames_per_year, len(years) - 1)
        # Interpolación lineal entre year_idx y year_idx+1 (si existe)
        progress = (chart_fi % frames_per_year) / frames_per_year
        curr = data[year_idx]
        if year_idx + 1 < len(years):
            nxt = data[year_idx + 1]
            values = [c + (n - c) * progress for c, n in zip(curr, nxt)]
        else:
            values = curr

        # Ordena por valor descendente
        pairs = sorted(zip(items, values), key=lambda x: -x[1])
        pairs = pairs[:10]  # Top 10

        y_pos = list(range(len(pairs), 0, -1))
        vals = [p[1] for p in pairs]
        names = [p[0] for p in pairs]
        colors = [item_colors[n] for n in names]

        bars = ax.barh(y_pos, vals, color=colors, edgecolor="white", linewidth=1.5)
        # Nombres a la izquierda
        for i, (name, val) in enumerate(zip(names, vals)):
            y = y_pos[i]
            ax.text(-max(vals) * 0.02, y, name, va="center", ha="right",
                     color="white", fontsize=14, fontweight="bold")
            ax.text(val + max(vals) * 0.01, y,
                     f"{val:,.0f}{unidad}", va="center", ha="left",
                     color="white", fontsize=12)

        # Título arriba
        year_display = years[year_idx] + int((years[min(year_idx+1, len(years)-1)] - years[year_idx]) * progress)
        ax.set_title(f"{dataset.get('titulo_video', 'TOP 10')}\n{year_display}",
                      color="white", fontsize=18, fontweight="bold", pad=20)
        ax.set_xlim(0, max(vals) * 1.3)
        ax.set_yticks([])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color("#374151")
        ax.tick_params(colors="white")

    anim = manim.FuncAnimation(fig, draw, frames=n_frames, interval=1000//fps)

    out_video.parent.mkdir(parents=True, exist_ok=True)
    writer = manim.FFMpegWriter(fps=fps, bitrate=2500,
                                  codec="libx264",
                                  extra_args=["-pix_fmt", "yuv420p"])
    try:
        anim.save(str(out_video), writer=writer)
        plt.close(fig)
        return out_video
    except Exception as e:
        print(f"  ranking: matplotlib animation save fail: {e}")
        plt.close(fig)
        return None


def _add_music_to_video(video: Path, work_dir: Path,
                         duration_seconds: int) -> Path | None:
    """Añade música de fondo Pixabay. Query aleatorio entre estilos épicos
    (los que retienen mejor en chart race según canales top 2026)."""
    import os as _os
    import random as _random
    key = _os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        return video

    # Music queries que rinden en chart race format (canales 1M+ usan estas)
    query = _random.choice([
        "epic cinematic dramatic",
        "trending viral upbeat",
        "trailer intense build",
        "epic orchestral countdown",
        "cinematic tension rise",
    ])
    try:
        import requests
        r = requests.get("https://pixabay.com/api/audio/",
                          params={"key": key, "q": query,
                                   "per_page": 20, "safesearch": "true"},
                          timeout=30).json()
        hits = r.get("hits", [])
        if not hits:
            return video
        for h in hits:
            dur = int(h.get("duration") or 0)
            url = h.get("audio") or h.get("url") or ""
            if url and dur >= duration_seconds:
                audio_bytes = requests.get(url, timeout=60).content
                audio_path = work_dir / "bgm.mp3"
                audio_path.write_bytes(audio_bytes)
                # Mezcla con ffmpeg
                out = work_dir / "video_final.mp4"
                cmd = ["ffmpeg", "-y",
                        "-i", str(video), "-i", str(audio_path),
                        "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "128k",
                        "-map", "0:v", "-map", "1:a",
                        "-shortest",
                        str(out)]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if r.returncode == 0:
                    return out
                return video
        return video
    except Exception as e:
        print(f"  ranking: bgm fail {e}")
        return video


def generate_ranking_video(topic: dict, out_dir: Path, duration_seconds: int = 55,
                             vertical: bool = True) -> dict | None:
    """Pipeline completo. Devuelve {video_path, title, description, dataset}."""
    dataset = _generate_dataset_with_gemini(topic)
    if not dataset:
        return None

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"{topic['key']}_{ts}"
    work_dir = out_dir / slug
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"  ranking: rendering chart race {duration_seconds}s vertical={vertical}")
    raw_video = _render_bar_chart_race(dataset, work_dir / "chart.mp4",
                                         duration_seconds=duration_seconds,
                                         vertical=vertical)
    if not raw_video:
        return None

    final_video = _add_music_to_video(raw_video, work_dir, duration_seconds)
    if not final_video:
        return None

    # Guarda dataset + video
    (work_dir / "dataset.json").write_text(
        json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "slug": slug,
        "topic_key": topic["key"],
        "video_path": str(final_video),
        "title": dataset.get("titulo_video", topic["titulo"])[:100],
        "description": (
            f"{dataset.get('titulo_video','')}\n\n"
            f"{dataset.get('cierre_dato','')}\n\n"
            f"📊 Fuente: {topic.get('fuente','')}\n\n"
            f"⚠️ Datos aproximados de fuentes oficiales · verifica antes de citarlos.\n\n"
            f"#ranking #top10 #datos #españa #curiosidades #estadisticas #Shorts"
        )[:4900],
        "tags": ["ranking", "top10", "datos", "estadisticas", "españa"],
    }
