from dataclasses import dataclass

from manashelper.modules.food_menu.application.food_menu_notification_settings import (
    FoodMenuMeal,
    FoodMenuNotificationSettingsSummary,
    build_food_menu_settings_summary,
    ensure_food_menu_user_exists,
    is_meal_enabled,
)
from manashelper.modules.food_menu.infrastructure.repositories.food_menu_notification_settings import (
    WEEKDAYS,
    FoodMenuNotificationSettingsRepository,
)
from manashelper.modules.users.queries import UsersQuery


@dataclass(frozen=True, slots=True)
class ToggleFoodMenuMealForWeekUseCase:
    food_menu_notification_settings_repository: FoodMenuNotificationSettingsRepository
    users: UsersQuery

    async def execute(self, user_id: int, meal: FoodMenuMeal) -> FoodMenuNotificationSettingsSummary:
        await ensure_food_menu_user_exists(self.users, user_id)
        rows = await self.food_menu_notification_settings_repository.get_all_by_user_id(user_id)
        by_weekday = {row.weekday: row for row in rows}
        all_enabled = all(is_meal_enabled(by_weekday, weekday, meal) for weekday in WEEKDAYS)
        new_value = not all_enabled
        for weekday in WEEKDAYS:
            settings = await self.food_menu_notification_settings_repository.get_or_create(user_id, weekday)
            if meal is FoodMenuMeal.LUNCH:
                settings.lunch_enabled = new_value
            else:
                settings.dinner_enabled = new_value
        return await build_food_menu_settings_summary(self.food_menu_notification_settings_repository, user_id)
