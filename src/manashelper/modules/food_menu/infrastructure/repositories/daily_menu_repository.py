import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from manashelper.db.models import DailyMenu


class DailyMenuRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_date(self, menu_date: date) -> DailyMenu | None:
        result = await self._session.execute(
            select(DailyMenu).options(selectinload(DailyMenu.dishes)).where(DailyMenu.date == menu_date)
        )
        return result.scalar_one_or_none()

    def add(self, daily_menu: DailyMenu) -> None:
        self._session.add(daily_menu)

    async def get_dates_between(self, start_date: date, end_date: date) -> list[date]:
        result = await self._session.scalars(
            select(DailyMenu.date).where(DailyMenu.date.between(start_date, end_date)).order_by(DailyMenu.date)
        )
        return list(result.all())

    async def get_by_id(self, daily_menu_id: uuid.UUID) -> DailyMenu | None:
        result = await self._session.execute(
            select(DailyMenu).options(selectinload(DailyMenu.dishes)).where(DailyMenu.id == daily_menu_id)
        )
        return result.scalar_one_or_none()
