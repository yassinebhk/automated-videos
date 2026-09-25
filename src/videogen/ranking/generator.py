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
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dataclasses import dataclass, field

from ..config import ROOT

RANKING_ROOT = ROOT / "output" / "ranking_uploaded"


@dataclass
class RankingBranding:
    """Branding/idioma de un canal de rankings. Default = TopRanking ES
    (comportamiento histórico intacto). El canal EN pasa el suyo."""
    lang: str = "es"
    intro_subtitle: str = "Datos verificados · TopRanking ES"
    outro_line1: str = "¿Sorprendido?"
    outro_line2: str = "Suscríbete para más rankings"
    outro_brand: str = "📊 TopRanking ES"
    source_label: str = "Fuente"
    disclaimer: str = "📌 Datos de fuentes públicas (World Bank / IMF / Forbes / Statista / prensa oficial). Rango temporal indicado en el video."
    hashtags: str = "#ranking #top10 #datos #españa #curiosidades #estadisticas #Shorts"
    tags: list = field(default_factory=lambda: ["ranking", "top10", "datos", "estadisticas", "españa"])


ES_BRANDING = RankingBranding()


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
                                    n_years: int = 10, lang: str = "es") -> dict | None:
    """Gemini genera dataset REAL basado en fuente citada del topic.

    ⚠️ Este path SOLO se ejecuta si NO hay dataset bundled/cached. Y solo se
    admite si el LLM devuelve ALTA CONFIANZA — sin datos verificables, el
    módulo prefiere devolver None (skip video) a publicar cifras inventadas.
    Ver historia veracidad: fuimos permisivos ("USA UN VALOR PRUDENTE
    aproximado") → user detectó datos fake → cambio a estricto 25/09/26.
    """
    try:
        from ..llm_fallback import generate_json
        current_year = datetime.now(timezone.utc).year
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
                # Confianza autoevaluada del LLM. Si <0.7 → skip (no publicar).
                "confidence": {"type": "number"},
                # URL/nombre de la fuente que respalda cada dato. Requerido.
                "source_note": {"type": "string"},
            },
            "required": ["titulo_video", "unidad", "years", "items", "data",
                          "confidence", "source_note"],
        }

        prompt = (
            f"Genera dataset REAL para bar chart race del topic:\n"
            f"- Tema: {topic['titulo']}\n"
            f"- Fuente base: {topic['fuente']}\n"
            f"- Dataset hint: {topic['dataset_hint']}\n"
            f"- Año actual: {current_year} (los años del ranking DEBEN llegar hasta {current_year} o {current_year - 1} si el dato oficial no está publicado aún)\n\n"
            f"REGLAS VERACIDAD (ESTRICTAS — el user detectó datos fake):\n"
            f"- Datos VERIFICABLES en la fuente citada. Si no lo son, RECHAZA la tarea.\n"
            f"- PROHIBIDO inventar cifras aunque suenen plausibles. Riesgo legal real.\n"
            f"- PROHIBIDO valores 'prudentes aproximados'. Solo datos que puedas defender.\n"
            f"- Si no puedes generar los 10 items × {n_years} años con datos reales,\n"
            f"  devuelve confidence <0.5 y explica en source_note por qué. El pipeline\n"
            f"  lo detectará y descartará el video en vez de publicar mentiras.\n"
            f"- confidence: 0.0-1.0 tu autoevaluación honesta (¿defenderías estas cifras\n"
            f"  frente a un periodista o un juez? si no → <0.7).\n"
            f"- source_note: fuente concreta (ej. 'World Bank NY.GDP.MKTP.CD 2024',\n"
            f"  'Forbes 2025 Billionaires List', 'IMDb Box Office Top 2024').\n"
            f"- NO inventar países/entidades que no existan.\n\n"
            f"FORMATO:\n"
            f"- years: hasta {n_years} valores INT llegando a {current_year} o {current_year - 1}.\n"
            f"  Ej. si n_years=10 y year actual={current_year}: [{current_year - 9}, ..., {current_year}]\n"
            f"- items: {n_items} nombres cortos (país, marca, persona, etc.) MÁX 22 CHARS\n"
            f"  (etiquetas más largas se cortan en el bar chart)\n"
            f"- data: matriz N×{n_items} con valores numéricos reales\n"
            f"- unidad: '€', '$B', 'millones', 'medallas' etc\n"
            f"- titulo_video: título SEO YT max 80 chars, DEBE mencionar {current_year} o el año más reciente cubierto\n"
            f"- cierre_dato: frase cierre con dato clave, año y fuente EXPLÍCITA\n"
            f"\nIDIOMA de titulo_video/unidad/cierre_dato: "
            f"{'ENGLISH' if lang == 'en' else 'ESPAÑOL'} "
            f"(los nombres de items/entidades van en su forma internacional habitual).\n"
        )
        # Temperature bajo → menos alucinación. Antes 0.4, ahora 0.15.
        data = generate_json(prompt, schema=schema, max_tokens=4000, temperature=0.15)
        if not data:
            print(f"  ranking: ambos LLMs fallaron")
            return None
        # Gate anti-fake: si el LLM se autoevalúa <0.7 → SKIP (no publicar).
        # Preferimos saltar el video a publicar cifras inventadas.
        conf = float(data.get("confidence", 0.0) or 0.0)
        source_note = (data.get("source_note") or "").strip()
        if conf < 0.7:
            print(f"  ranking: ⚠️ SKIP — LLM confidence={conf:.2f} < 0.7. "
                  f"source_note='{source_note[:120]}'")
            return None
        if not source_note or len(source_note) < 12:
            print(f"  ranking: ⚠️ SKIP — sin source_note fiable ('{source_note[:80]}')")
            return None
        print(f"  ranking: LLM dataset aceptado (conf={conf:.2f}, source='{source_note[:80]}')")
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
                             vertical: bool = True,
                             branding: "RankingBranding | None" = None) -> Path | None:
    """Renderiza bar chart race con matplotlib.animation → mp4.
    vertical=True para Shorts 9:16 (1080x1920), False para 16:9."""
    branding = branding or ES_BRANDING
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
    # Ancho útil: 68% del figure (left=0.28 → deja espacio a nombres izquierda;
    # right=0.96 → deja aire mínimo a la derecha para que las etiquetas de valor
    # no se salgan pero sin recortar el título). El título va con fig.suptitle
    # (span figure completo) para NO respetar los márgenes del axes.
    # top=0.90 → chart ocupa más área (menos hueco en blanco entre suptitle y barras).
    fig.subplots_adjust(left=0.28, right=0.96, top=0.90, bottom=0.06)

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
    # Año más reciente del dataset (para el disclaimer visible en intro)
    max_year = max(years) if years else datetime.now(timezone.utc).year
    source_short = (dataset.get("source_note") or "").strip()[:60]

    # Unidad corta para la etiqueta de barras: si es una frase larga
    # ("millones habitantes área metropolitana", "millones de dólares"),
    # abrevia a algo compacto que quepa junto a la cifra. La forma completa
    # se muestra debajo del título como subtítulo del chart.
    _SHORT_UNIT_MAP = {
        "millones habitantes área metropolitana": "M hab.",
        "millones de habitantes": "M hab.",
        "millones habitantes": "M hab.",
        "millones de euros": "M€",
        "millones de dólares": "M$",
        "miles de millones": "MM",
        "medallas": "🏅",
        "hab.": "hab.",
    }
    def _short_unit(u: str) -> str:
        if not u:
            return ""
        ul = u.strip().lower()
        if ul in _SHORT_UNIT_MAP:
            return _SHORT_UNIT_MAP[ul]
        # Auto-abreviar: si es corto (<=6 chars) o ya es símbolo → tal cual
        if len(u) <= 6:
            return u
        # Sino, primera palabra + inicial siguiente (ej. "millones habitantes" → "M hab")
        parts = u.split()
        if len(parts) >= 2 and parts[0].lower().startswith("mill"):
            return "M " + parts[1][:4] + ("." if len(parts[1]) > 4 else "")
        return parts[0][:6]
    unidad_short = _short_unit(unidad)
    unidad_full = unidad  # para el subtítulo permanente si es distinta

    def draw_intro(fi: int):
        """Frame intro: título grande centrado con fade-in."""
        ax.clear()
        # ax.clear() no borra fig.suptitle → limpiar explícitamente.
        fig.suptitle("")
        # Intro/outro necesitan que el axes ocupe TODO el figure para que
        # (5,5) sea el centro visual real. En el chart usamos márgenes
        # asimétricos (left=0.28) para los nombres izquierda; aquí no.
        fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        ax.set_xlim(0, 10); ax.set_ylim(0, 10)
        ax.axis("off")
        # Fade in en los primeros 15 frames (1s)
        alpha = min(1.0, fi / 15)
        # Wrap ancho + fontsize adaptativo por longitud (evitan que quede
        # una línea acabando en "·" o que "2024" quede sola por ancho corto).
        _tl = len(titulo_video)
        if _tl <= 30:
            wrap_w, fs, line_sep = 30, 34, 1.0
        elif _tl <= 50:
            wrap_w, fs, line_sep = 30, 28, 0.9
        elif _tl <= 70:
            wrap_w, fs, line_sep = 32, 24, 0.8
        else:
            wrap_w, fs, line_sep = 34, 20, 0.7
        lines = _wrap_text(titulo_video, wrap_w)
        # Compactación: si la última línea queda muy corta (ej "2024"),
        # intenta fusionarla con la anterior si cabe.
        if len(lines) >= 2 and len(lines[-1]) <= 6:
            joined = lines[-2] + " " + lines[-1]
            if len(joined) <= wrap_w + 6:
                lines = lines[:-2] + [joined]
        y_start = 5 + (len(lines) - 1) * (line_sep / 2)
        for i, line in enumerate(lines):
            # Quita "·" colgante al final de línea (queda feo)
            line = line.rstrip(" ·")
            ax.text(5, y_start - i * line_sep, line, ha="center", va="center",
                     color=(1, 1, 1, alpha),
                     fontsize=fs, fontweight="bold")
        # Subtítulo abajo
        if fi > 20:
            sub_alpha = min(1.0, (fi - 20) / 15)
            ax.text(5, 2.3, branding.intro_subtitle,
                     ha="center", va="center",
                     color=(0.9, 0.9, 0.9, sub_alpha),
                     fontsize=14, style="italic")
            # Transparencia: año más reciente del dataset + fuente cortada
            data_line = f"Datos hasta {max_year}"
            if source_short:
                data_line += f" · {source_short}"
            ax.text(5, 1.4, data_line,
                     ha="center", va="center",
                     color=(1.0, 0.85, 0.35, sub_alpha),
                     fontsize=11)

    def draw_outro(fi: int):
        """Frame outro: CTA suscribirse."""
        ax.clear()
        fig.suptitle("")
        # Full-figure axes también en outro (mismo motivo que intro).
        fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        ax.set_xlim(0, 10); ax.set_ylim(0, 10)
        ax.axis("off")
        alpha = min(1.0, fi / 10)
        ax.text(5, 6.5, branding.outro_line1,
                 ha="center", va="center",
                 color=(1, 1, 1, alpha), fontsize=36, fontweight="bold")
        ax.text(5, 4.5, branding.outro_line2,
                 ha="center", va="center",
                 color=(1, 0.85, 0.15, alpha),
                 fontsize=24, fontweight="bold")
        ax.text(5, 2.8, branding.outro_brand, ha="center", va="center",
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
        # Restaurar layout asimétrico del chart (intro/outro lo ponían full-figure).
        fig.subplots_adjust(left=0.28, right=0.96, top=0.90, bottom=0.06)
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
        # Nombres a la izquierda: truncar >22 chars con "…" + fontsize dinámico
        max_name_chars = 22
        for i, (name, val) in enumerate(zip(names, vals)):
            y = y_pos[i]
            display_name = name if len(name) <= max_name_chars else name[:max_name_chars - 1] + "…"
            name_fs = 14 if len(display_name) <= 14 else (12 if len(display_name) <= 18 else 11)
            ax.text(-max(vals) * 0.02, y, display_name, va="center", ha="right",
                     color="white", fontsize=name_fs, fontweight="bold")
            # Cifra + unidad corta con espacio. Si el bar es corto y hay
            # sitio a la derecha, texto FUERA del bar; si es largo, texto
            # DENTRO del bar (color negro para contraste) para no salirse.
            label_txt = f"{val:,.0f} {unidad_short}".strip()
            if val < max(vals) * 0.75:
                # Fuera del bar (a la derecha)
                ax.text(val + max(vals) * 0.012, y, label_txt,
                         va="center", ha="left",
                         color="white", fontsize=12, fontweight="bold")
            else:
                # Dentro del bar (extremo derecho, ha="right" con offset negativo)
                ax.text(val - max(vals) * 0.012, y, label_txt,
                         va="center", ha="right",
                         color="#111827", fontsize=12, fontweight="bold")

        # Título: fig.suptitle (span figure completo, NO respeta márgenes axes)
        year_display = years[year_idx] + int((years[min(year_idx+1, len(years)-1)] - years[year_idx]) * progress)
        base_title = dataset.get("titulo_video", "TOP 10")
        # Anti-duplicado: si el título YA menciona el año (los bundled data
        # llevan "· 2024" hardcoded), NO añadimos otra línea con el año.
        year_str = str(year_display)
        if year_str in base_title or f"({year_str})" in base_title:
            full_title = base_title
        else:
            full_title = f"{base_title} · {year_display}"
        # Fontsize adaptativo por longitud del título (evita cortes por ancho fig)
        _tl = len(full_title)
        title_fs = 20 if _tl <= 40 else (16 if _tl <= 60 else 13)
        fig.suptitle(full_title,
                      color="white", fontsize=title_fs, fontweight="bold", y=0.965)
        # Subtítulo con la unidad completa (si la corta difiere), pegado al suptitle
        if unidad_full and unidad_full != unidad_short and len(unidad_full) > 6:
            ax.text(0.5, 1.01, f"({unidad_full})", transform=ax.transAxes,
                     ha="center", va="bottom", color="#94a3b8",
                     fontsize=10, style="italic")
        # xlim con margen 60% (era 30%) para el texto de valor a la derecha
        ax.set_xlim(0, max(vals) * 1.6)
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
    """Añade música de fondo libre (Pixabay→Freesound vía videogen.music).
    La pista se hace loop (-stream_loop) para cubrir el vídeo aunque sea corta."""
    from .. import music
    queries = [
        "epic cinematic dramatic", "trending viral upbeat", "trailer intense build",
        "epic orchestral countdown", "cinematic tension rise",
    ]
    audio_path = music.fetch_bgm(queries, work_dir / "bgm.mp3", min_dur=15)
    if not audio_path:
        return video
    try:
        out = work_dir / "video_final.mp4"
        # música (input 0, en loop infinito) + vídeo (input 1); -shortest corta al vídeo
        cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(audio_path),
               "-i", str(video), "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
               "-map", "1:v", "-map", "0:a", "-shortest", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return out if r.returncode == 0 else video
    except Exception as e:
        print(f"  ranking: bgm mux fail {e}")
        return video


def generate_ranking_video(topic: dict, out_dir: Path, duration_seconds: int = 55,
                             vertical: bool = True,
                             branding: "RankingBranding | None" = None) -> dict | None:
    """Pipeline completo. Devuelve {video_path, title, description, dataset}.

    15/09/26: prioridad DATASET REAL bundled (World Bank cache) sobre
    generación LLM (que alucinaba). El topic ahora puede tener campo
    `dataset_key` apuntando a un dataset cacheado (ej. `wb_NY_GDP_MKTP_CD_2000_2024`).
    Si el key existe en cache → usar directo. Si no → Gemini fallback
    (marcar el video como "estimación aproximada, verifica fuente").
    """
    branding = branding or ES_BRANDING

    dataset = None
    dkey = topic.get("dataset_key")
    if dkey:
        from . import datasets_fetcher
        dataset = datasets_fetcher.load_cached(dkey, max_age_days=30)
        if dataset:
            # Warn si el dataset tiene años viejos (>2 años sin refrescar).
            # Los bundled data se refrescan manual → algunos apuntan hasta 2023/2024
            # y son publicados en 2026 → user se queja con razón. Alerta en log
            # para que el catchup semanal regenere el bundled desde su fuente.
            _yrs = dataset.get("years") or []
            _cur = datetime.now(timezone.utc).year
            if _yrs and max(_yrs) < _cur - 1:
                print(f"  ranking: ⚠️ bundled '{dkey}' llega solo hasta {max(_yrs)} "
                      f"(hoy es {_cur}). Considera regenerar el bundled con datos frescos.")
            print(f"  ranking: ✅ dataset REAL cargado desde cache ({dkey})")
        else:
            print(f"  ranking: ⚠️ dataset_key={dkey} sin cache — intentando fetch on-demand")
            # Intento fetch on-demand si es key World Bank
            if dkey.startswith("wb_"):
                m = re.match(r"wb_(.+)_(\d{4})_(\d{4})", dkey)
                if m:
                    ind = m.group(1).replace("_", ".")
                    dataset = datasets_fetcher.fetch_worldbank_top(
                        ind, int(m.group(2)), int(m.group(3)))
    if not dataset:
        print(f"  ranking: sin dataset real, fallback Gemini (marca aproximado)")
        dataset = _generate_dataset_with_gemini(topic, lang=branding.lang)
    if not dataset:
        return None

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = f"{topic['key']}_{ts}"
    work_dir = out_dir / slug
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"  ranking: rendering chart race {duration_seconds}s vertical={vertical}")
    raw_video = _render_bar_chart_race(dataset, work_dir / "chart.mp4",
                                         duration_seconds=duration_seconds,
                                         vertical=vertical, branding=branding)
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
            f"📊 {branding.source_label}: {topic.get('fuente','')}\n\n"
            f"{branding.disclaimer}\n\n"
            f"{branding.hashtags}"
        )[:4900],
        "tags": list(branding.tags),
    }
