import uuid
from dataclasses import dataclass

from manashelper.modules.schedule.infrastructure.repositories.faculty import FacultyRepository


@dataclass(frozen=True, slots=True)
class FacultyModel:
    id: uuid.UUID
    name: str


@dataclass(frozen=True, slots=True)
class FacultyQuery:
    faculty_repository: FacultyRepository

    async def get_all_faculties(self) -> list[FacultyModel]:
        faculties = await self.faculty_repository.get_all()
        return [FacultyModel(id=faculty.id, name=faculty.name) for faculty in faculties]
