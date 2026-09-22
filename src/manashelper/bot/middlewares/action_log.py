from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import CallbackQuery, Message, TelegramObject
from dishka import AsyncContainer
from dishka.integrations.aiogram import CONTAINER_NAME

from manashelper.services.action_log import ActionLogService

MASK_LOGGED_MESSAGE_FLAG = "mask_logged_message"
_MASKED_MESSAGE_TEXT = "[masked]"


class ActionLogMiddleware(BaseMiddleware):
    """Persists an update to the `action_logs` table, for basic usage auditing.

    Registered as an *inner* middleware (`.middleware()`, not `.outer_middleware()`) so it only
    fires for updates that matched a router's filters and were dispatched to a handler —
    `data["handler"]` is populated by `TelegramEventObserver.trigger` right before inner
    middlewares run, same as `PrivateChatOnlyMiddleware` — instead of logging every
    message/callback_query the bot receives regardless of whether anything handled it.
    Registered after `PrivateChatOnlyMiddleware` (see main.py) so it nests inside it and skips
    logging an attempt that middleware already rejected outside a private chat.

    A handler flagged `mask_logged_message` (see `bot/routers/obis.py::on_password_entered`)
    has its `message_text` replaced with a placeholder instead of the raw text — for handlers
    that collect sensitive free-text input (e.g. an OBIS password) that must never land in the
    log.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = data.get("event_chat")
        user = data.get("event_from_user")
        if chat is not None and user is not None:
            container: AsyncContainer = data[CONTAINER_NAME]
            action_log_service = await container.get(ActionLogService)
            if isinstance(event, CallbackQuery):
                action_log_service.log_callback_query(chat.id, user.id, event.data)
            elif isinstance(event, Message):
                message_text: str | None
                if get_flag(data, MASK_LOGGED_MESSAGE_FLAG):
                    message_text = _MASKED_MESSAGE_TEXT
                else:
                    message_text = event.text or event.caption
                action_log_service.log_message(chat.id, user.id, message_text)

        return await handler(event, data)
