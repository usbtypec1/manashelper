from collections.abc import Iterable
from datetime import timedelta
from enum import StrEnum

from manashelper.db.models.food_menu_cleanup_settings import DEFAULT_FOOD_MENU_CLEANUP_DELAY_MINUTES
from manashelper.repositories.food_menu_cleanup_settings_repository import FoodMenuCleanupSettingsRepository
from manashelper.services.message_deletion import MessageDeletionService


class FoodMenuCleanupOption(StrEnum):
    MINUTES_15 = "minutes_15"
    MINUTES_45 = "minutes_45"
    HOURS_3 = "hours_3"
    DAY_1 = "day_1"
    DISABLED = "disabled"


_OPTION_TO_DELAY_MINUTES: dict[FoodMenuCleanupOption, int | None] = {
    FoodMenuCleanupOption.MINUTES_15: 15,
    FoodMenuCleanupOption.MINUTES_45: 45,
    FoodMenuCleanupOption.HOURS_3: 180,
    FoodMenuCleanupOption.DAY_1: 24 * 60,
    FoodMenuCleanupOption.DISABLED: None,
}
_DELAY_MINUTES_TO_OPTION = {minutes: option for option, minutes in _OPTION_TO_DELAY_MINUTES.items()}

DEFAULT_FOOD_MENU_CLEANUP_OPTION = _DELAY_MINUTES_TO_OPTION[DEFAULT_FOOD_MENU_CLEANUP_DELAY_MINUTES]


def _delay_minutes_to_option(delay_minutes: int | None) -> FoodMenuCleanupOption:
    return _DELAY_MINUTES_TO_OPTION.get(delay_minutes, DEFAULT_FOOD_MENU_CLEANUP_OPTION)


class FoodMenuCleanupSettingsService:
    def __init__(
        self,
        food_menu_cleanup_settings_repository: FoodMenuCleanupSettingsRepository,
        message_deletion_service: MessageDeletionService,
    ) -> None:
        self._food_menu_cleanup_settings_repository = food_menu_cleanup_settings_repository
        self._message_deletion_service = message_deletion_service

    async def get_option(self, chat_id: int) -> FoodMenuCleanupOption:
        delay_minutes = await self._get_delay_minutes(chat_id)
        return _delay_minutes_to_option(delay_minutes)

    async def set_option(self, chat_id: int, option: FoodMenuCleanupOption) -> FoodMenuCleanupOption:
        settings = await self._food_menu_cleanup_settings_repository.get_or_create(chat_id)
        settings.delay_minutes = _OPTION_TO_DELAY_MINUTES[option]
        return option

    async def schedule_cleanup(self, chat_id: int, message_ids: Iterable[int]) -> None:
        delay_minutes = await self._get_delay_minutes(chat_id)
        if delay_minutes is None:
            return
        await self._message_deletion_service.schedule_deletion(chat_id, message_ids, timedelta(minutes=delay_minutes))

    async def _get_delay_minutes(self, chat_id: int) -> int | None:
        settings = await self._food_menu_cleanup_settings_repository.get_by_chat_id(chat_id)
        if settings is None:
            return DEFAULT_FOOD_MENU_CLEANUP_DELAY_MINUTES
        return settings.delay_minutes
