from dataclasses import dataclass

from manashelper.repositories.lesson_repository import LessonRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.course import UserNotFoundError


class NoTrackedCoursesError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} has no tracked courses")
        self.user_id = user_id


@dataclass(frozen=True, slots=True)
class ScheduleLessonModel:
    weekday: int
    time_range: str
    content: str


def parse_time_range_start_minutes(time_range: str) -> int:
    """Minutes since midnight for a "H:MM-H:MM" range's start — sorts "10:45" correctly after "9:50"."""
    hours, minutes = time_range.split("-", 1)[0].split(":")
    return int(hours) * 60 + int(minutes)


def parse_time_range_end_minutes(time_range: str) -> int:
    hours, minutes = time_range.split("-", 1)[1].split(":")
    return int(hours) * 60 + int(minutes)


# Regular breaks between periods run ~10 minutes; anything longer (a free period, lunch) starts a new block.
MAX_GAP_MINUTES_TO_GROUP = 20


class ScheduleService:
    def __init__(self, lesson_repository: LessonRepository, user_repository: UserRepository) -> None:
        self._lesson_repository = lesson_repository
        self._user_repository = user_repository

    async def get_user_schedule(self, user_id: int) -> list[ScheduleLessonModel]:
        user = await self._user_repository.get_with_tracked_courses(user_id)
        if user is None:
            raise UserNotFoundError(user_id)

        course_ids = [course.id for course in user.tracked_courses]
        if not course_ids:
            raise NoTrackedCoursesError(user_id)

        lessons = await self._lesson_repository.get_all_by_course_ids(course_ids)
        return sorted(
            (
                ScheduleLessonModel(weekday=lesson.weekday, time_range=lesson.time_range, content=lesson.content)
                for lesson in lessons
            ),
            key=lambda lesson: (lesson.weekday, parse_time_range_start_minutes(lesson.time_range)),
        )
