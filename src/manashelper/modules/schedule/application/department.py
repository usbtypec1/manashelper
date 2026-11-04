import uuid
from dataclasses import dataclass

from manashelper.modules.schedule.infrastructure.repositories.department import DepartmentRepository


@dataclass(frozen=True, slots=True)
class DepartmentSummary:
    id: uuid.UUID
    name: str


@dataclass(frozen=True, slots=True)
class DepartmentQuery:
    department_repository: DepartmentRepository

    async def get_departments_by_faculty(self, faculty_id: uuid.UUID) -> list[DepartmentSummary]:
        departments = await self.department_repository.get_all_by_faculty_id(faculty_id)
        return [DepartmentSummary(id=department.id, name=department.name) for department in departments]
