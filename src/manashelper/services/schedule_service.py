from dataclasses import dataclass

from manashelper.repositories.lesson_repository import LessonRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.course_service import UserNotFoundError


@dataclass(frozen=True, slots=True)
class ScheduleLessonModel:
    weekday: int
    time_range: str
    content: str


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
            return []

        lessons = await self._lesson_repository.get_all_by_course_ids(course_ids)
        return sorted(
            (
                ScheduleLessonModel(weekday=lesson.weekday, time_range=lesson.time_range, content=lesson.content)
                for lesson in lessons
            ),
            key=lambda lesson: (lesson.weekday, lesson.time_range),
        )
