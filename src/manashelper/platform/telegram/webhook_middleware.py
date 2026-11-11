from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from dishka.integrations.aiogram import CONTAINER_NAME

from manashelper.platform.telegram.webhook_service import WebhookReceiptService


class WebhookReceiptMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        assert isinstance(event, Update)
        receipts = await data[CONTAINER_NAME].get(WebhookReceiptService)
        if not await receipts.begin(event.update_id):
            return None
        result = await handler(event, data)
        await receipts.complete(event.update_id)
        return result
