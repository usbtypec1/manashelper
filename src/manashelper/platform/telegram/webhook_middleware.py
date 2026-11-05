from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from dishka.integrations.aiogram import CONTAINER_NAME
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.platform.telegram.webhook_models import ProcessedTelegramUpdate


class ConcurrentWebhookUpdateError(Exception):
    """A delivery of this update is already being processed; Telegram should retry."""


class WebhookReceiptMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        assert isinstance(event, Update)
        session = await data[CONTAINER_NAME].get(AsyncSession)
        locked = await session.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": event.update_id})
        if not locked:
            raise ConcurrentWebhookUpdateError()
        if await session.get(ProcessedTelegramUpdate, event.update_id) is not None:
            return None
        result = await handler(event, data)
        now = datetime.now(UTC)
        # Same REQUEST session and commit as the business changes. A crash cannot
        # commit an achievement without its receipt (or the other way around).
        session.add(ProcessedTelegramUpdate(update_id=event.update_id, processed_at=now))
        await session.execute(
            delete(ProcessedTelegramUpdate).where(ProcessedTelegramUpdate.processed_at < now - timedelta(days=7))
        )
        return result
