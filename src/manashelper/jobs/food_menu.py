import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from dishka import AsyncContainer

from manashelper.bot.keyboards.food_menu import build_food_menu_settings_buttons, build_menu_rating_buttons
from manashelper.jobs.common import get_user_locale
from manashelper.localization.i18n import i18n
from manashelper.repositories.food_menu_notification_settings_repository import (
    FoodMenuNotificationSettingsRepository,
)
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.daily_menu import BISHKEK_TZ, DailyMenuModel, DailyMenuNotFoundError, DailyMenuService
from manashelper.services.food_menu_cleanup_settings import FoodMenuCleanupSettingsService
from manashelper.services.food_menu_formatter import build_daily_menu_rich_message
from manashelper.services.food_menu_sync import FoodMenuSyncService

logger = logging.getLogger(__name__)


async def sync_daily_menus_job(container: AsyncContainer) -> None:
    try:
        async with container() as request_container:
            service = await request_container.get(FoodMenuSyncService)
            await service.synchronize_daily_menus()
    except Exception:
        logger.exception("Failed to synchronize daily menus")


async def _send_daily_menu_broadcast(
    bot: Bot,
    user_repository: UserRepository,
    food_menu_cleanup_settings_service: FoodMenuCleanupSettingsService,
    daily_menu: DailyMenuModel,
    user_ids: list[int],
) -> None:
    for user_id in user_ids:
        try:
            locale = await get_user_locale(user_repository, user_id)
            with i18n.context(), i18n.use_locale(locale.value):
                rich_message = build_daily_menu_rich_message(
                    daily_menu,
                    build_menu_rating_buttons(daily_menu.id),
                    build_food_menu_settings_buttons(include_notifications=True),
                )
            sent = await bot.send_rich_message(chat_id=user_id, rich_message=rich_message)
            await food_menu_cleanup_settings_service.schedule_cleanup(user_id, [sent.message_id])
        except TelegramAPIError:
            logger.warning("Failed to send food menu broadcast to user %s", user_id, exc_info=True)


async def broadcast_lunch_menu_job(container: AsyncContainer, bot: Bot) -> None:
    try:
        async with container() as request_container:
            daily_menu_service = await request_container.get(DailyMenuService)
            user_repository = await request_container.get(UserRepository)
            food_menu_notification_settings_repository = await request_container.get(
                FoodMenuNotificationSettingsRepository
            )
            food_menu_cleanup_settings_service = await request_container.get(FoodMenuCleanupSettingsService)
            try:
                daily_menu = await daily_menu_service.get_daily_menu_by_skipping_days(0)
            except DailyMenuNotFoundError:
                logger.warning("No daily menu to broadcast for lunch")
                return
            weekday = datetime.now(BISHKEK_TZ).date().weekday()
            user_ids = await food_menu_notification_settings_repository.get_user_ids_with_lunch_enabled_for_weekday(
                weekday
            )
            await _send_daily_menu_broadcast(
                bot, user_repository, food_menu_cleanup_settings_service, daily_menu, user_ids
            )
    except Exception:
        logger.exception("Failed to broadcast lunch menu")


async def broadcast_dinner_menu_job(container: AsyncContainer, bot: Bot) -> None:
    try:
        async with container() as request_container:
            daily_menu_service = await request_container.get(DailyMenuService)
            user_repository = await request_container.get(UserRepository)
            food_menu_notification_settings_repository = await request_container.get(
                FoodMenuNotificationSettingsRepository
            )
            food_menu_cleanup_settings_service = await request_container.get(FoodMenuCleanupSettingsService)
            try:
                daily_menu = await daily_menu_service.get_daily_menu_by_skipping_days(0)
            except DailyMenuNotFoundError:
                logger.warning("No daily menu to broadcast for dinner")
                return
            weekday = datetime.now(BISHKEK_TZ).date().weekday()
            user_ids = await food_menu_notification_settings_repository.get_user_ids_with_dinner_enabled_for_weekday(
                weekday
            )
            await _send_daily_menu_broadcast(
                bot, user_repository, food_menu_cleanup_settings_service, daily_menu, user_ids
            )
    except Exception:
        logger.exception("Failed to broadcast dinner menu")
