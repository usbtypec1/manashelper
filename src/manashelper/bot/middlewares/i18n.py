from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from dishka import AsyncContainer
from dishka.integrations.aiogram import CONTAINER_NAME

from manashelper.bot.callback_data import LocaleCallback
from manashelper.bot.keyboards.locale import LOCALE_PROMPT_TEXT, build_locale_keyboard
from manashelper.localization.i18n import i18n
from manashelper.services.locale import LocaleService

_LOCALE_CALLBACK_PREFIX = f"{LocaleCallback.__prefix__}:"


class LocaleMiddleware(BaseMiddleware):
    """Resolves the current user's locale before any handler runs and activates aiogram's
    gettext context for it (see `localization/i18n.py`), so every `_()`/`ngettext()` call made
    while handling this update — in filters, handlers, and formatters alike — resolves
    against that locale without needing it threaded through as a parameter.

    If the locale can't be determined (a new user whose Telegram client language isn't one of
    the supported ones), it shows a language picker and stops propagation instead of calling
    the handler — except for a tap on that very picker (a `LocaleCallback`), which must reach
    `bot/routers/locale.py::on_locale_selected` or the user could never get past it.

    Must be registered *after* `setup_dishka` on the same observers, so `data[CONTAINER_NAME]`
    is already a request-scoped container by the time this runs — see main.py.
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
        )

        if locale is None:
            if isinstance(event, CallbackQuery) and (event.data or "").startswith(_LOCALE_CALLBACK_PREFIX):
                return await handler(event, data)
            await _prompt_locale_selection(event)
            return None

        data["locale"] = locale
        with i18n.context(), i18n.use_locale(locale.value):
            return await handler(event, data)


async def _prompt_locale_selection(event: TelegramObject) -> None:
    if isinstance(event, Message):
        await event.answer(LOCALE_PROMPT_TEXT, reply_markup=build_locale_keyboard())
        return

    if isinstance(event, CallbackQuery):
        await event.answer()
        if isinstance(event.message, Message):
            await event.message.answer(LOCALE_PROMPT_TEXT, reply_markup=build_locale_keyboard())
