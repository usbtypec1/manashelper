from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from manashelper.modules.notifications.orm import NotificationSettings
from manashelper.modules.schedule.infrastructure.models.associations import user_courses
from manashelper.modules.users.infrastructure.models.user import User


class NotificationSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, user_id: int) -> NotificationSettings:
        settings = await self._session.get(NotificationSettings, user_id)
        if settings is None:
            settings = NotificationSettings(
                user_id=user_id,
                schedule_changes_enabled=True,
                exam_grades_enabled=True,
                lesson_skips_enabled=True,
            )
            self._session.add(settings)
        return settings

    async def get_broadcast_recipient_ids(self, now: datetime) -> list[int]:
        result = await self._session.scalars(
            select(User.id)
            .outerjoin(NotificationSettings, NotificationSettings.user_id == User.id)
            .where(User.bot_stopped.is_(False))
            .where(
                or_(
                    NotificationSettings.broadcast_muted_until.is_(None),
                    NotificationSettings.broadcast_muted_until <= now,
                )
            )
        )
        return list(result.all())

    async def get_user_ids_with_exam_grades_enabled(self) -> list[int]:
        return await self._get_user_ids_with_enabled(NotificationSettings.exam_grades_enabled)

    async def allows_queued_delivery(self, user_id: int, category: str, now: datetime) -> bool:
        statement = (
            select(User.id)
            .outerjoin(NotificationSettings, NotificationSettings.user_id == User.id)
            .where(User.id == user_id, User.bot_stopped.is_(False))
        )
        if category == "broadcast":
            statement = statement.where(
                or_(
                    NotificationSettings.broadcast_muted_until.is_(None),
                    NotificationSettings.broadcast_muted_until <= now,
                )
            )
        else:
            flag = {
                "exam_grades": NotificationSettings.exam_grades_enabled,
                "lesson_skips": NotificationSettings.lesson_skips_enabled,
                "schedule": NotificationSettings.schedule_changes_enabled,
            }.get(category)
            if flag is not None:
                statement = statement.where(flag.is_distinct_from(False))
        return (await self._session.scalar(statement)) is not None

    async def get_user_ids_with_lesson_skips_enabled(self) -> list[int]:
        return await self._get_user_ids_with_enabled(NotificationSettings.lesson_skips_enabled)

    async def get_user_ids_tracking_course_with_schedule_changes_enabled(self, course_id: int) -> list[int]:
        result = await self._session.execute(
            select(user_courses.c.user_id)
            .select_from(user_courses)
            .join(User, User.id == user_courses.c.user_id)
            .outerjoin(NotificationSettings, NotificationSettings.user_id == user_courses.c.user_id)
            .where(user_courses.c.course_id == course_id)
            .where(User.bot_stopped.is_(False))
            .where(NotificationSettings.schedule_changes_enabled.is_distinct_from(False))
        )
        return list(result.scalars().all())

    async def _get_user_ids_with_enabled(self, column: InstrumentedAttribute[bool]) -> list[int]:
        result = await self._session.execute(
            select(User.id)
            .outerjoin(NotificationSettings, NotificationSettings.user_id == User.id)
            .where(column.is_distinct_from(False))
            .where(User.bot_stopped.is_(False))
        )
        return list(result.scalars().all())
