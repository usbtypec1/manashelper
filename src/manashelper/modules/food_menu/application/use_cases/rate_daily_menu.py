import uuid
from dataclasses import dataclass

from manashelper.modules.food_menu.application.daily_menu import (
    DailyMenuModel,
    to_model,
)
from manashelper.modules.food_menu.infrastructure.repositories.daily_menu import DailyMenuRepository
from manashelper.modules.food_menu.infrastructure.repositories.daily_menu_rating import (
    DailyMenuRatingRepository,
)


@dataclass(frozen=True, slots=True)
class RateDailyMenuUseCase:
    daily_menu_repository: DailyMenuRepository
    daily_menu_rating_repository: DailyMenuRatingRepository

    async def execute(self, user_id: int, daily_menu_id: uuid.UUID, score: int) -> DailyMenuModel:
        if not 1 <= score <= 5:
            raise ValueError("Menu rating must be between 1 and 5")
        daily_menu = await self.daily_menu_repository.get_by_id(daily_menu_id)
        if daily_menu is None:
            raise ValueError("Daily menu is unavailable")
        await self.daily_menu_rating_repository.set_score(daily_menu_id, user_id, score)
        ratings = await self.daily_menu_rating_repository.get_all_by_daily_menu_id(daily_menu_id)
        return to_model(daily_menu, ratings, user_id)
