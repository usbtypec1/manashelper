from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import TelegramObject
from dishka import AsyncContainer
from dishka.integrations.aiogram import CONTAINER_NAME

from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.platform.i18n.catalog import i18n


class LocaleMiddleware(BaseMiddleware):
    """Resolves the current user's locale and saved menu theme, and activates aiogram's
    gettext context for it (see `localization/i18n.py`), so every `_()`/`ngettext()` call made
    while handling this update — in filters, handlers, and formatters alike — resolves
    against that locale without needing it threaded through as a parameter.

    The locale is always resolved: a saved locale wins, otherwise it's auto-detected from the
    Telegram client's language, falling back to `DEFAULT_LOCALE` (see
    `localization/locale.py::resolve_from_language_code`) — there's no picker shown here, only
    via the explicit `/language` command/setting in Users presentation.

    Must be registered *after* `setup_dishka` on the same observers, so `data[CONTAINER_NAME]`
    is already a request-scoped container by the time this runs — see bot/dispatcher.py.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_user = data.get("event_from_user")
        if telegram_user is None:
            return await handler(event, data)

        container: AsyncContainer = data[CONTAINER_NAME]
        locale_service = await container.get(LocaleService)
        locale = await locale_service.resolve(
            user_id=telegram_user.id,
            full_name=telegram_user.full_name,
            username=telegram_user.username,
            language_code=telegram_user.language_code,
            resume_bot=getattr(data.get("event_chat"), "type", None) == ChatType.PRIVATE,
        )

        theme_service = await container.get(ThemeService)
        theme = await theme_service.get_theme(telegram_user.id)
        data["locale"] = locale
        with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
            return await handler(event, data)
