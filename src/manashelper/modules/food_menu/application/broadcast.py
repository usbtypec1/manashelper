import logging
from datetime import datetime
from typing import Protocol

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.food_menu.application.daily_menu import (
    DailyMenuModel,
    DailyMenuNotFoundError,
    DailyMenuService,
)
from manashelper.modules.food_menu.application.food_menu_notification_settings import FoodMenuMeal
from manashelper.modules.food_menu.infrastructure.repositories.food_menu_notification_settings_repository import (
    FoodMenuNotificationSettingsRepository,
)

logger = logging.getLogger(__name__)


class FoodMenuSender(Protocol):
    async def send(self, daily_menu: DailyMenuModel, user_id: int) -> None: ...


class BroadcastFoodMenu:
    def __init__(self, menus: DailyMenuService, settings: FoodMenuNotificationSettingsRepository) -> None:
        self._menus = menus
        self._settings = settings

    async def execute(self, meal: FoodMenuMeal, sender: FoodMenuSender) -> None:
        try:
            daily_menu = await self._menus.get_daily_menu_by_skipping_days(0)
        except DailyMenuNotFoundError:
            logger.warning("No daily menu to broadcast for %s", meal.value)
            return
        weekday = datetime.now(BISHKEK_TZ).date().weekday()
        if meal is FoodMenuMeal.LUNCH:
            user_ids = await self._settings.get_user_ids_with_lunch_enabled_for_weekday(weekday)
        else:
            user_ids = await self._settings.get_user_ids_with_dinner_enabled_for_weekday(weekday)
        for user_id in user_ids:
            await sender.send(daily_menu, user_id)
