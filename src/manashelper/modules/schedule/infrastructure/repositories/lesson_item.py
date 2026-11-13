from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from manashelper.modules.schedule.infrastructure.models.course import Course
from manashelper.modules.schedule.infrastructure.models.department import Department
from manashelper.modules.schedule.infrastructure.models.lesson import Lesson
from manashelper.modules.schedule.infrastructure.models.lesson_item import LessonItem
from manashelper.modules.schedule.infrastructure.repositories.lesson import escape_like_pattern

type ItemRow = tuple[LessonItem, int, str, int, str, str]
"""Item, weekday, time range, course number, course level and department name."""


class LessonItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_room_names(self) -> Sequence[tuple[str, str]]:
        """Distinct (room_key, printed name) pairs of every room used by a lesson."""
        result = await self._session.execute(
            select(LessonItem.room_key, func.min(LessonItem.room))
            .where(LessonItem.room_key != "")
            .group_by(LessonItem.room_key)
        )
        return result.tuples().all()

    async def get_room_occupancy(self, weekday: int) -> Sequence[tuple[str, str]]:
        """(room_key, time_range) pairs occupied on one weekday."""
        result = await self._session.execute(
            select(LessonItem.room_key, Lesson.time_range)
            .join(Lesson, Lesson.id == LessonItem.lesson_id)
            .where(Lesson.weekday == weekday, LessonItem.room_key != "")
            .distinct()
        )
        return result.tuples().all()

    async def search_teachers(self, normalized_query: str, limit: int) -> Sequence[tuple[str, str]]:
        return await self._search(LessonItem.teacher_key, LessonItem.teacher, normalized_query, limit)

    async def search_rooms(self, room_key_query: str, limit: int) -> Sequence[tuple[str, str]]:
        return await self._search(LessonItem.room_key, LessonItem.room, room_key_query, limit)

    async def get_by_teacher_key(self, key: str) -> Sequence[ItemRow]:
        return await self._entries(LessonItem.teacher_key == key)

    async def get_by_room_key(self, key: str) -> Sequence[ItemRow]:
        return await self._entries(LessonItem.room_key == key)

    async def _search(
        self, key_column: InstrumentedAttribute[str], name_column: InstrumentedAttribute[str], query: str, limit: int
    ) -> Sequence[tuple[str, str]]:
        pattern = f"%{escape_like_pattern(query)}%"
        result = await self._session.execute(
            select(key_column, func.min(name_column))
            .where(key_column.like(pattern, escape="\\"), key_column != "")
            .group_by(key_column)
            .order_by(func.length(key_column), key_column)
            .limit(limit)
        )
        return result.tuples().all()

    async def _entries(self, condition: ColumnElement[bool]) -> Sequence[ItemRow]:
        result = await self._session.execute(
            select(LessonItem, Lesson.weekday, Lesson.time_range, Course.number, Course.level, Department.name)
            .join(Lesson, Lesson.id == LessonItem.lesson_id)
            .join(Course, Course.id == Lesson.course_id)
            .join(Department, Department.id == Course.department_id)
            .where(condition)
            .order_by(Lesson.weekday, Lesson.time_range, LessonItem.position)
        )
        return result.tuples().all()
