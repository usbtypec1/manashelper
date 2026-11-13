"""Common free periods of several courses, e.g. a student and friends from other departments."""

from collections.abc import Sequence
from dataclasses import dataclass

from manashelper.modules.schedule.application.campus import sort_periods
from manashelper.modules.schedule.application.course import CourseNotFoundError
from manashelper.modules.schedule.application.course_level import CourseLevel, parse_course_level
from manashelper.modules.schedule.application.time_ranges import (
    parse_time_range_end_minutes,
    parse_time_range_start_minutes,
)
from manashelper.modules.schedule.application.timetable_entries import WORKDAYS
from manashelper.modules.schedule.infrastructure.repositories.course import CourseRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson import LessonRepository

MAX_FREE_TIME_COURSES = 8


class TooManyCoursesError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class FreeWindow:
    start_minutes: int
    end_minutes: int
    periods: int


@dataclass(frozen=True, slots=True)
class FreeDay:
    weekday: int
    windows: tuple[FreeWindow, ...]


@dataclass(frozen=True, slots=True)
class FreeTimeCourse:
    id: int
    number: int
    level: CourseLevel
    department_name: str
    faculty_name: str


@dataclass(frozen=True, slots=True)
class FreeTime:
    courses: tuple[FreeTimeCourse, ...]
    days: tuple[FreeDay, ...]


def free_windows(periods: Sequence[str], busy: set[str]) -> tuple[FreeWindow, ...]:
    """Maximal runs of consecutive free periods; a run may span a break such as lunch."""
    windows: list[FreeWindow] = []
    run: list[str] = []
    for time_range in [*periods, None]:
        if time_range is not None and time_range not in busy:
            run.append(time_range)
            continue
        if run:
            windows.append(
                FreeWindow(
                    start_minutes=parse_time_range_start_minutes(run[0]),
                    end_minutes=parse_time_range_end_minutes(run[-1]),
                    periods=len(run),
                )
            )
            run = []
    return tuple(windows)


@dataclass(frozen=True, slots=True)
class FreeTimeQuery:
    course_repository: CourseRepository
    lesson_repository: LessonRepository

    async def execute(self, course_ids: Sequence[int]) -> FreeTime:
        unique_ids = list(dict.fromkeys(course_ids))
        if len(unique_ids) > MAX_FREE_TIME_COURSES:
            raise TooManyCoursesError
        courses = {course.id: course for course in await self.course_repository.get_with_departments(unique_ids)}
        missing = next((course_id for course_id in unique_ids if course_id not in courses), None)
        if missing is not None:
            raise CourseNotFoundError(missing)

        periods = sort_periods(await self.lesson_repository.get_time_ranges())
        busy: dict[int, set[str]] = {weekday: set() for weekday in WORKDAYS}
        if unique_ids:
            for lesson in await self.lesson_repository.get_all_by_course_ids(unique_ids):
                busy.setdefault(lesson.weekday, set()).add(lesson.time_range)

        return FreeTime(
            courses=tuple(
                FreeTimeCourse(
                    id=course.id,
                    number=course.number,
                    level=parse_course_level(course.level),
                    department_name=course.department.name,
                    faculty_name=course.department.faculty.name,
                )
                for course in (courses[course_id] for course_id in unique_ids)
            ),
            days=tuple(FreeDay(weekday=day, windows=free_windows(periods, busy[day])) for day in WORKDAYS),
        )
