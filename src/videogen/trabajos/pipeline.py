"""Pipeline Curiosidades Laborales ES — instancia el channel_pipeline genérico."""
from __future__ import annotations

from ..channel_pipeline import ChannelConfig, run_channel_once


CONFIG = ChannelConfig(
    slug="trabajos",
    display_name="CuriosLaboral ES",
    handle="@CuriosLaboral_ES",
    yt_prefix="YT_TRABAJOS",
    system_prompt_file="trabajos_system.md",
    topic_pool_module="videogen.trabajos.topic_pool",
    ledger_filename="trabajos_ledger.json",
    kokoro_voice_es="em_alex",
    edge_voice_es="es-ES-AlvaroNeural",
    audience_emoji={"general": "💼", "jovenes": "🧑‍💼", "_": "💼"},
    series_name="CuriosLaboral ES",
    cooldown_days=90,
)


def run_once():
    # ⏸ PAUSADO 20/09 (consolidación: sin canal YT propio + sin tracción).
    # Reactivar = borrar estas 2 líneas + crear YT_TRABAJOS_* + `gh workflow enable trabajos-daily`.
    print("  trabajos: ⏸ PAUSADO (consolidación) — no genera")
    return {"status": "paused", "channel": "trabajos"}
    return run_channel_once(CONFIG)
