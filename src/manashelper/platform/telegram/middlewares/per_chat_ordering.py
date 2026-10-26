import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class PerChatOrderingMiddleware(BaseMiddleware):
    """Serializes update processing per chat while letting different chats run concurrently.

    Course-tracking is a read-modify-write over a user's tracked courses; without this,
    two updates from the same chat arriving close together could race on that mutation.
    """

    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = data.get("event_chat")
        if chat is None:
            return await handler(event, data)

        lock = self._locks.setdefault(chat.id, asyncio.Lock())
        async with lock:
            return await handler(event, data)
