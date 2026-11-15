import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType, ParseMode
from aiogram.types import CallbackQuery, Message, TelegramObject

from manashelper.localization.locale import DEFAULT_LOCALE
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.html import escape_html
from manashelper.platform.telegram.middlewares.token_bucket import TokenBucket

_WARNING_COOLDOWN_SECONDS = 3.0


class RateLimitMiddleware(BaseMiddleware):
    """Per-chat token-bucket rate limiting.

    Registered as an outer middleware ahead of `PerChatOrderingMiddleware` so an over-limit
    update is rejected before it even queues up for that chat's lock. Each chat gets its own
    bucket (default: burst of `capacity`, refilling at `refill_rate` tokens/second), so one
    chat flooding the bot doesn't affect another chat's allowance.
    """

    def __init__(self, capacity: int = 10, refill_rate: float = 1.0) -> None:
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._buckets: dict[int, TokenBucket] = {}
        self._last_warned_at: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = data.get("event_chat")
        if chat is None:
            return await handler(event, data)

        bucket = self._buckets.setdefault(chat.id, TokenBucket(self._capacity, self._refill_rate))
        if bucket.try_consume():
            return await handler(event, data)

        await self._reject(event, chat.id)
        return None

    async def _reject(self, event: TelegramObject, chat_id: int) -> None:
        # Rate limiting runs before locale resolution; keep the existing default language.
        text = i18n.gettext("common.rate_limit", locale=DEFAULT_LOCALE.value)
        if isinstance(event, CallbackQuery):
            # Always answer, even without alert text, so the tap doesn't leave the button
            # spinning on the user's client.
            await event.answer(text, show_alert=False)
            return

        if not isinstance(event, Message):
            return

        # Cooled down separately from the bucket itself, so a message flood doesn't turn into
        # an equally sized flood of "you're rate limited" replies.
        now = time.monotonic()
        if now - self._last_warned_at.get(chat_id, 0.0) < _WARNING_COOLDOWN_SECONDS:
            return
        self._last_warned_at[chat_id] = now
        if event.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            # Anonymous administrators and channel posts expose only the sender chat.
            if event.sender_chat is not None:
                sender = event.sender_chat
                name = f"@{sender.username}" if sender.username else sender.title or str(sender.id)
                sender_id = sender.id
            elif event.from_user is not None:
                user = event.from_user
                name = f"@{user.username}" if user.username else user.full_name
                sender_id = user.id
            else:
                await event.answer(text)
                return
            text = i18n.gettext("common.rate_limit_group", locale=DEFAULT_LOCALE.value).format(
                sender=escape_html(name), sender_id=sender_id
            )
            await event.answer(text, parse_mode=ParseMode.HTML)
            return
        await event.answer(text)
