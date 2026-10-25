from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import UserLessonAttendance


class UserLessonAttendanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_user_id(self, user_id: int) -> list[UserLessonAttendance]:
        result = await self._session.execute(
            select(UserLessonAttendance).where(UserLessonAttendance.user_id == user_id)
        )
        return list(result.scalars().all())

    def add(self, attendance: UserLessonAttendance) -> None:
        self._session.add(attendance)
