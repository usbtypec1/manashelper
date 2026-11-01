from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class AfterRequestActions:
    """Work to run only after the inner Dishka request has committed successfully."""

    def __init__(self) -> None:
        self._actions: list[Callable[[], Awaitable[None]]] = []

    def add(self, action: Callable[[], Awaitable[None]]) -> None:
        self._actions.append(action)

    async def run(self) -> None:
        for action in self._actions:
            await action()


class AfterRequestMiddleware(BaseMiddleware):
    """Register inside per-chat ordering, outside the Dishka container middleware."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        actions = AfterRequestActions()
        data["after_request"] = actions
        result = await handler(event, data)
        await actions.run()
        return result
