import uuid
from dataclasses import dataclass

from manashelper.modules.schedule.application.text_normalization import fold_turkish
from manashelper.modules.schedule.application.timetable_sync import LessonChange, format_slot_content
from manashelper.modules.schedule.infrastructure.models.lesson import Lesson
from manashelper.modules.schedule.infrastructure.models.lesson_history import LessonHistory
from manashelper.modules.schedule.infrastructure.repositories.lesson import LessonRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson_history import LessonHistoryRepository
from manashelper.modules.schedule.infrastructure.timetable_client import TimetableClient
from manashelper.modules.schedule.infrastructure.timetable_parser import (
    parse_timetable_page,
)


@dataclass(frozen=True, slots=True)
class SyncTimetableUseCase:
    timetable_client: TimetableClient
    lesson_repository: LessonRepository
    lesson_history_repository: LessonHistoryRepository

    async def execute(self, course_id: int) -> list[LessonChange]:
        html = await self.timetable_client.fetch_timetable_html(course_id)
        scraped_slots = parse_timetable_page(html)
        scraped_by_key = {(slot.weekday, slot.time_range): format_slot_content(slot) for slot in scraped_slots}

        existing_lessons = await self.lesson_repository.get_all_by_course_id(course_id)
        existing_by_key = {(lesson.weekday, lesson.time_range): lesson for lesson in existing_lessons}
        is_first_sync = not existing_lessons

        changes: list[LessonChange] = []
        for (weekday, time_range), content in scraped_by_key.items():
            existing = existing_by_key.get((weekday, time_range))
            if existing is None:
                self.lesson_repository.add(
                    Lesson(
                        id=uuid.uuid4(),
                        course_id=course_id,
                        weekday=weekday,
                        time_range=time_range,
                        content=content,
                        normalized_content=fold_turkish(content),
                    )
                )
                if not is_first_sync:
                    changes.append(
                        LessonChange(weekday=weekday, time_range=time_range, previous_content=None, new_content=content)
                    )
            else:
                if existing.content != content:
                    changes.append(
                        LessonChange(
                            weekday=weekday,
                            time_range=time_range,
                            previous_content=existing.content,
                            new_content=content,
                        )
                    )
                    existing.content = content
                existing.normalized_content = fold_turkish(content)

        for (weekday, time_range), existing in existing_by_key.items():
            if (weekday, time_range) not in scraped_by_key:
                changes.append(
                    LessonChange(
                        weekday=weekday, time_range=time_range, previous_content=existing.content, new_content=None
                    )
                )
                await self.lesson_repository.delete(existing)

        for change in changes:
            self.lesson_history_repository.add(
                LessonHistory(
                    id=uuid.uuid4(),
                    course_id=course_id,
                    weekday=change.weekday,
                    time_range=change.time_range,
                    previous_content=change.previous_content,
                    new_content=change.new_content,
                )
            )

        return changes
