from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import UserExamGrade


class UserExamGradeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_user_id(self, user_id: int) -> list[UserExamGrade]:
        result = await self._session.execute(select(UserExamGrade).where(UserExamGrade.user_id == user_id))
        return list(result.scalars().all())

    def add(self, grade: UserExamGrade) -> None:
        self._session.add(grade)
