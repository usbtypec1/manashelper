import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from manashelper.db.models import Course
from manashelper.repositories.course_repository import CourseRepository
from manashelper.repositories.user_repository import UserRepository


class CourseNotFoundError(Exception):
    def __init__(self, course_id: int) -> None:
        super().__init__(f"Course {course_id} not found")
        self.course_id = course_id


class UserNotFoundError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} not found")
        self.user_id = user_id


@dataclass(frozen=True, slots=True)
class CourseSummary:
    id: int
    number: int
    is_tracked: bool


class CourseService:
    def __init__(self, course_repository: CourseRepository, user_repository: UserRepository) -> None:
        self._course_repository = course_repository
        self._user_repository = user_repository

    async def get_courses_by_department(self, department_id: uuid.UUID, user_id: int) -> list[CourseSummary]:
        courses = await self._course_repository.get_all_by_department_id(department_id)
        tracked_course_ids = await self._get_tracked_course_ids(user_id)
        return self._to_summaries(courses, tracked_course_ids)

    async def toggle_tracked_course(self, course_id: int, user_id: int) -> list[CourseSummary]:
        course = await self._course_repository.get_by_id(course_id)
        if course is None:
            raise CourseNotFoundError(course_id)

        user = await self._user_repository.get_with_tracked_courses(user_id)
        if user is None:
            raise UserNotFoundError(user_id)

        tracked_course_ids = {tracked_course.id for tracked_course in user.tracked_courses}
        if course_id in tracked_course_ids:
            user.tracked_courses = [
                tracked_course for tracked_course in user.tracked_courses if tracked_course.id != course_id
            ]
        else:
            user.tracked_courses.append(course)

        sibling_courses = await self._course_repository.get_all_by_department_id(course.department_id)
        updated_tracked_ids = {tracked_course.id for tracked_course in user.tracked_courses}
        return self._to_summaries(sibling_courses, updated_tracked_ids)

    async def _get_tracked_course_ids(self, user_id: int) -> set[int]:
        user = await self._user_repository.get_with_tracked_courses(user_id)
        if user is None:
            return set()
        return {tracked_course.id for tracked_course in user.tracked_courses}

    @staticmethod
    def _to_summaries(courses: Sequence[Course], tracked_course_ids: set[int]) -> list[CourseSummary]:
        return [
            CourseSummary(id=course.id, number=course.number, is_tracked=course.id in tracked_course_ids)
            for course in courses
        ]
