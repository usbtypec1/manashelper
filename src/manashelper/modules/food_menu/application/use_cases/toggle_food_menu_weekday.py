from dataclasses import dataclass

from manashelper.modules.food_menu.application.food_menu_notification_settings import (
    FoodMenuNotificationSettingsSummary,
    build_food_menu_settings_summary,
    ensure_food_menu_user_exists,
)
from manashelper.modules.food_menu.infrastructure.repositories.food_menu_notification_settings import (
    FoodMenuNotificationSettingsRepository,
)
from manashelper.modules.users.queries import UsersQuery


@dataclass(frozen=True, slots=True)
class ToggleFoodMenuWeekdayUseCase:
    food_menu_notification_settings_repository: FoodMenuNotificationSettingsRepository
    users: UsersQuery

    async def execute(self, user_id: int, weekday: int) -> FoodMenuNotificationSettingsSummary:
        await ensure_food_menu_user_exists(self.users, user_id)
        settings = await self.food_menu_notification_settings_repository.get_or_create(user_id, weekday)
        new_value = not (settings.lunch_enabled and settings.dinner_enabled)
        settings.lunch_enabled = new_value
        settings.dinner_enabled = new_value
        return await build_food_menu_settings_summary(self.food_menu_notification_settings_repository, user_id)
