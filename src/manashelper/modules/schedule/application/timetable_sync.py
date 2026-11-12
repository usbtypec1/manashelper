from dataclasses import dataclass

from manashelper.modules.schedule.application.lesson_items import LessonItemModel, format_items
from manashelper.modules.schedule.infrastructure.timetable_parser import ScrapedTimeSlot


@dataclass(frozen=True, slots=True)
class LessonChange:
    weekday: int
    time_range: str
    previous_content: str | None
    new_content: str | None


def slot_items(slot: ScrapedTimeSlot) -> list[LessonItemModel]:
    return [
        LessonItemModel(code=lesson.lesson_code, name=lesson.lesson_name, teacher=lesson.teacher, room=lesson.room)
        for lesson in slot.lessons
    ]


def format_slot_content(slot: ScrapedTimeSlot) -> str:
    return format_items(slot_items(slot))
