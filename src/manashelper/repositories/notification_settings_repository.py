from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from manashelper.db.models import NotificationSettings, User, user_courses


class NotificationSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, user_id: int) -> NotificationSettings:
        settings = await self._session.get(NotificationSettings, user_id)
        if settings is None:
            settings = NotificationSettings(user_id=user_id)
            self._session.add(settings)
        return settings

    async def get_user_ids_with_exam_grades_enabled(self) -> list[int]:
        return await self._get_user_ids_with_enabled(NotificationSettings.exam_grades_enabled)

    async def get_user_ids_with_lesson_skips_enabled(self) -> list[int]:
        return await self._get_user_ids_with_enabled(NotificationSettings.lesson_skips_enabled)

    async def get_user_ids_tracking_course_with_schedule_changes_enabled(self, course_id: int) -> list[int]:
        result = await self._session.execute(
            select(user_courses.c.user_id)
            .select_from(user_courses)
            .outerjoin(NotificationSettings, NotificationSettings.user_id == user_courses.c.user_id)
            .where(user_courses.c.course_id == course_id)
            .where(NotificationSettings.schedule_changes_enabled.is_distinct_from(False))
        )
        return list(result.scalars().all())

    async def _get_user_ids_with_enabled(self, column: InstrumentedAttribute[bool]) -> list[int]:
        result = await self._session.execute(
            select(User.id)
            .outerjoin(NotificationSettings, NotificationSettings.user_id == User.id)
            .where(column.is_distinct_from(False))
        )
        return list(result.scalars().all())
