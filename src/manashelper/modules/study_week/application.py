from dataclasses import dataclass
from datetime import date, datetime, timedelta

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.eders.application.eders import EdersService
from manashelper.modules.eders.application.models import EdersSnapshot
from manashelper.modules.schedule.application.schedule import (
    NoTrackedCoursesError,
    ScheduleLessonModel,
    ScheduleService,
)


@dataclass(frozen=True, slots=True)
class StudyWeek:
    start: date
    lessons: tuple[ScheduleLessonModel, ...]
    snapshot: EdersSnapshot
    has_tracked_courses: bool


class GetStudyWeek:
    def __init__(self, eders_service: EdersService, schedule_service: ScheduleService) -> None:
        self._eders = eders_service
        self._schedule = schedule_service

    async def execute(self, user_id: int) -> StudyWeek:
        snapshot = await self._eders.get_snapshot(user_id)
        has_courses = True
        try:
            lessons = await self._schedule.get_user_schedule(user_id)
        except NoTrackedCoursesError:
            lessons, has_courses = [], False
        return StudyWeek(datetime.now(BISHKEK_TZ).date(), tuple(lessons), snapshot, has_courses)


def week_end(week: StudyWeek) -> date:
    return week.start + timedelta(days=6)
