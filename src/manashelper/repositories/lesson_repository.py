from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from manashelper.db.models import Course, Department, Lesson


def _escape_like_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class LessonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_course_id(self, course_id: int) -> list[Lesson]:
        result = await self._session.execute(select(Lesson).where(Lesson.course_id == course_id))
        return list(result.scalars().all())

    async def get_all_by_course_ids(self, course_ids: Sequence[int]) -> list[Lesson]:
        result = await self._session.execute(select(Lesson).where(Lesson.course_id.in_(course_ids)))
        return list(result.scalars().all())

    async def search_by_normalized_content(self, normalized_query: str) -> Sequence[Lesson]:
        pattern = f"%{_escape_like_pattern(normalized_query)}%"
        result = await self._session.execute(
            select(Lesson)
            .options(joinedload(Lesson.course).joinedload(Course.department).joinedload(Department.faculty))
            .where(Lesson.normalized_content.like(pattern, escape="\\"))
            .order_by(Lesson.course_id, Lesson.weekday, Lesson.time_range)
        )
        return result.unique().scalars().all()

    def add(self, lesson: Lesson) -> None:
        self._session.add(lesson)

    async def delete(self, lesson: Lesson) -> None:
        await self._session.delete(lesson)
