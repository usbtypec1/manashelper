from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, User
from dishka import AsyncContainer
from dishka.integrations.aiogram import CONTAINER_NAME

from manashelper.modules.users.queries import UsersQuery


class UserBlockingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Telegram does not identify the account behind a message sent as a chat.
        assert isinstance(event, Update)
        if event.message is not None and event.message.sender_chat is not None:
            return None
        user: User | None = data.get("event_from_user")
        if user is not None:
            container: AsyncContainer = data[CONTAINER_NAME]
            if await (await container.get(UsersQuery)).is_blocked(user.id):
                return None
        return await handler(event, data)
