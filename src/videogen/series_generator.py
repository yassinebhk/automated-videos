"""Series encadenadas: divide 1 caso español gordo en 5 shorts consecutivos
con cliffhangers artificiales. Fuerza retorno diario → suscripción.

Flow:
- Elige caso "gordo" del pool (>200M€ o muy conocido).
- Gemini genera plan de 5 partes con ángulos DISTINTOS:
  1. Contexto (quién/cuándo)
  2. Mecanismo (cómo lo hicieron)
  3. Detalles brutales (números/testimonios)
  4. Investigación/juicio (cómo cayeron)
  5. Consecuencias hoy
- Cada parte con cliffhander explícito al final que enganche a mañana.
- Se guarda plan en output/active_series.json.
- Cada daily-short, si serie activa y última parte >20h → siguiente parte.

Objetivo: convertir spectadores casuales en suscriptores por FOMO
("mañana la parte 3, no os la perdáis").
"""
from __future__ import annotations

import json
import random
import urllib.request
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .config import ROOT

ACTIVE_SERIES = ROOT / "output" / "active_series.json"
SERIES_HISTORY = ROOT / "output" / "series_history.json"
MIN_HOURS_BETWEEN_PARTS = 20  # No publicar 2 partes en <20h


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _pick_gordo_case() -> str | None:
    """Selecciona un caso 'gordo' del pool, no usado como serie recientemente."""
    from . import case_ledger
    try:
        avail = case_ledger.available_cases_for_prompt(days=365, sample_size=30)
    except Exception:
        return None
    # Historia de series pasadas
    hist = _load(SERIES_HISTORY, [])
    used_keys = {h.get("case_key") for h in hist[-10:] if h.get("case_key")}
    # Filtra los que no se usaron como serie
    candidates = [c for c in avail if (c.get("key") or c.get("name")) not in used_keys]
    if not candidates:
        candidates = avail
    if not candidates:
        return None
    random.shuffle(candidates)
    picked = candidates[0]
    return picked.get("name") or picked.get("title") or picked.get("key")


