import logging

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.modules.food_menu.application.broadcast import BroadcastFoodMenu, FoodMenuSender
from manashelper.modules.food_menu.application.food_menu_cleanup_settings import FoodMenuCleanupSettingsService
from manashelper.modules.food_menu.application.food_menu_notification_settings import FoodMenuMeal
from manashelper.modules.food_menu.application.food_menu_sync import FoodMenuSyncService
from manashelper.modules.food_menu.presentation.sender import TelegramFoodMenuSender
from manashelper.modules.users.application.locale import LocaleService

logger = logging.getLogger(__name__)


async def sync_daily_menus_job(container: AsyncContainer) -> None:
    try:
        async with container() as request_container:
            service = await request_container.get(FoodMenuSyncService)
            await service.synchronize_daily_menus()
    except Exception:
        logger.exception("Failed to synchronize daily menus")


async def _broadcast_menu_job(container: AsyncContainer, bot: Bot, meal: FoodMenuMeal) -> None:
    try:
        async with container() as request_container:
            service = await request_container.get(BroadcastFoodMenu)
            locales = await request_container.get(LocaleService)
            cleanup = await request_container.get(FoodMenuCleanupSettingsService)
            sender: FoodMenuSender = TelegramFoodMenuSender(bot, locales, cleanup)
            await service.execute(meal, sender)
    except Exception:
        logger.exception("Failed to broadcast %s menu", meal.value)


async def broadcast_lunch_menu_job(container: AsyncContainer, bot: Bot) -> None:
    await _broadcast_menu_job(container, bot, FoodMenuMeal.LUNCH)


async def broadcast_dinner_menu_job(container: AsyncContainer, bot: Bot) -> None:
    await _broadcast_menu_job(container, bot, FoodMenuMeal.DINNER)
