"""Synchronous webhook acknowledgement; no aiogram timeout/background handoff."""

import asyncio
import hmac

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiohttp import web
from pydantic import ValidationError

from manashelper.core.config import Settings


def install_webhook(app: web.Application, bot: Bot, dispatcher: Dispatcher, settings: Settings) -> None:
    if settings.telegram_webhook_secret is None:
        raise ValueError("Configure MANASHELPER_TELEGRAM_WEBHOOK_SECRET for webhook transport")
    secret = settings.telegram_webhook_secret.get_secret_value().encode()
    slots = asyncio.Semaphore(32)

    async def receive(request: web.Request) -> web.Response:
        if not hmac.compare_digest(secret, request.headers.get("X-Telegram-Bot-Api-Secret-Token", "").encode()):
            raise web.HTTPForbidden()
        if slots.locked():
            raise web.HTTPServiceUnavailable()
        async with slots:
            try:
                payload = await request.json()
                if not isinstance(payload, dict) or set(payload) - {"update_id", "message", "callback_query"}:
                    raise ValueError("Unsupported update")
                if sum(payload.get(kind) is not None for kind in ("message", "callback_query")) != 1:
                    raise ValueError("One supported update is required")
                update = Update.model_validate(payload, context={"bot": bot})
            except (ValueError, ValidationError) as error:
                raise web.HTTPBadRequest() from error
            await dispatcher.feed_update(bot, update, webhook=True)
            # State/receipts/intent have committed and after-request work finished.
            return web.json_response({"ok": True})

    app.router.add_post("/telegram/webhook", receive)
