from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import Dish


class DishRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_name(self, name: str) -> Dish | None:
        result = await self._session.execute(select(Dish).where(Dish.name == name))
        return result.scalar_one_or_none()

    def add(self, dish: Dish) -> None:
        self._session.add(dish)
