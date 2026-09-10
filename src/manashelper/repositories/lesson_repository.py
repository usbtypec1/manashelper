from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import Lesson


class LessonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_course_id(self, course_id: int) -> list[Lesson]:
        result = await self._session.execute(select(Lesson).where(Lesson.course_id == course_id))
        return list(result.scalars().all())

    async def get_all_by_course_ids(self, course_ids: Sequence[int]) -> list[Lesson]:
        result = await self._session.execute(select(Lesson).where(Lesson.course_id.in_(course_ids)))
        return list(result.scalars().all())

    def add(self, lesson: Lesson) -> None:
        self._session.add(lesson)

    async def delete(self, lesson: Lesson) -> None:
        await self._session.delete(lesson)
