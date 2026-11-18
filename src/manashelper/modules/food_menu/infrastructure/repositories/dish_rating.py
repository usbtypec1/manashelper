import uuid
from collections.abc import Sequence

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from manashelper.modules.food_menu.infrastructure.models.dish import Dish
from manashelper.modules.food_menu.infrastructure.models.dish_rating import DishRating
from manashelper.modules.users.infrastructure.models.user import User


class DishRatingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_stats(self, dish_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[float, int]]:
        result = await self._session.execute(
            select(DishRating.dish_id, func.avg(DishRating.score), func.count())
            .where(DishRating.dish_id.in_(dish_ids))
            .group_by(DishRating.dish_id)
        )
        return {dish_id: (float(average), count) for dish_id, average, count in result}

    async def next_unrated(self, user_id: int) -> Dish | None:
        own_rating = aliased(DishRating)
        already_rated = (
            select(own_rating.dish_id).where(own_rating.dish_id == Dish.id, own_rating.user_id == user_id).exists()
        )
        result = await self._session.scalars(
            select(Dish)
            .outerjoin(DishRating, DishRating.dish_id == Dish.id)
            .where(~already_rated)
            .group_by(Dish.id)
            .order_by(func.count(DishRating.dish_id), Dish.id)
            .limit(1)
        )
        return result.one_or_none()

    async def add_score(self, dish_id: uuid.UUID, user_id: int, score: int) -> bool:
        # Serialize writes for one user so the completion check sees their previous ratings.
        if await self._session.scalar(select(User.id).where(User.id == user_id).with_for_update()) is None:
            raise ValueError("User is unavailable")
        saved = await self._session.scalar(
            insert(DishRating)
            .from_select(
                ["dish_id", "user_id", "score"],
                select(Dish.id, literal(user_id), literal(score)).where(Dish.id == dish_id),
            )
            .on_conflict_do_nothing(index_elements=[DishRating.dish_id, DishRating.user_id])
            .returning(DishRating.dish_id)
        )
        return saved is not None
