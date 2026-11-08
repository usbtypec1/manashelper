from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from manashelper.modules.schedule.infrastructure.models.associations import user_courses
from manashelper.modules.schedule.infrastructure.models.course import Course
from manashelper.modules.schedule.infrastructure.models.department import Department
from manashelper.modules.users.infrastructure.models.user import User


class CourseTrackingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_with_tracked_courses(self, user_id: int, *, lock: bool = False) -> User | None:
        statement = select(User).options(selectinload(User.tracked_courses)).where(User.id == user_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_tracked_courses(self, user_id: int) -> list[Course]:
        result = await self._session.scalars(
            select(Course)
            .join(user_courses, user_courses.c.course_id == Course.id)
            .where(user_courses.c.user_id == user_id)
            .options(selectinload(Course.department).selectinload(Department.faculty))
            .order_by(Course.department_id, Course.number)
        )
        return list(result.all())
