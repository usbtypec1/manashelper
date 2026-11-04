from dataclasses import dataclass

from manashelper.modules.schedule.infrastructure.timetable_parser import (
    ScrapedLessonSlot,
    ScrapedTimeSlot,
)


@dataclass(frozen=True, slots=True)
class LessonChange:
    weekday: int
    time_range: str
    previous_content: str | None
    new_content: str | None


def format_slot_content(slot: ScrapedTimeSlot) -> str:
    return " | ".join(_format_lesson(lesson) for lesson in slot.lessons)


def _format_lesson(lesson: ScrapedLessonSlot) -> str:
    code_prefix = f"{lesson.lesson_code} " if lesson.lesson_code else ""
    return f"{code_prefix}{lesson.lesson_name} — {lesson.teacher}, {lesson.room}"
