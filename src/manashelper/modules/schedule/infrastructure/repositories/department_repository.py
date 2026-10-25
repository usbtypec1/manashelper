import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import Department


class DepartmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_faculty_id(self, faculty_id: uuid.UUID) -> Sequence[Department]:
        result = await self._session.execute(
            select(Department).where(Department.faculty_id == faculty_id).order_by(Department.name)
        )
        return result.scalars().all()
