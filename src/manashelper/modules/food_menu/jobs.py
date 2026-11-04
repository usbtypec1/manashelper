import logging

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.modules.food_menu.application.broadcast import FoodMenuSender
from manashelper.modules.food_menu.application.food_menu_notification_settings import FoodMenuMeal
from manashelper.modules.food_menu.application.use_cases.broadcast_food_menu import BroadcastFoodMenuUseCase
from manashelper.modules.food_menu.application.use_cases.sync_food_menus import SyncFoodMenusUseCase
from manashelper.modules.food_menu.presentation.sender import TelegramFoodMenuSender
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.platform.telegram.outbox.service import OutboxService

logger = logging.getLogger(__name__)


async def sync_daily_menus_job(container: AsyncContainer) -> None:
    try:
        async with container() as request_container:
            sync_food_menus = await request_container.get(SyncFoodMenusUseCase)
            await sync_food_menus.execute()
    except Exception:
        logger.exception("Failed to synchronize daily menus")


async def _broadcast_menu_job(container: AsyncContainer, bot: Bot, meal: FoodMenuMeal) -> None:
    try:
        async with container() as request_container:
            broadcast_food_menu = await request_container.get(BroadcastFoodMenuUseCase)
            locales = await request_container.get(LocaleQuery)
            themes = await request_container.get(ThemeQuery)
            outbox = await request_container.get(OutboxService)
            sender: FoodMenuSender = TelegramFoodMenuSender(outbox, locales, themes)
            await broadcast_food_menu.execute(meal, sender)
    except Exception:
        logger.exception("Failed to broadcast %s menu", meal.value)


async def broadcast_lunch_menu_job(container: AsyncContainer, bot: Bot) -> None:
    await _broadcast_menu_job(container, bot, FoodMenuMeal.LUNCH)


async def broadcast_dinner_menu_job(container: AsyncContainer, bot: Bot) -> None:
    await _broadcast_menu_job(container, bot, FoodMenuMeal.DINNER)
