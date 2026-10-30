from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.obis.infrastructure.snapshot import ObisSnapshot
from manashelper.modules.obis.infrastructure.user_exam_grade import UserExamGrade
from manashelper.modules.obis.infrastructure.user_lesson_attendance import UserLessonAttendance
from manashelper.modules.users.infrastructure.user import User


class ObisSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int, kind: str) -> ObisSnapshot | None:
        return await self._session.get(ObisSnapshot, (user_id, kind), populate_existing=True)

    async def save(self, snapshot: ObisSnapshot) -> None:
        await self._session.merge(snapshot)

    async def reset(self, user_id: int) -> None:
        # A new account must also start notification comparisons from a silent baseline.
        for model in (ObisSnapshot, UserExamGrade, UserLessonAttendance):
            await self._session.execute(delete(model).where(model.user_id == user_id))

    async def get_poll_user_ids(self) -> list[int]:
        query = select(User.id).where(User.student_number.is_not(None), User.encrypted_password.is_not(None))
        return list((await self._session.scalars(query)).all())
