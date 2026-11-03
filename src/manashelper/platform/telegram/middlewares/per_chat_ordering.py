import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from dishka import AsyncContainer


class ChatOrdering:
    """One APP-owned gate shared by updates and post-commit screen delivery."""

    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}

    def lock(self, chat_id: int) -> asyncio.Lock:
        return self._locks.setdefault(chat_id, asyncio.Lock())


class PerChatOrderingMiddleware(BaseMiddleware):
    """Serializes update processing per chat while letting different chats run concurrently.

    Course-tracking is a read-modify-write over a user's tracked courses; without this,
    two updates from the same chat arriving close together could race on that mutation.
    """

    def __init__(self, container: AsyncContainer | None = None) -> None:
        self._container = container
        self._ordering = ChatOrdering()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = data.get("event_chat")
        if chat is None:
            return await handler(event, data)

        ordering = await self._container.get(ChatOrdering) if self._container is not None else self._ordering
        async with ordering.lock(chat.id):
            return await handler(event, data)
