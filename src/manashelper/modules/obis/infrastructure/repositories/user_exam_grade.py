import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.obis.application.models import ExamGradeRecord
from manashelper.modules.obis.infrastructure.models.user_exam_grade import UserExamGrade


class UserExamGradeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_user_id(self, user_id: int) -> list[ExamGradeRecord]:
        result = await self._session.execute(select(UserExamGrade).where(UserExamGrade.user_id == user_id))
        return [ExamGradeRecord(row.id, row.lesson_code, row.exam_name, row.score) for row in result.scalars()]

    async def save_all(self, user_id: int, records: list[ExamGradeRecord]) -> None:
        ids = [record.id for record in records if record.id is not None]
        existing = {}
        if ids:
            rows = await self._session.scalars(
                select(UserExamGrade).where(UserExamGrade.user_id == user_id, UserExamGrade.id.in_(ids))
            )
            existing = {row.id: row for row in rows}
        for record in records:
            if record.id is None:
                self._session.add(
                    UserExamGrade(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        lesson_code=record.lesson_code,
                        exam_name=record.exam_name,
                        score=record.score,
                    )
                )
            else:
                existing[record.id].score = record.score
