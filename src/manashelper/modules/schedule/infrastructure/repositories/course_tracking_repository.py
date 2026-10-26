from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from manashelper.modules.users.infrastructure.user import User


class CourseTrackingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_with_tracked_courses(self, user_id: int) -> User | None:
        result = await self._session.execute(
            select(User).options(selectinload(User.tracked_courses)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
