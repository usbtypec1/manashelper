from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import Faculty


class FacultyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> Sequence[Faculty]:
        result = await self._session.execute(select(Faculty).order_by(Faculty.name))
        return result.scalars().all()
