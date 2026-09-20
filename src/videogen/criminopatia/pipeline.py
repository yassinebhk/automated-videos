"""Pipeline Criminopatía ES — instancia el channel_pipeline genérico."""
from __future__ import annotations

from ..channel_pipeline import ChannelConfig, run_channel_once


CONFIG = ChannelConfig(
    slug="criminopatia",
    display_name="Criminopatía",
    handle="@Criminopatia_ES",
    yt_prefix="YT_CRIMINOPATIA",
    system_prompt_file="criminopatia_system.md",
    topic_pool_module="videogen.criminopatia.topic_pool",
    ledger_filename="criminopatia_ledger.json",
    kokoro_voice_es="em_alex",
    edge_voice_es="es-ES-AlvaroNeural",
    audience_emoji={"general": "🔍", "_": "🔬"},
    series_name="Criminopatía",
    cooldown_days=90,
)


def run_once():
    # ⏸ PAUSADO 20/09 (consolidación: sin canal YT propio + sin tracción).
    # Reactivar = borrar estas 2 líneas + crear YT_CRIMINOPATIA_* + `gh workflow enable criminopatia-daily`.
    print("  criminopatia: ⏸ PAUSADO (consolidación) — no genera")
    return {"status": "paused", "channel": "criminopatia"}
    return run_channel_once(CONFIG)
