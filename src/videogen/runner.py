"""Entrypoints one-shot para correr los jobs del bot fuera del framework PTB.

Diseñado para GitHub Actions: cada Action ejecuta `videogen autogen-once` o
`videogen longgen-once` o `videogen dispatch --cmd ...`, y estas funciones
reutilizan la lógica de `telegram_bot._run_*` sin necesitar el long-polling ni
el JobQueue de python-telegram-bot.

Truco central: `FakeCtx` implementa la interfaz mínima que las funciones del bot
esperan (`ctx.bot.send_message`, `ctx.bot.send_photo`, `ctx.bot.send_video`,
`ctx.job.chat_id`) hablando con la API HTTP de Telegram vía `requests`.
"""
from __future__ import annotations

import asyncio
import io
import os
from pathlib import Path
from typing import Any

import requests

from .config import telegram_chat_id, telegram_token


class _HttpTelegramBot:
    """Adapter que implementa el subset de la Bot API que usan los handlers.

    Las firmas son async porque las funciones del bot llaman con `await`, pero
    internamente delegamos a `requests` en un thread para no bloquear el loop.
    """

    def __init__(self, token: str):
        self._token = token
        self._base = f"https://api.telegram.org/bot{token}"

    async def _post(self, method: str, *, json: dict | None = None,
                    data: dict | None = None, files: dict | None = None,
                    timeout: int = 60) -> dict:
        def _call():
            r = requests.post(f"{self._base}/{method}", json=json, data=data,
                              files=files, timeout=timeout)
            r.raise_for_status()
            return r.json()
        return await asyncio.to_thread(_call)

    async def send_message(self, chat_id: int | str, text: str, *,
                           parse_mode: str | None = None,
                           disable_web_page_preview: bool | None = None,
                           **_kw) -> dict:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if disable_web_page_preview is not None:
            payload["disable_web_page_preview"] = disable_web_page_preview
        return await self._post("sendMessage", json=payload)

    async def send_photo(self, chat_id: int | str, photo, *,
                         caption: str | None = None, parse_mode: str | None = None,
                         **_kw) -> dict:
        data: dict[str, Any] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        files = {"photo": self._to_file(photo)}
        return await self._post("sendPhoto", data=data, files=files, timeout=180)

    async def send_video(self, chat_id: int | str, video, *,
                         caption: str | None = None, parse_mode: str | None = None,
                         supports_streaming: bool = True, **_kw) -> dict:
        data: dict[str, Any] = {"chat_id": str(chat_id),
                                "supports_streaming": "true" if supports_streaming else "false"}
        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        files = {"video": self._to_file(video)}
        return await self._post("sendVideo", data=data, files=files, timeout=600)

    async def send_document(self, chat_id: int | str, document, *,
                            caption: str | None = None, **_kw) -> dict:
        data: dict[str, Any] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        files = {"document": self._to_file(document)}
        return await self._post("sendDocument", data=data, files=files, timeout=300)

    async def send_photo(self, chat_id: int | str, photo, *,
                         caption: str | None = None, **_kw) -> dict:
        data: dict[str, Any] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        files = {"photo": self._to_file(photo)}
        return await self._post("sendPhoto", data=data, files=files, timeout=180)

    async def pin_chat_message(self, chat_id: int | str, message_id: int,
                                disable_notification: bool = True, **_kw) -> dict:
        return await self._post("pinChatMessage", json={
            "chat_id": chat_id, "message_id": message_id,
            "disable_notification": disable_notification,
        })

    async def unpin_chat_message(self, chat_id: int | str, message_id: int, **_kw) -> dict:
        return await self._post("unpinChatMessage", json={
            "chat_id": chat_id, "message_id": message_id,
        })

    @staticmethod
    def _to_file(x):
        if isinstance(x, (str, Path)):
            return open(str(x), "rb")
        if isinstance(x, (bytes, bytearray)):
            return io.BytesIO(bytes(x))
        return x  # file-like ya


