import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.schedule.application.faculty import FacultyService
from manashelper.modules.schedule.infrastructure.models.faculty import Faculty
from manashelper.modules.schedule.infrastructure.repositories.faculty_repository import FacultyRepository


async def test_get_all_faculties_returns_faculties_sorted_by_name(session: AsyncSession) -> None:
    session.add_all(
        [
            Faculty(id=uuid.uuid4(), name="Тестовый факультет Б"),
            Faculty(id=uuid.uuid4(), name="Тестовый факультет А"),
        ]
    )
    await session.flush()

    service = FacultyService(FacultyRepository(session))
    faculties = await service.get_all_faculties()

    names = [faculty.name for faculty in faculties]
    assert names == sorted(names)
    assert {"Тестовый факультет А", "Тестовый факультет Б"} <= set(names)
