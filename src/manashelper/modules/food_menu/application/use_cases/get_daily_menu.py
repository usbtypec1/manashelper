from dataclasses import dataclass
from datetime import date

from manashelper.modules.food_menu.application.daily_menu import DailyMenuModel, DailyMenuNotFoundError, to_model
from manashelper.modules.food_menu.infrastructure.repositories.daily_menu import DailyMenuRepository
from manashelper.modules.food_menu.infrastructure.repositories.daily_menu_rating import (
    DailyMenuRatingRepository,
)
from manashelper.modules.gamification.application.use_cases.record_activity import RecordActivityUseCase


@dataclass(frozen=True, slots=True)
class GetDailyMenuUseCase:
    daily_menu_repository: DailyMenuRepository
    daily_menu_rating_repository: DailyMenuRatingRepository
    activity: RecordActivityUseCase

    async def execute(self, menu_date: date, *, user_id: int | None = None) -> DailyMenuModel:
        daily_menu = await self.daily_menu_repository.get_by_date(menu_date)
        if daily_menu is None:
            raise DailyMenuNotFoundError(menu_date)
        ratings = await self.daily_menu_rating_repository.get_all_by_daily_menu_id(daily_menu.id)
        daily_menu.views_count += 1
        if user_id is not None:
            await self.activity.execute(user_id, "food")
        return to_model(daily_menu, ratings, user_id)
