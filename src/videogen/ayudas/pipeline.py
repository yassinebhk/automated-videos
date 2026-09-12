"""Pipeline canal Ayudas y Subvenciones ES — AyudaGob."""
from __future__ import annotations

from ..channel_pipeline import ChannelConfig, run_channel_once, run_channel_longform_once


CONFIG = ChannelConfig(
    slug="ayudas",
    display_name="AyudaGob",
    handle="@AyudaGob_es",
    yt_prefix="YT_AYUDAS",
    system_prompt_file="ayudas_system.md",
    topic_pool_module="videogen.ayudas.topic_pool",
    ledger_filename="ayudas_ledger.json",
    topic_pool_long_module="videogen.ayudas.topic_pool_long",
    kokoro_voice_es="em_alex",
    edge_voice_es="es-ES-ElviraNeural",
    audience_emoji={
        "autonomos": "👔",
        "familias": "👨‍👩‍👧",
        "particulares": "🧑",
        "trabajadores": "👷",
        "estudiantes": "🎓",
        "empresas": "🏢",
        "_": "🎁",
    },
    series_name="AyudaGob",
    cooldown_days=90,
)


def run_longform():
    return run_channel_longform_once(CONFIG)


def run_once():
    return run_channel_once(CONFIG)
