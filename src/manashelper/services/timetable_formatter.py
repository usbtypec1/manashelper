from dataclasses import dataclass, field
from datetime import datetime

from manashelper.services.schedule import ScheduleLessonModel, parse_time_range_start_minutes
from manashelper.services.timetable_sync import LessonChange

WEEKDAY_LABELS = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт"}
WEEKDAY_FULL_LABELS = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг", 5: "Пятница"}

LUNCH_START_MINUTES = 12 * 60 + 25
LUNCH_END_MINUTES = 14 * 60 + 25
LATE_MORNING_THRESHOLD_MINUTES = 11 * 60 + 30
LUNCH_LABEL = "😋 Обед. Узнать что на йемек - /yemek"

CURRENT_LESSON_EMOJI = "🔥"
UPCOMING_LESSON_EMOJI = "⏰"
UPCOMING_WINDOW_MINUTES = 45

# Regular breaks between periods run ~10 minutes; anything longer (a free period, lunch) starts a new block.
_MAX_GAP_MINUTES_TO_GROUP = 20


@dataclass(slots=True)
class _LessonBlock:
    content: str
    start_minutes: int
    end_minutes: int
    periods: list[str] = field(default_factory=list)


def _parse_end_minutes(time_range: str) -> int:
    hours, minutes = time_range.split("-", 1)[1].split(":")
    return int(hours) * 60 + int(minutes)


def _period_marker(start: int, end: int, now_minutes: int) -> str:
    if start <= now_minutes < end:
        return f"{CURRENT_LESSON_EMOJI} "
    if 0 < start - now_minutes <= UPCOMING_WINDOW_MINUTES:
        return f"{UPCOMING_LESSON_EMOJI} "
    return ""


def _group_into_blocks(day_lessons: list[ScheduleLessonModel], now_minutes: int, is_today: bool) -> list[_LessonBlock]:
    blocks: list[_LessonBlock] = []
    for lesson in day_lessons:
        start = parse_time_range_start_minutes(lesson.time_range)
        end = _parse_end_minutes(lesson.time_range)
        marker = _period_marker(start, end, now_minutes) if is_today else ""
        period = f"- {marker}{lesson.time_range}"

        previous = blocks[-1] if blocks else None
        if (
            previous is not None
            and previous.content == lesson.content
            and start - previous.end_minutes <= _MAX_GAP_MINUTES_TO_GROUP
        ):
            previous.end_minutes = end
            previous.periods.append(period)
        else:
            blocks.append(_LessonBlock(content=lesson.content, start_minutes=start, end_minutes=end, periods=[period]))
    return blocks


def _split_lesson_content(content: str) -> tuple[str, str | None]:
    if " | " in content:
        return content, None

    parts = content.split(" — ", 1)
    if len(parts) != 2:
        return content, None

    lesson_name, teacher_and_room = parts
    teacher_room_parts = teacher_and_room.split(", ", 1)
    if len(teacher_room_parts) != 2:
        return lesson_name, teacher_and_room

    teacher, room = teacher_room_parts
    return lesson_name, f"{teacher} - {room}"


def _should_show_lunch(day_lessons: list[ScheduleLessonModel]) -> bool:
    intervals = [
        (parse_time_range_start_minutes(lesson.time_range), _parse_end_minutes(lesson.time_range))
        for lesson in day_lessons
    ]
    if any(start < LUNCH_END_MINUTES and end > LUNCH_START_MINUTES for start, end in intervals):
        return False

    morning = [(start, end) for start, end in intervals if end <= LUNCH_START_MINUTES]
    afternoon = [(start, end) for start, end in intervals if start >= LUNCH_END_MINUTES]

    if morning and afternoon:
        return True
    if morning and max(end for _, end in morning) > LATE_MORNING_THRESHOLD_MINUTES:
        return True
    return bool(afternoon and min(start for start, _ in afternoon) == LUNCH_END_MINUTES)


def format_day_schedule(weekday: int, lessons: list[ScheduleLessonModel], now: datetime) -> str:
    day_name = WEEKDAY_FULL_LABELS.get(weekday, "?")
    day_lessons = sorted(
        (lesson for lesson in lessons if lesson.weekday == weekday),
        key=lambda lesson: parse_time_range_start_minutes(lesson.time_range),
    )
    if not day_lessons:
        return f"📅 <b>{day_name}</b>\n\nПар нет."

    is_today = weekday == now.isoweekday()
    now_minutes = now.hour * 60 + now.minute
    blocks = _group_into_blocks(day_lessons, now_minutes, is_today)
    show_lunch = _should_show_lunch(day_lessons)

    lines = [f"📅 <b>{day_name}</b>", ""]
    lunch_inserted = not show_lunch
    for block in blocks:
        if not lunch_inserted and block.start_minutes >= LUNCH_END_MINUTES:
            lines.append(LUNCH_LABEL)
            lines.append("")
            lunch_inserted = True

        lesson_name, teacher_and_room = _split_lesson_content(block.content)
        lines.append(f"<b>{lesson_name}</b>")
        if teacher_and_room:
            lines.append(teacher_and_room)
        lines.extend(block.periods)
        lines.append("")

    if not lunch_inserted:
        lines.append(LUNCH_LABEL)

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def format_lesson_changes(changes: list[LessonChange]) -> str:
    lines = ["🔔 Изменения в расписании:"]
    for change in changes:
        day = WEEKDAY_LABELS.get(change.weekday, "?")
        if change.previous_content is None:
            lines.append(f"➕ {day} {change.time_range}: {change.new_content}")
        elif change.new_content is None:
            lines.append(f"➖ {day} {change.time_range}: {change.previous_content} (отменено)")
        else:
            lines.append(f"✏️ {day} {change.time_range}: {change.previous_content} → {change.new_content}")
    return "\n".join(lines)
