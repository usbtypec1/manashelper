import uuid
from dataclasses import dataclass

from manashelper.db.models import Lesson
from manashelper.repositories.lesson_repository import LessonRepository
from manashelper.scraping.timetable_client import TimetableClient
from manashelper.scraping.timetable_parser import ScrapedLessonSlot, ScrapedTimeSlot, parse_timetable_page


@dataclass(frozen=True, slots=True)
class LessonChange:
    weekday: int
    time_range: str
    previous_content: str | None
    new_content: str | None


class TimetableSyncService:
    def __init__(self, timetable_client: TimetableClient, lesson_repository: LessonRepository) -> None:
        self._timetable_client = timetable_client
        self._lesson_repository = lesson_repository

    async def synchronize_course_timetable(self, course_id: int) -> list[LessonChange]:
        html = await self._timetable_client.fetch_timetable_html(course_id)
        scraped_slots = parse_timetable_page(html)
        scraped_by_key = {(slot.weekday, slot.time_range): _format_slot_content(slot) for slot in scraped_slots}

        existing_lessons = await self._lesson_repository.get_all_by_course_id(course_id)
        existing_by_key = {(lesson.weekday, lesson.time_range): lesson for lesson in existing_lessons}
        is_first_sync = not existing_lessons

        changes: list[LessonChange] = []
        for (weekday, time_range), content in scraped_by_key.items():
            existing = existing_by_key.get((weekday, time_range))
            if existing is None:
                self._lesson_repository.add(
                    Lesson(
                        id=uuid.uuid4(),
                        course_id=course_id,
                        weekday=weekday,
                        time_range=time_range,
                        content=content,
                    )
                )
                if not is_first_sync:
                    changes.append(
                        LessonChange(weekday=weekday, time_range=time_range, previous_content=None, new_content=content)
                    )
            elif existing.content != content:
                changes.append(
                    LessonChange(
                        weekday=weekday, time_range=time_range, previous_content=existing.content, new_content=content
                    )
                )
                existing.content = content

        for (weekday, time_range), existing in existing_by_key.items():
            if (weekday, time_range) not in scraped_by_key:
                changes.append(
                    LessonChange(
                        weekday=weekday, time_range=time_range, previous_content=existing.content, new_content=None
                    )
                )
                await self._lesson_repository.delete(existing)

        return changes


def _format_slot_content(slot: ScrapedTimeSlot) -> str:
    return " | ".join(_format_lesson(lesson) for lesson in slot.lessons)


def _format_lesson(lesson: ScrapedLessonSlot) -> str:
    code_prefix = f"{lesson.lesson_code} " if lesson.lesson_code else ""
    return f"{code_prefix}{lesson.lesson_name} — {lesson.teacher}, {lesson.room}"
