from dataclasses import dataclass
from datetime import datetime

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.eders.application.eders import EdersQuery
from manashelper.modules.schedule.application.schedule import (
    NoTrackedCoursesError,
    ScheduleQuery,
)
from manashelper.modules.study_week.application import StudyWeek


@dataclass(frozen=True, slots=True)
class GetStudyWeekUseCase:
    eders_query: EdersQuery
    schedule_query: ScheduleQuery

    async def execute(self, user_id: int) -> StudyWeek:
        snapshot = await self.eders_query.get_snapshot(user_id)
        has_courses = True
        try:
            lessons = await self.schedule_query.get_user_schedule(user_id)
        except NoTrackedCoursesError:
            lessons, has_courses = [], False
        return StudyWeek(datetime.now(BISHKEK_TZ).date(), tuple(lessons), snapshot, has_courses)
