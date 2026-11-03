"""Validate Telegram's signed launch data; never trust initDataUnsafe."""

from collections import deque
from datetime import UTC, datetime
from time import monotonic
from urllib.parse import parse_qsl

from aiogram.utils.web_app import safe_parse_webapp_init_data

from manashelper.core.config import Settings


class InvalidInitDataError(Exception):
    pass


class TooManyExchangesError(Exception):
    pass


class TelegramMiniAppAuth:
    """Single-host exchange limit for the one configured administrator."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._exchanges: deque[float] = deque()

    def authenticate(self, init_data: str) -> int:
        try:
            pairs = parse_qsl(init_data, strict_parsing=True, keep_blank_values=True)
            if len({key for key, _ in pairs}) != len(pairs):
                raise ValueError("Duplicate fields")
            launch = safe_parse_webapp_init_data(self._settings.telegram_bot_token, init_data)
            age = (datetime.now(UTC) - launch.auth_date).total_seconds()
            if not 0 <= age <= 300 or launch.user is None or launch.user.id != self._settings.admin_chat_id:
                raise ValueError("Invalid launch context")
        except (ValueError, TypeError, OverflowError) as error:
            raise InvalidInitDataError("Telegram launch context is invalid or expired") from error
        now = monotonic()
        while self._exchanges and self._exchanges[0] <= now - 60:
            self._exchanges.popleft()
        if len(self._exchanges) >= 5:
            raise TooManyExchangesError("Wait before opening another administrative session")
        self._exchanges.append(now)
        return launch.user.id
