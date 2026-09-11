"""Pipeline canal Motor 2ª mano — Motor60s."""
from __future__ import annotations

from ..channel_pipeline import ChannelConfig, run_channel_once


CONFIG = ChannelConfig(
    slug="motor",
    display_name="Motor60s",
    handle="@Motor60s_es",
    yt_prefix="YT_MOTOR",
    system_prompt_file="motor_system.md",
    topic_pool_module="videogen.motor.topic_pool",
    ledger_filename="motor_ledger.json",
    kokoro_voice_es="em_alex",
    audience_emoji={
        "compradores": "🛒",
        "propietarios": "🚗",
        "vendedores": "💰",
        "_": "🏎",
    },
    series_name="Motor60s",
    cooldown_days=90,
)


def run_once():
    return run_channel_once(CONFIG)
