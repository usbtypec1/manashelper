import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject
from dishka import AsyncContainer
from dishka.integrations.aiogram import CONTAINER_NAME

from manashelper.platform.telegram.middlewares.after_request import AfterRequestActions
from ui_flows.application.locations import LocationService

logger = logging.getLogger(__name__)


class ObservationCoordinator:
    def __init__(self, container: AsyncContainer) -> None:
        self._container = container

    async def observe(self, user_id: int, chat_id: int, update_id: int, handler: str, state: FSMContext) -> None:
        try:
            current = await state.get_state()
            async with self._container() as request:
                await (await request.get(LocationService)).observe(user_id, chat_id, update_id, handler, current)
        except Exception:
            logger.exception("Could not persist legacy step metadata")

    async def restart(self) -> None:
        async with self._container() as request:
            await (await request.get(LocationService)).forget_legacy()


class UiFlowObservationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        result = await handler(event, data)
        chat, user, state = data.get("event_chat"), data.get("event_from_user"), data.get("state")
        if chat is None or user is None or state is None or chat.type != ChatType.PRIVATE or get_flag(data, "ui_flow"):
            return result
        request: AsyncContainer = data[CONTAINER_NAME]
        coordinator = await request.get(ObservationCoordinator)
        callback = data["handler"].callback
        name = callback.__module__ + "." + callback.__qualname__
        actions: AfterRequestActions = data["after_request"]
        update_id = data["event_update"].update_id
        actions.add(lambda: coordinator.observe(user.id, chat.id, update_id, name, state))
        return result
