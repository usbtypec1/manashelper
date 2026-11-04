import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.obis.application.models import AttendanceBaseline
from manashelper.modules.obis.infrastructure.models.user_lesson_attendance import UserLessonAttendance


class UserLessonAttendanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_user_id(self, user_id: int) -> list[AttendanceBaseline]:
        result = await self._session.execute(
            select(UserLessonAttendance).where(UserLessonAttendance.user_id == user_id)
        )
        return [
            AttendanceBaseline(row.id, row.lesson_code, row.theory_skips_percentage, row.practice_skips_percentage)
            for row in result.scalars()
        ]

    async def save_all(self, user_id: int, records: list[AttendanceBaseline]) -> None:
        ids = [record.id for record in records if record.id is not None]
        existing = {}
        if ids:
            rows = await self._session.scalars(
                select(UserLessonAttendance).where(
                    UserLessonAttendance.user_id == user_id, UserLessonAttendance.id.in_(ids)
                )
            )
            existing = {row.id: row for row in rows}
        for record in records:
            if record.id is None:
                self._session.add(
                    UserLessonAttendance(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        lesson_code=record.lesson_code,
                        theory_skips_percentage=record.theory_skips_percentage,
                        practice_skips_percentage=record.practice_skips_percentage,
                    )
                )
            else:
                row = existing[record.id]
                row.theory_skips_percentage = record.theory_skips_percentage
                row.practice_skips_percentage = record.practice_skips_percentage
