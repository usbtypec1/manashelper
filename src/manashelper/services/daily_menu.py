import uuid
import zoneinfo
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from manashelper.db.models import DailyMenu, DailyMenuRating
from manashelper.repositories.daily_menu_rating_repository import DailyMenuRatingRepository
from manashelper.repositories.daily_menu_repository import DailyMenuRepository

BISHKEK_TZ = zoneinfo.ZoneInfo("Asia/Bishkek")
MENU_LOOKAHEAD_DAYS = 3


class DailyMenuNotFoundError(Exception):
    def __init__(self, menu_date: date) -> None:
        super().__init__(f"No daily menu for {menu_date}")
        self.date = menu_date


@dataclass(frozen=True, slots=True)
class DailyMenuAvailability:
    today: date
    dates: list[date]


@dataclass(frozen=True, slots=True)
class DishModel:
    id: uuid.UUID
    name: str
    photo_url: str
    calories: int


@dataclass(frozen=True, slots=True)
class DailyMenuModel:
    id: uuid.UUID
    date: date
    dishes: list[DishModel]
    average_rating: float
    ratings_count: int
    views_count: int
    user_rating: int | None = None


def _to_model(daily_menu: DailyMenu, ratings: Sequence[DailyMenuRating], user_id: int | None) -> DailyMenuModel:
    return DailyMenuModel(
        id=daily_menu.id,
        date=daily_menu.date,
        dishes=[
            DishModel(id=dish.id, name=dish.name, photo_url=dish.photo_url, calories=dish.calories)
            for dish in daily_menu.dishes
        ],
        average_rating=sum(rating.score for rating in ratings) / len(ratings) if ratings else 0.0,
        ratings_count=len(ratings),
        views_count=daily_menu.views_count,
        user_rating=next((rating.score for rating in ratings if rating.user_id == user_id), None),
    )


class DailyMenuService:
    def __init__(
        self,
        daily_menu_repository: DailyMenuRepository,
        daily_menu_rating_repository: DailyMenuRatingRepository,
    ) -> None:
        self._daily_menu_repository = daily_menu_repository
        self._daily_menu_rating_repository = daily_menu_rating_repository

    async def get_available_dates(self) -> DailyMenuAvailability:
        today = datetime.now(BISHKEK_TZ).date()
        dates = await self._daily_menu_repository.get_dates_between(
            today, today + timedelta(days=MENU_LOOKAHEAD_DAYS - 1)
        )
        return DailyMenuAvailability(today, dates)

    async def get_daily_menu_by_skipping_days(self, skip_days: int, user_id: int | None = None) -> DailyMenuModel:
        target_date = datetime.now(BISHKEK_TZ).date() + timedelta(days=skip_days)
        return await self.get_daily_menu_by_date(target_date, user_id=user_id)

    async def get_daily_menu_by_date(self, menu_date: date, *, user_id: int | None = None) -> DailyMenuModel:
        daily_menu = await self._daily_menu_repository.get_by_date(menu_date)
        if daily_menu is None:
            raise DailyMenuNotFoundError(menu_date)

        ratings = await self._daily_menu_rating_repository.get_all_by_daily_menu_id(daily_menu.id)
        daily_menu.views_count += 1
        return _to_model(daily_menu, ratings, user_id)

    async def set_rating(self, user_id: int, daily_menu_id: uuid.UUID, score: int) -> DailyMenuModel:
        if not 1 <= score <= 5:
            raise ValueError("Menu rating must be between 1 and 5")
        daily_menu = await self._daily_menu_repository.get_by_id(daily_menu_id)
        if daily_menu is None:
            raise ValueError("Daily menu is unavailable")
        await self._daily_menu_rating_repository.set_score(daily_menu_id, user_id, score)
        ratings = await self._daily_menu_rating_repository.get_all_by_daily_menu_id(daily_menu_id)
        return _to_model(daily_menu, ratings, user_id)
