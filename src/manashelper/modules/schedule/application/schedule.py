from dataclasses import dataclass
from datetime import datetime

from manashelper.modules.schedule.application.course import UserNotFoundError
from manashelper.modules.schedule.application.time_ranges import parse_time_range_start_minutes
from manashelper.modules.schedule.application.timetable_entries import (
    NowNext,
    TimetableEntry,
    find_now_next,
    lesson_entries,
)
from manashelper.modules.schedule.infrastructure.repositories.course_tracking import CourseTrackingRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson import LessonRepository


class NoTrackedCoursesError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} has no tracked courses")
        self.user_id = user_id


@dataclass(frozen=True, slots=True)
class ScheduleLessonModel:
    weekday: int
    time_range: str
    content: str


@dataclass(frozen=True, slots=True)
class ScheduleQuery:
    lesson_repository: LessonRepository
    tracking_repository: CourseTrackingRepository

    async def get_user_schedule(self, user_id: int) -> list[ScheduleLessonModel]:
        course_ids = await self.get_tracked_course_ids(user_id)
        lessons = await self.lesson_repository.get_all_by_course_ids(course_ids)
        return sorted(
            (
                ScheduleLessonModel(weekday=lesson.weekday, time_range=lesson.time_range, content=lesson.content)
                for lesson in lessons
            ),
            key=lambda lesson: (lesson.weekday, parse_time_range_start_minutes(lesson.time_range)),
        )

    async def get_user_entries(self, user_id: int) -> list[TimetableEntry]:
        """Real lessons of the user's tracked courses; reserved placeholders are omitted."""
        course_ids = await self.get_tracked_course_ids(user_id)
        lessons = await self.lesson_repository.get_all_with_courses_by_course_ids(course_ids)
        return [entry for lesson in lessons for entry in lesson_entries(lesson)]

    async def get_now_next(self, user_id: int, now: datetime) -> NowNext:
        return find_now_next(await self.get_user_entries(user_id), now)

    async def get_tracked_course_ids(self, user_id: int) -> list[int]:
        user = await self.tracking_repository.get_with_tracked_courses(user_id)
        if user is None:
            raise UserNotFoundError(user_id)

        course_ids = [course.id for course in user.tracked_courses]
        if not course_ids:
            raise NoTrackedCoursesError(user_id)
        return course_ids
