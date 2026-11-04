from dataclasses import dataclass
from datetime import datetime

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.food_menu.application.broadcast import FoodMenuSender, logger
from manashelper.modules.food_menu.application.daily_menu import (
    DailyMenuNotFoundError,
)
from manashelper.modules.food_menu.application.food_menu_notification_settings import FoodMenuMeal
from manashelper.modules.food_menu.application.use_cases.get_daily_menu_by_offset import GetDailyMenuByOffsetUseCase
from manashelper.modules.food_menu.infrastructure.repositories.food_menu_notification_settings import (
    FoodMenuNotificationSettingsRepository,
)


@dataclass(frozen=True, slots=True)
class BroadcastFoodMenuUseCase:
    get_daily_menu_by_offset: GetDailyMenuByOffsetUseCase
    settings: FoodMenuNotificationSettingsRepository

    async def execute(self, meal: FoodMenuMeal, sender: FoodMenuSender) -> None:
        try:
            daily_menu = await self.get_daily_menu_by_offset.execute(0)
        except DailyMenuNotFoundError:
            logger.warning("No daily menu to broadcast for %s", meal.value)
            return
        weekday = datetime.now(BISHKEK_TZ).date().weekday()
        if meal is FoodMenuMeal.LUNCH:
            user_ids = await self.settings.get_user_ids_with_lunch_enabled_for_weekday(weekday)
        else:
            user_ids = await self.settings.get_user_ids_with_dinner_enabled_for_weekday(weekday)
        for user_id in user_ids:
            await sender.send(daily_menu, user_id)
