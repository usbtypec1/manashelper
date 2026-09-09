import uuid
from dataclasses import dataclass

from manashelper.repositories.faculty_repository import FacultyRepository


@dataclass(frozen=True, slots=True)
class FacultyModel:
    id: uuid.UUID
    name: str


class FacultyService:
    def __init__(self, faculty_repository: FacultyRepository) -> None:
        self._faculty_repository = faculty_repository

    async def get_all_faculties(self) -> list[FacultyModel]:
        faculties = await self._faculty_repository.get_all()
        return [FacultyModel(id=faculty.id, name=faculty.name) for faculty in faculties]
