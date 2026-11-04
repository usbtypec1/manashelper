from dataclasses import dataclass
from enum import StrEnum

from manashelper.modules.food_menu.infrastructure.models.food_menu_notification_settings import (
    FoodMenuNotificationSettings,
)
from manashelper.modules.food_menu.infrastructure.repositories.food_menu_notification_settings import (
    WEEKDAYS,
    FoodMenuNotificationSettingsRepository,
)
from manashelper.modules.users.queries import UsersQuery


class UserNotFoundError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} not found")
        self.user_id = user_id


class FoodMenuMeal(StrEnum):
    LUNCH = "lunch"
    DINNER = "dinner"


@dataclass(frozen=True, slots=True)
class DayNotificationSettings:
    weekday: int
    lunch_enabled: bool
    dinner_enabled: bool


@dataclass(frozen=True, slots=True)
class FoodMenuNotificationSettingsSummary:
    days: list[DayNotificationSettings]


def is_meal_enabled(by_weekday: dict[int, FoodMenuNotificationSettings], weekday: int, meal: FoodMenuMeal) -> bool:
    if weekday not in by_weekday:
        return True
    settings = by_weekday[weekday]
    return settings.lunch_enabled if meal is FoodMenuMeal.LUNCH else settings.dinner_enabled


@dataclass(frozen=True, slots=True)
class FoodMenuSettingsQuery:
    food_menu_notification_settings_repository: FoodMenuNotificationSettingsRepository
    users: UsersQuery

    async def get_settings(self, user_id: int) -> FoodMenuNotificationSettingsSummary:
        await ensure_food_menu_user_exists(self.users, user_id)
        return await build_food_menu_settings_summary(self.food_menu_notification_settings_repository, user_id)


async def build_food_menu_settings_summary(
    food_menu_notification_settings_repository: FoodMenuNotificationSettingsRepository, user_id: int
) -> FoodMenuNotificationSettingsSummary:
    rows = await food_menu_notification_settings_repository.get_all_by_user_id(user_id)
    by_weekday = {row.weekday: row for row in rows}
    days = [
        DayNotificationSettings(
            weekday=weekday,
            lunch_enabled=by_weekday[weekday].lunch_enabled if weekday in by_weekday else True,
            dinner_enabled=by_weekday[weekday].dinner_enabled if weekday in by_weekday else True,
        )
        for weekday in WEEKDAYS
    ]
    return FoodMenuNotificationSettingsSummary(days=days)


async def ensure_food_menu_user_exists(users: UsersQuery, user_id: int) -> None:
    if not await users.exists(user_id):
        raise UserNotFoundError(user_id)
