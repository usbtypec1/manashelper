import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import Course


class CourseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_department_id(self, department_id: uuid.UUID) -> Sequence[Course]:
        result = await self._session.execute(
            select(Course).where(Course.department_id == department_id).order_by(Course.number)
        )
        return result.scalars().all()

    async def get_by_id(self, course_id: int) -> Course | None:
        return await self._session.get(Course, course_id)
