import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from manashelper.modules.schedule.application.course_level import CourseLevel, parse_course_level
from manashelper.modules.schedule.infrastructure.models.course import Course
from manashelper.modules.schedule.infrastructure.repositories.course import CourseRepository
from manashelper.modules.schedule.infrastructure.repositories.course_tracking import CourseTrackingRepository


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
    level: CourseLevel = CourseLevel.BACHELOR


@dataclass(frozen=True, slots=True)
class TrackedCourseSummary:
    id: int
    number: int
    department_name: str
    faculty_name: str
    level: CourseLevel = CourseLevel.BACHELOR


def to_summaries(courses: Sequence[Course], tracked_course_ids: set[int]) -> list[CourseSummary]:
    return [
        CourseSummary(
            id=course.id,
            number=course.number,
            is_tracked=course.id in tracked_course_ids,
            level=parse_course_level(course.level),
        )
        for course in courses
    ]


@dataclass(frozen=True, slots=True)
class CourseQuery:
    course_repository: CourseRepository
    tracking_repository: CourseTrackingRepository

    async def get_tracked_courses(self, user_id: int) -> list[TrackedCourseSummary]:
        return [
            TrackedCourseSummary(
                course.id,
                course.number,
                course.department.name,
                course.department.faculty.name,
                parse_course_level(course.level),
            )
            for course in await self.tracking_repository.get_tracked_courses(user_id)
        ]

    async def get_courses_by_department(self, department_id: uuid.UUID, user_id: int) -> list[CourseSummary]:
        courses = await self.course_repository.get_all_by_department_id(department_id)
        tracked_course_ids = await self._get_tracked_course_ids(user_id)
        return to_summaries(courses, tracked_course_ids)

    async def _get_tracked_course_ids(self, user_id: int) -> set[int]:
        user = await self.tracking_repository.get_with_tracked_courses(user_id)
        if user is None:
            return set()
        return {tracked_course.id for tracked_course in user.tracked_courses}

    async def get_all_ids(self) -> Sequence[int]:
        return await self.course_repository.get_all_ids()
