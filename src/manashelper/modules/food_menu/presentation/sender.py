import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from manashelper.modules.food_menu.application.daily_menu import DailyMenuModel
from manashelper.modules.food_menu.application.food_menu_cleanup_settings import FoodMenuCleanupSettingsService
from manashelper.modules.food_menu.presentation.food_menu_formatter import build_daily_menu_rich_message
from manashelper.modules.food_menu.presentation.keyboards.food_menu import (
    build_food_menu_settings_buttons,
    build_menu_rating_buttons,
)
from manashelper.modules.users.application.bot_status import BotStatusService
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.delivery import UserMessageDelivery

logger = logging.getLogger(__name__)


class TelegramFoodMenuSender:
    def __init__(
        self,
        bot: Bot,
        locales: LocaleService,
        cleanup: FoodMenuCleanupSettingsService,
        themes: ThemeService,
        status: BotStatusService,
    ) -> None:
        self._bot = bot
        self._locales = locales
        self._cleanup = cleanup
        self._themes = themes
        self._delivery = UserMessageDelivery(status)

    async def send(self, daily_menu: DailyMenuModel, user_id: int) -> None:
        try:
            locale = await self._locales.get_locale(user_id)
            theme = await self._themes.get_theme(user_id)
            with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
                rich_message = build_daily_menu_rich_message(
                    daily_menu,
                    build_menu_rating_buttons(daily_menu.id),
                    build_food_menu_settings_buttons(include_notifications=True),
                )
            sent = await self._delivery.send(
                user_id, lambda: self._bot.send_rich_message(chat_id=user_id, rich_message=rich_message)
            )
            if sent is not None:
                await self._cleanup.schedule_cleanup(user_id, [sent.message_id])
        except TelegramAPIError:
            logger.warning("Failed to send food menu broadcast to user %s", user_id, exc_info=True)
