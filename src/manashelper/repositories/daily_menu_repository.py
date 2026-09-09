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
