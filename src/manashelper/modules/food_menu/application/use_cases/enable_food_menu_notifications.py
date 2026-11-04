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
class EnableFoodMenuNotificationsUseCase:
    food_menu_notification_settings_repository: FoodMenuNotificationSettingsRepository
    users: UsersQuery

    async def execute(self, user_id: int) -> FoodMenuNotificationSettingsSummary:
        await ensure_food_menu_user_exists(self.users, user_id)
        await self.food_menu_notification_settings_repository.reset_to_default(user_id)
        return await build_food_menu_settings_summary(self.food_menu_notification_settings_repository, user_id)
