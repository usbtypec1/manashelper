import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import Department, Faculty
from manashelper.repositories.department_repository import DepartmentRepository
from manashelper.services.department import DepartmentService


async def test_get_departments_by_faculty_returns_only_that_faculty(session: AsyncSession) -> None:
    faculty = Faculty(id=uuid.uuid4(), name="Тестовый факультет")
    other_faculty = Faculty(id=uuid.uuid4(), name="Другой факультет")
    session.add_all([faculty, other_faculty])
    await session.flush()

    department = Department(id=uuid.uuid4(), name="Тестовое направление", faculty_id=faculty.id)
    other_department = Department(id=uuid.uuid4(), name="Другое направление", faculty_id=other_faculty.id)
    session.add_all([department, other_department])
    await session.flush()

    service = DepartmentService(DepartmentRepository(session))
    departments = await service.get_departments_by_faculty(faculty.id)

    assert [d.id for d in departments] == [department.id]
    assert departments[0].name == "Тестовое направление"
