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
    # 21/09: sin canal YT propio → redirige a Legal ES (temas laborales/contratos).
    host_yt_prefix_fallback="YT_LEGAL",
)


def run_once():
    return run_channel_once(CONFIG)
