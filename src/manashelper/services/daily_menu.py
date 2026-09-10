import uuid
import zoneinfo
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from manashelper.db.models import DailyMenu, DailyMenuRating
from manashelper.repositories.daily_menu_rating_repository import DailyMenuRatingRepository
from manashelper.repositories.daily_menu_repository import DailyMenuRepository

BISHKEK_TZ = zoneinfo.ZoneInfo("Asia/Bishkek")


class DailyMenuNotFoundError(Exception):
    def __init__(self, menu_date: date) -> None:
        super().__init__(f"No daily menu for {menu_date}")
        self.date = menu_date


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


def _to_model(daily_menu: DailyMenu, average_rating: float, ratings_count: int) -> DailyMenuModel:
    return DailyMenuModel(
        id=daily_menu.id,
        date=daily_menu.date,
        dishes=[
            DishModel(id=dish.id, name=dish.name, photo_url=dish.photo_url, calories=dish.calories)
            for dish in daily_menu.dishes
        ],
        average_rating=average_rating,
        ratings_count=ratings_count,
        views_count=daily_menu.views_count,
    )


class DailyMenuService:
    def __init__(
        self,
        daily_menu_repository: DailyMenuRepository,
        daily_menu_rating_repository: DailyMenuRatingRepository,
    ) -> None:
        self._daily_menu_repository = daily_menu_repository
        self._daily_menu_rating_repository = daily_menu_rating_repository

    async def get_daily_menu_by_skipping_days(self, skip_days: int) -> DailyMenuModel:
        target_date = datetime.now(BISHKEK_TZ).date() + timedelta(days=skip_days)
        return await self.get_daily_menu_by_date(target_date)

    async def get_daily_menu_by_date(self, menu_date: date) -> DailyMenuModel:
        daily_menu = await self._daily_menu_repository.get_by_date(menu_date)
        if daily_menu is None:
            raise DailyMenuNotFoundError(menu_date)

        ratings = await self._daily_menu_rating_repository.get_all_by_daily_menu_id(daily_menu.id)
        average_rating = sum(rating.score for rating in ratings) / len(ratings) if ratings else 0.0

        daily_menu.views_count += 1

        return _to_model(daily_menu, average_rating, len(ratings))

    async def set_rating(self, user_id: int, daily_menu_id: uuid.UUID, score: int) -> None:
        rating = await self._daily_menu_rating_repository.get_by_daily_menu_and_user(daily_menu_id, user_id)
        if rating is None:
            self._daily_menu_rating_repository.add(
                DailyMenuRating(id=uuid.uuid4(), daily_menu_id=daily_menu_id, user_id=user_id, score=score)
            )
        else:
            rating.score = score
