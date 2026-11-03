from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.dispatcher.flags import get_flag
from aiogram.enums import ChatType
from aiogram.types import TelegramObject, Update
from dishka import AsyncContainer
from dishka.integrations.aiogram import CONTAINER_NAME

from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.platform.telegram.middlewares.after_request import AfterRequestActions
from ui_flows.application.dialogs import DialogService
from ui_flows.domain.state import RuntimeUser


class UiFlowNavigationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat, user = data.get("event_chat"), data.get("event_from_user")
        if (
            chat is not None
            and user is not None
            and chat.type == ChatType.PRIVATE
            and chat.id == user.id
            and not get_flag(data, "ui_flow")
        ):
            request: AsyncContainer = data[CONTAINER_NAME]
            dialogs = await request.get(DialogService)
            if await dialogs.active(RuntimeUser(user.id, chat.id)) is not None:
                coordinator = await request.get(FlowTelegramCoordinator)
                actions: AfterRequestActions = data["after_request"]
                update: Update = data["event_update"]
                bot: Bot = data["bot"]
                if get_flag(data, "refresh_ui_flow"):
                    actions.add(lambda: coordinator.refresh(bot, user.id, update.update_id))
                elif (
                    not get_flag(data, "preserve_ui_flow")
                    and getattr(data.get("ingress_route"), "policy", None) != "preserve"
                ):
                    actions.add(lambda: coordinator.leave(user.id, update.update_id))
        return await handler(event, data)