class _FakeJob:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id


class FakeCtx:
    """Contexto sintético que replica la firma de PTB `ContextTypes.DEFAULT_TYPE`.

    Solo expone `.bot` (HTTP wrapper) y `.job` (con `chat_id`). El resto de
    atributos que PTB inyecta (user_data, chat_data, application, etc.) no los
    usa ningún handler de los que ejecutamos aquí — si alguno los usa en el
    futuro, romperá ruidosamente en vez de silenciosamente.
    """

    def __init__(self, chat_id: int | None = None):
        self.bot = _HttpTelegramBot(telegram_token())
        self.job = _FakeJob(chat_id if chat_id is not None else telegram_chat_id())


# --------------------------------------------------------------------------- #
# Entrypoints
# --------------------------------------------------------------------------- #

async def _run_autogen_impl() -> None:
    from . import telegram_bot
    ctx = FakeCtx()
    await telegram_bot._auto_generate_daily_short(ctx)


async def _run_longgen_impl() -> None:
    from . import telegram_bot
    ctx = FakeCtx()
    await telegram_bot._auto_generate_weekly_longform(ctx)


async def _run_hourly_catchup_impl() -> None:
    from . import telegram_bot
    ctx = FakeCtx()
    await telegram_bot._hourly_autogen_check(ctx)


async def _run_weekly_catchup_impl() -> None:
    from . import telegram_bot
    ctx = FakeCtx()
    await telegram_bot._weekly_longgen_catchup(ctx)


async def _run_daily_summary_impl() -> None:
    from . import telegram_bot
    ctx = FakeCtx()
    await telegram_bot.daily_summary(ctx)


async def _dispatch_command_impl(cmd: str, args_text: str = "") -> None:
    """Ejecuta un comando del bot como si el usuario lo hubiese enviado.

    Usado por el webhook Vercel: recibe `{"command": "autogen", "args": ""}` y
    despacha aquí. Comandos soportados = mismos que el bot en polling.
    """
    from . import telegram_bot

    ctx = FakeCtx()
    # `Update` sintético mínimo: los handlers usan solo update.effective_chat.id
    # y (a veces) update.message.text.
    class _FakeChat:
        id = ctx.job.chat_id
    class _FakeMessage:
        text = f"/{cmd} {args_text}".strip()
        async def reply_text(self, text, **_kw):
            await ctx.bot.send_message(ctx.job.chat_id, text)
    class _FakeUpdate:
        effective_chat = _FakeChat()
        message = _FakeMessage()

    update = _FakeUpdate()
    table = {
        "autogen": telegram_bot.autogen_cmd,
        "longgen": telegram_bot.longgen_cmd,
        "snapshot": telegram_bot.snapshot_cmd,
        "atomize": telegram_bot.atomize_cmd,
        "send": telegram_bot.send_cmd,
        "ideas": telegram_bot.ideas_cmd,
        "stats": telegram_bot.stats_cmd,
        "help": telegram_bot.help_cmd,
        "start": telegram_bot.start,
    }
    handler = table.get(cmd)
    if not handler:
        await ctx.bot.send_message(ctx.job.chat_id, f"❌ Comando desconocido: /{cmd}")
        return
    await handler(update, ctx)


# --------------------------------------------------------------------------- #
# Sync wrappers para CLI (click)
# --------------------------------------------------------------------------- #

def run_autogen() -> None:
    asyncio.run(_run_autogen_impl())


def run_longgen() -> None:
    asyncio.run(_run_longgen_impl())


def run_hourly_catchup() -> None:
    asyncio.run(_run_hourly_catchup_impl())


def run_weekly_catchup() -> None:
    asyncio.run(_run_weekly_catchup_impl())


def run_daily_summary() -> None:
    asyncio.run(_run_daily_summary_impl())


def dispatch_command(cmd: str, args_text: str = "") -> None:
    asyncio.run(_dispatch_command_impl(cmd, args_text))
