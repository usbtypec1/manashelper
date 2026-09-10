import uuid
from dataclasses import dataclass

from manashelper.repositories.department_repository import DepartmentRepository


@dataclass(frozen=True, slots=True)
class DepartmentSummary:
    id: uuid.UUID
    name: str


class DepartmentService:
    def __init__(self, department_repository: DepartmentRepository) -> None:
        self._department_repository = department_repository

    async def get_departments_by_faculty(self, faculty_id: uuid.UUID) -> list[DepartmentSummary]:
        departments = await self._department_repository.get_all_by_faculty_id(faculty_id)
        return [DepartmentSummary(id=department.id, name=department.name) for department in departments]
