import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.food_menu.infrastructure.models.daily_menu import DailyMenu
from manashelper.modules.food_menu.infrastructure.models.daily_menu_rating import DailyMenuRating
from manashelper.modules.food_menu.infrastructure.repositories.daily_menu import DailyMenuRepository

MENU_LOOKAHEAD_DAYS = 5


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


def to_model(daily_menu: DailyMenu, ratings: Sequence[DailyMenuRating], user_id: int | None) -> DailyMenuModel:
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


@dataclass(frozen=True, slots=True)
class DailyMenuQuery:
    daily_menu_repository: DailyMenuRepository

    async def get_available_dates(self) -> DailyMenuAvailability:
        today = datetime.now(BISHKEK_TZ).date()
        dates = await self.daily_menu_repository.get_dates_between(
            today, today + timedelta(days=MENU_LOOKAHEAD_DAYS - 1)
        )
        return DailyMenuAvailability(today, dates)
