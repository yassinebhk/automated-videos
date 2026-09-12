"""Pipeline canal Legal Laboral — TusDerechos ES.
Instancia channel_pipeline genérico con config del nicho."""
from __future__ import annotations

from ..channel_pipeline import ChannelConfig, run_channel_once, run_channel_longform_once


CONFIG = ChannelConfig(
    slug="legal",
    display_name="TusDerechos ES",
    handle="@TusDerechos_ES",
    yt_prefix="YT_LEGAL",
    system_prompt_file="legal_system.md",
    topic_pool_module="videogen.legal.topic_pool",
    ledger_filename="legal_ledger.json",
    topic_pool_long_module="videogen.legal.topic_pool_long",
    kokoro_voice_es="em_alex",
    edge_voice_es="es-ES-AlvaroNeural",
    audience_emoji={
        "trabajadores": "👷",
        "autonomos": "👔",
        "empresas": "🏢",
        "_": "⚖️",
    },
    series_name="TusDerechos ES",
    cooldown_days=90,
)


def run_longform():
    return run_channel_longform_once(CONFIG)


def run_once():
    return run_channel_once(CONFIG)
