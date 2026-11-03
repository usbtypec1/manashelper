from contextlib import suppress

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramRetryAfter, TelegramServerError
from aiogram.methods.base import Response, TelegramMethod, TelegramType


class TelegramSession(AiohttpSession):
    """Keep retryable HTTP statuses even when an upstream proxy returns HTML."""

    def check_response(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        status_code: int,
        content: str,
    ) -> Response[TelegramType]:
        if status_code >= 500:
            raise TelegramServerError(method, "Telegram upstream server error")
        if status_code == 429:
            retry_after = 1
            with suppress(ValueError, TypeError, AttributeError):
                retry_after = max(1, int(self.json_loads(content).get("parameters", {}).get("retry_after", 1)))
            raise TelegramRetryAfter(method, "Telegram flood control", retry_after=retry_after)
        return super().check_response(bot, method, status_code, content)
