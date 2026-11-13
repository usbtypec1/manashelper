"""Read models shared by personal, teacher and room timetables, plus "now / next" calculation."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from manashelper.modules.schedule.application.course_level import CourseLevel, parse_course_level
from manashelper.modules.schedule.application.lesson_items import LessonItemModel, is_reserved, parse_slot_content
from manashelper.modules.schedule.application.time_ranges import (
    MAX_GAP_MINUTES_TO_GROUP,
    parse_time_range_end_minutes,
    parse_time_range_start_minutes,
)
from manashelper.modules.schedule.infrastructure.models.lesson import Lesson

WORKDAYS = (1, 2, 3, 4, 5)
MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True, slots=True)
class TimetableEntry:
    weekday: int
    time_range: str
    code: str | None
    name: str
    teacher: str
    room: str
    department_name: str
    course_number: int
    course_level: CourseLevel

    @property
    def start_minutes(self) -> int:
        return parse_time_range_start_minutes(self.time_range)

    @property
    def end_minutes(self) -> int:
        return parse_time_range_end_minutes(self.time_range)


@dataclass(frozen=True, slots=True)
class EntryBlock:
    """Consecutive periods of one day that hold the same lessons."""

    weekday: int
    start_minutes: int
    end_minutes: int
    time_ranges: tuple[str, ...]
    entries: tuple[TimetableEntry, ...]


@dataclass(frozen=True, slots=True)
class NowNext:
    current: EntryBlock | None
    upcoming: EntryBlock | None
    upcoming_is_today: bool


def lesson_items(lesson: Lesson) -> list[LessonItemModel]:
    """Structured items, falling back to the stored text for slots synchronized before items existed."""
    if lesson.items:
        return [
            LessonItemModel(code=item.code, name=item.name, teacher=item.teacher, room=item.room)
            for item in lesson.items
        ]
    return parse_slot_content(lesson.content)


def lesson_entries(lesson: Lesson) -> list[TimetableEntry]:
    """Entries of one slot; requires ``lesson.course.department`` to be loaded."""
    course = lesson.course
    return [
        TimetableEntry(
            weekday=lesson.weekday,
            time_range=lesson.time_range,
            code=item.code,
            name=item.name,
            teacher=item.teacher,
            room=item.room,
            department_name=course.department.name,
            course_number=course.number,
            course_level=parse_course_level(course.level),
        )
        for item in lesson_items(lesson)
        if not is_reserved(item)
    ]


def _slot_identity(entries: Iterable[TimetableEntry]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        sorted(
            (entry.code or "", entry.name, entry.teacher, entry.room, entry.department_name, entry.course_number)
            for entry in entries
        )
    )


def group_blocks(entries: Sequence[TimetableEntry]) -> list[EntryBlock]:
    slots: dict[tuple[int, str], list[TimetableEntry]] = {}
    for entry in entries:
        slots.setdefault((entry.weekday, entry.time_range), []).append(entry)

    ordered = sorted(slots.items(), key=lambda item: (item[0][0], parse_time_range_start_minutes(item[0][1])))
    blocks: list[EntryBlock] = []
    for (weekday, time_range), slot_entries in ordered:
        start = parse_time_range_start_minutes(time_range)
        end = parse_time_range_end_minutes(time_range)
        previous = blocks[-1] if blocks else None
        if (
            previous is not None
            and previous.weekday == weekday
            and start - previous.end_minutes <= MAX_GAP_MINUTES_TO_GROUP
            and _slot_identity(previous.entries) == _slot_identity(slot_entries)
        ):
            blocks[-1] = EntryBlock(
                weekday=weekday,
                start_minutes=previous.start_minutes,
                end_minutes=end,
                time_ranges=(*previous.time_ranges, time_range),
                entries=previous.entries,
            )
        else:
            blocks.append(
                EntryBlock(
                    weekday=weekday,
                    start_minutes=start,
                    end_minutes=end,
                    time_ranges=(time_range,),
                    entries=tuple(slot_entries),
                )
            )
    return blocks


def find_now_next(entries: Sequence[TimetableEntry], now: datetime) -> NowNext:
    """Block in progress and the next block to start, wrapping to the following week."""
    blocks = group_blocks(entries)
    weekday, minutes = now.isoweekday(), now.hour * 60 + now.minute
    current = next(
        (block for block in blocks if block.weekday == weekday and block.start_minutes <= minutes < block.end_minutes),
        None,
    )
    position = weekday * MINUTES_PER_DAY + minutes

    def distance(block: EntryBlock) -> int:
        start = block.weekday * MINUTES_PER_DAY + block.start_minutes
        return (start - position) % (7 * MINUTES_PER_DAY) or 7 * MINUTES_PER_DAY

    upcoming = min((block for block in blocks if block is not current), key=distance, default=None)
    upcoming_is_today = upcoming is not None and upcoming.weekday == weekday and upcoming.start_minutes > minutes
    return NowNext(current=current, upcoming=upcoming, upcoming_is_today=upcoming_is_today)
