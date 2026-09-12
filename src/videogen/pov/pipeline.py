"""Pipeline canal TiempoAtrás ES (Historical POV)."""
from __future__ import annotations

from ..channel_pipeline import ChannelConfig, run_channel_once, run_channel_longform_once


CONFIG = ChannelConfig(
    slug="pov",
    display_name="TiempoAtrás ES",
    handle="@TiempoAtras_ES",
    yt_prefix="YT_POV",
    system_prompt_file="pov_system.md",
    topic_pool_module="videogen.pov.topic_pool",
    ledger_filename="pov_ledger.json",
    kokoro_voice_es="em_alex",
    edge_voice_es="es-ES-TeoNeural",
    audience_emoji={
        "general": "⏳",
        "_": "⏳",
    },
    series_name="TiempoAtrás ES",
    cooldown_days=90,
)


def run_once():
    return run_channel_once(CONFIG)


def run_longform():
    return run_channel_longform_once(CONFIG)
