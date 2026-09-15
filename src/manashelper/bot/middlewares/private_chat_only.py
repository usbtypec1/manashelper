from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.utils.i18n import gettext as _

PRIVATE_CHAT_ONLY_FLAG = "private_chat_only"


class PrivateChatOnlyMiddleware(BaseMiddleware):
    """Blocks a handler flagged `private_chat_only` outside private chats, replying with an explanation instead.

    Must be registered as an inner middleware (`.middleware()`, not `.outer_middleware()`) — the
    `private_chat_only` flag lives on the matched `HandlerObject`, which `get_flag` only finds via
    `data["handler"]`, populated by `TelegramEventObserver.trigger` right before inner middlewares run.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not get_flag(data, PRIVATE_CHAT_ONLY_FLAG):
            return await handler(event, data)

        chat = data.get("event_chat")
        if chat is None or chat.type == ChatType.PRIVATE:
            return await handler(event, data)

        await _notify_private_chat_only(event)
        return None


async def _notify_private_chat_only(event: TelegramObject) -> None:
    text = _("This feature is only available in a private chat with the bot.")
    if isinstance(event, Message):
        await event.reply(text)
    elif isinstance(event, CallbackQuery):
        await event.answer(text, show_alert=True)
