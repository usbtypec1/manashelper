import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import DailyMenuRating


class DailyMenuRatingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_daily_menu_id(self, daily_menu_id: uuid.UUID) -> Sequence[DailyMenuRating]:
        result = await self._session.execute(
            select(DailyMenuRating)
            .where(DailyMenuRating.daily_menu_id == daily_menu_id)
            .execution_options(populate_existing=True)
        )
        return result.scalars().all()

    async def get_by_daily_menu_and_user(self, daily_menu_id: uuid.UUID, user_id: int) -> DailyMenuRating | None:
        result = await self._session.execute(
            select(DailyMenuRating).where(
                DailyMenuRating.daily_menu_id == daily_menu_id,
                DailyMenuRating.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def set_score(self, daily_menu_id: uuid.UUID, user_id: int, score: int) -> None:
        statement = insert(DailyMenuRating).values(
            id=uuid.uuid4(), daily_menu_id=daily_menu_id, user_id=user_id, score=score
        )
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[DailyMenuRating.daily_menu_id, DailyMenuRating.user_id],
                set_={"score": score},
            )
        )

    def add(self, rating: DailyMenuRating) -> None:
        self._session.add(rating)
