from dataclasses import dataclass
from datetime import date, timedelta

from manashelper.modules.eders.application.models import EdersSnapshot
from manashelper.modules.schedule.application.schedule import (
    ScheduleLessonModel,
)


@dataclass(frozen=True, slots=True)
class StudyWeek:
    start: date
    lessons: tuple[ScheduleLessonModel, ...]
    snapshot: EdersSnapshot
    has_tracked_courses: bool


def week_end(week: StudyWeek) -> date:
    return week.start + timedelta(days=6)