def _generate_plan(case_name: str) -> list[dict] | None:
    """Gemini genera plan de 5 partes con ángulos distintos + cliffhangers."""
    try:
        from google import genai
        from google.genai import types
        from .config import gemini_key
        key = gemini_key()
        if not key:
            return None
        client = genai.Client(api_key=key)
        schema = {
            "type": "object",
            "properties": {
                "parts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "part_num": {"type": "integer"},
                            "angle": {"type": "string"},
                            "topic": {"type": "string"},
                            "cliffhanger": {"type": "string"},
                        },
                        "required": ["part_num", "topic", "cliffhanger"],
                    },
                }
            },
            "required": ["parts"],
        }
        prompt = (
            f"Divide el caso español real '{case_name}' en una MINISERIE de 5 shorts "
            f"YouTube (<60s cada uno). Cada parte con ángulo DISTINTO.\n\n"
            f"Estructura obligatoria:\n"
            f"- Parte 1/5 · Contexto: quién, cuándo, dónde. Sitúa al espectador.\n"
            f"- Parte 2/5 · Mecanismo: CÓMO lo hicieron paso a paso.\n"
            f"- Parte 3/5 · Detalles brutales: cifras, testimonios, momentos clave.\n"
            f"- Parte 4/5 · Investigación/juicio: cómo cayeron, sentencia.\n"
            f"- Parte 5/5 · Consecuencias hoy: qué queda, quién sigue impune.\n\n"
            f"Para cada parte devuelve:\n"
            f"- part_num (1-5)\n"
            f"- angle (etiqueta corta: contexto/mecanismo/detalles/juicio/consecuencias)\n"
            f"- topic: descripción del short LISTO para autogen, con formato:\n"
            f"  '[MINISERIE {case_name} · Parte N/5] <descripción angulo>'\n"
            f"  máximo 200 chars.\n"
            f"- cliffhanger: frase gancho para el FINAL del script que enganche a la\n"
            f"  siguiente parte. Ej: 'Y lo peor no era eso. Mañana, la parte 2: cómo\n"
            f"  movieron 200M€ sin que nadie los detectara'. Máx 150 chars.\n\n"
            f"Devuelve JSON con clave 'parts' = array de 5 objetos."
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=1.0,
                max_output_tokens=4000,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        text = (resp.text or "").strip()
        try:
            data = json.loads(text)
        except Exception:
            print(f"  series: JSON parse fail — text[:200]={text[:200]}")
            return None
        parts = data.get("parts") or []
        if len(parts) < 5:
            print(f"  series: solo {len(parts)} partes generadas")
            return None
        return parts[:5]
    except Exception as e:
        print(f"  series: Gemini fail {type(e).__name__}: {e}")
        return None


def start_new_series() -> dict | None:
    """Crea nueva serie: elige caso + genera plan + guarda active_series."""
    case = _pick_gordo_case()
    if not case:
        return None
    print(f"  series: iniciando nueva miniserie sobre «{case[:80]}»")
    plan = _generate_plan(case)
    if not plan:
        return None
    from . import case_ledger
    key = None
    try:
        key = case_ledger.match_case_key(case)
    except Exception:
        pass
    active = {
        "case_name": case,
        "case_key": key,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "parts": plan,
        "next_part": 1,
        "last_published_at": None,
    }
    _save(ACTIVE_SERIES, active)
    _notify(f"🎬 <b>Miniserie iniciada</b>\n"
            f"→ <i>{case[:80]}</i>\n"
            f"5 partes planificadas · próxima: 1/5")
    return active


def get_next_series_topic() -> str | None:
    """Si hay serie activa y toca siguiente parte, devuelve topic + marca."""
    active = _load(ACTIVE_SERIES, None)
    if not active:
        return None
    next_num = active.get("next_part", 1)
    if next_num > 5:
        # Serie completa — archiva y borra
        _archive_completed(active)
        return None
    # Rate-limit: no publicar 2 partes en <20h
    last = active.get("last_published_at")
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if (datetime.now(timezone.utc) - last_dt) < timedelta(hours=MIN_HOURS_BETWEEN_PARTS):
                print(f"  series: parte {next_num}/5 aún no toca (última hace <20h)")
                return None
        except Exception:
            pass
    # Encuentra topic de esta parte
    part = next(
        (p for p in active["parts"] if p.get("part_num") == next_num), None
    )
    if not part:
        return None
    topic = part.get("topic") or f"[MINISERIE {active['case_name']} · Parte {next_num}/5]"
    # Añade cliffhanger como instrucción explícita al final
    cliff = part.get("cliffhanger", "")
    if cliff:
        topic = f"{topic}. IMPORTANTE: el script DEBE terminar con este cliffhanger literal: «{cliff}»"
    return topic


def mark_part_published() -> None:
    """Llamado tras publicar exitosamente una parte."""
    active = _load(ACTIVE_SERIES, None)
    if not active:
        return
    published = active.get("next_part", 1)
    active["next_part"] = published + 1
    active["last_published_at"] = datetime.now(timezone.utc).isoformat()
    if active["next_part"] > 5:
        _archive_completed(active)
    else:
        _save(ACTIVE_SERIES, active)
    _notify(f"📺 Miniserie «{active['case_name'][:60]}»: parte {published}/5 publicada")


def _archive_completed(active: dict) -> None:
    """Mueve serie completa al history y borra active."""
    hist = _load(SERIES_HISTORY, [])
    hist.append({
        **active,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    hist = hist[-50:]  # No más de 50 series en history
    _save(SERIES_HISTORY, hist)
    if ACTIVE_SERIES.exists():
        try:
            ACTIVE_SERIES.unlink()
        except Exception:
            pass
    _notify(f"✅ Miniserie <i>{active['case_name'][:60]}</i> COMPLETA (5/5)")


def _notify(text: str) -> None:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data=json.dumps({"chat_id": int(chat), "text": text,
                              "parse_mode": "HTML"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass
