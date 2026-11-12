from collections.abc import Sequence
from dataclasses import dataclass, field

from manashelper.modules.schedule.application.course_level import CourseLevel, parse_course_level
from manashelper.modules.schedule.application.text_normalization import fold_turkish
from manashelper.modules.schedule.application.time_ranges import (
    MAX_GAP_MINUTES_TO_GROUP,
    parse_time_range_end_minutes,
    parse_time_range_start_minutes,
)
from manashelper.modules.schedule.infrastructure.models.lesson import Lesson
from manashelper.modules.schedule.infrastructure.repositories.lesson import LessonRepository


@dataclass(frozen=True, slots=True)
class LessonSearchResult:
    course_id: int
    course_number: int
    faculty_name: str
    department_name: str
    weekday: int
    content: str
    time_ranges: list[str]
    course_level: CourseLevel = CourseLevel.BACHELOR


@dataclass(slots=True)
class _Block:
    course_id: int
    course_number: int
    faculty_name: str
    department_name: str
    weekday: int
    content: str
    end_minutes: int
    time_ranges: list[str] = field(default_factory=list)
    course_level: CourseLevel = CourseLevel.BACHELOR


def _group_lessons(lessons: Sequence[Lesson]) -> list[LessonSearchResult]:
    sorted_lessons = sorted(
        lessons,
        key=lambda lesson: (lesson.course_id, lesson.weekday, parse_time_range_start_minutes(lesson.time_range)),
    )

    blocks: list[_Block] = []
    for lesson in sorted_lessons:
        start = parse_time_range_start_minutes(lesson.time_range)
        end = parse_time_range_end_minutes(lesson.time_range)

        previous = blocks[-1] if blocks else None
        if (
            previous is not None
            and previous.course_id == lesson.course_id
            and previous.weekday == lesson.weekday
            and previous.content == lesson.content
            and start - previous.end_minutes <= MAX_GAP_MINUTES_TO_GROUP
        ):
            previous.end_minutes = end
            previous.time_ranges.append(lesson.time_range)
        else:
            blocks.append(
                _Block(
                    course_id=lesson.course_id,
                    course_number=lesson.course.number,
                    faculty_name=lesson.course.department.faculty.name,
                    department_name=lesson.course.department.name,
                    weekday=lesson.weekday,
                    content=lesson.content,
                    end_minutes=end,
                    time_ranges=[lesson.time_range],
                    course_level=parse_course_level(lesson.course.level),
                )
            )

    return [
        LessonSearchResult(
            course_id=block.course_id,
            course_number=block.course_number,
            faculty_name=block.faculty_name,
            department_name=block.department_name,
            weekday=block.weekday,
            content=block.content,
            time_ranges=block.time_ranges,
            course_level=block.course_level,
        )
        for block in blocks
    ]


@dataclass(frozen=True, slots=True)
class LessonSearchQuery:
    lesson_repository: LessonRepository

    async def search(self, query: str) -> list[LessonSearchResult]:
        normalized_query = fold_turkish(query)
        lessons = await self.lesson_repository.search_by_normalized_content(normalized_query)
        return _group_lessons(lessons)
