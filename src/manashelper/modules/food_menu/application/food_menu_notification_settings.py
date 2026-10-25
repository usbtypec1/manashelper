from dataclasses import dataclass
from enum import StrEnum

from manashelper.db.models import FoodMenuNotificationSettings
from manashelper.modules.food_menu.infrastructure.repositories.food_menu_notification_settings_repository import (
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


def _is_meal_enabled(by_weekday: dict[int, FoodMenuNotificationSettings], weekday: int, meal: FoodMenuMeal) -> bool:
    if weekday not in by_weekday:
        return True
    settings = by_weekday[weekday]
    return settings.lunch_enabled if meal is FoodMenuMeal.LUNCH else settings.dinner_enabled


class FoodMenuNotificationSettingsService:
    def __init__(
        self,
        food_menu_notification_settings_repository: FoodMenuNotificationSettingsRepository,
        users: UsersQuery,
    ) -> None:
        self._food_menu_notification_settings_repository = food_menu_notification_settings_repository
        self._users = users

    async def get_settings(self, user_id: int) -> FoodMenuNotificationSettingsSummary:
        await self._ensure_user_exists(user_id)
        return await self._build_summary(user_id)

    async def toggle(self, user_id: int, weekday: int, meal: FoodMenuMeal) -> FoodMenuNotificationSettingsSummary:
        await self._ensure_user_exists(user_id)
        settings = await self._food_menu_notification_settings_repository.get_or_create(user_id, weekday)
        if meal is FoodMenuMeal.LUNCH:
            settings.lunch_enabled = not settings.lunch_enabled
        else:
            settings.dinner_enabled = not settings.dinner_enabled
        return await self._build_summary(user_id)

    async def toggle_weekday(self, user_id: int, weekday: int) -> FoodMenuNotificationSettingsSummary:
        await self._ensure_user_exists(user_id)
        settings = await self._food_menu_notification_settings_repository.get_or_create(user_id, weekday)
        new_value = not (settings.lunch_enabled and settings.dinner_enabled)
        settings.lunch_enabled = new_value
        settings.dinner_enabled = new_value
        return await self._build_summary(user_id)

    async def toggle_meal(self, user_id: int, meal: FoodMenuMeal) -> FoodMenuNotificationSettingsSummary:
        await self._ensure_user_exists(user_id)
        rows = await self._food_menu_notification_settings_repository.get_all_by_user_id(user_id)
        by_weekday = {row.weekday: row for row in rows}
        all_enabled = all(_is_meal_enabled(by_weekday, weekday, meal) for weekday in WEEKDAYS)
        new_value = not all_enabled
        for weekday in WEEKDAYS:
            settings = await self._food_menu_notification_settings_repository.get_or_create(user_id, weekday)
            if meal is FoodMenuMeal.LUNCH:
                settings.lunch_enabled = new_value
            else:
                settings.dinner_enabled = new_value
        return await self._build_summary(user_id)

    async def enable_all(self, user_id: int) -> FoodMenuNotificationSettingsSummary:
        await self._ensure_user_exists(user_id)
        await self._food_menu_notification_settings_repository.reset_to_default(user_id)
        return await self._build_summary(user_id)

    async def disable_all(self, user_id: int) -> FoodMenuNotificationSettingsSummary:
        await self._ensure_user_exists(user_id)
        await self._food_menu_notification_settings_repository.disable_all(user_id)
        return await self._build_summary(user_id)

    async def _ensure_user_exists(self, user_id: int) -> None:
        if not await self._users.exists(user_id):
            raise UserNotFoundError(user_id)

    async def _build_summary(self, user_id: int) -> FoodMenuNotificationSettingsSummary:
        rows = await self._food_menu_notification_settings_repository.get_all_by_user_id(user_id)
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
