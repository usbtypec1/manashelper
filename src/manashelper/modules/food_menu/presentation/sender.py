from datetime import UTC, datetime, timedelta

from aiogram.methods import SendRichMessage

from manashelper.modules.food_menu.application.daily_menu import DailyMenuModel
from manashelper.modules.food_menu.presentation.food_menu_formatter import build_daily_menu_rich_message
from manashelper.modules.food_menu.presentation.keyboards.food_menu import (
    build_food_menu_settings_buttons,
    build_menu_rating_buttons,
)
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.outbox.service import OutboxService


class TelegramFoodMenuSender:
    def __init__(
        self,
        outbox: OutboxService,
        locales: LocaleQuery,
        themes: ThemeQuery,
    ) -> None:
        self._outbox = outbox
        self._locales = locales
        self._themes = themes

    async def send(self, daily_menu: DailyMenuModel, user_id: int) -> None:
        locale = await self._locales.get_locale(user_id)
        theme = await self._themes.get_theme(user_id)
        with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
            rich_message = build_daily_menu_rich_message(
                daily_menu,
                build_menu_rating_buttons(daily_menu.id),
                build_food_menu_settings_buttons(),
            )
        await self._outbox.enqueue(
            user_id,
            [SendRichMessage(chat_id=user_id, rich_message=rich_message)],
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        )
