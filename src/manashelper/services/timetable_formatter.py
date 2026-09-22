from dataclasses import dataclass, field
from datetime import datetime

from aiogram.utils.i18n import gettext as _

from manashelper.services.schedule import (
    LUNCH_END_MINUTES,
    LUNCH_START_MINUTES,
    MAX_GAP_MINUTES_TO_GROUP,
    ScheduleLessonModel,
    parse_time_range_end_minutes,
    parse_time_range_start_minutes,
)
from manashelper.services.timetable_sync import LessonChange

LATE_MORNING_THRESHOLD_MINUTES = 11 * 60 + 30

CURRENT_LESSON_EMOJI = "🔥"
UPCOMING_LESSON_EMOJI = "⏰"
UPCOMING_WINDOW_MINUTES = 45


def weekday_abbr(weekday: int) -> str:
    match weekday:
        case 1:
            return _("Mon")
        case 2:
            return _("Tue")
        case 3:
            return _("Wed")
        case 4:
            return _("Thu")
        case 5:
            return _("Fri")
        case 6:
            return _("Sat")
        case _:
            return _("Sun")


def weekday_full(weekday: int) -> str:
    match weekday:
        case 1:
            return _("Monday")
        case 2:
            return _("Tuesday")
        case 3:
            return _("Wednesday")
        case 4:
            return _("Thursday")
        case 5:
            return _("Friday")
        case 6:
            return _("Saturday")
        case _:
            return _("Sunday")


@dataclass(slots=True)
class _LessonBlock:
    content: str
    start_minutes: int
    end_minutes: int
    periods: list[str] = field(default_factory=list)


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
        end = parse_time_range_end_minutes(lesson.time_range)
        marker = _period_marker(start, end, now_minutes) if is_today else ""
        period = f"- {marker}{lesson.time_range}"

        previous = blocks[-1] if blocks else None
        if (
            previous is not None
            and previous.content == lesson.content
            and start - previous.end_minutes <= MAX_GAP_MINUTES_TO_GROUP
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
        (parse_time_range_start_minutes(lesson.time_range), parse_time_range_end_minutes(lesson.time_range))
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
    day_name = weekday_full(weekday)
    day_lessons = sorted(
        (lesson for lesson in lessons if lesson.weekday == weekday),
        key=lambda lesson: parse_time_range_start_minutes(lesson.time_range),
    )
    day_header = _("📅 <b>{day}</b>").format(day=day_name)
    if not day_lessons:
        return f"{day_header}\n\n{_('No classes.')}"

    is_today = weekday == now.isoweekday()
    now_minutes = now.hour * 60 + now.minute
    blocks = _group_into_blocks(day_lessons, now_minutes, is_today)
    show_lunch = _should_show_lunch(day_lessons)
    lunch_label = _("😋 Lunch break. Find out what's for lunch - /yemek")

    lines = [day_header, ""]
    lunch_inserted = not show_lunch
    for block in blocks:
        if not lunch_inserted and block.start_minutes >= LUNCH_END_MINUTES:
            lines.append(lunch_label)
            lines.append("")
            lunch_inserted = True

        lesson_name, teacher_and_room = _split_lesson_content(block.content)
        lines.append(f"<b>{lesson_name}</b>")
        if teacher_and_room:
            lines.append(teacher_and_room)
        lines.extend(block.periods)
        lines.append("")

    if not lunch_inserted:
        lines.append(lunch_label)

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _format_change_lesson_content(content: str) -> str:
    lines = []
    for part in content.split(" | "):
        lesson_name, teacher_and_room = _split_lesson_content(part)
        lines.append(f"<b>{lesson_name}</b>")
        if teacher_and_room:
            lines.append(teacher_and_room)
    return "\n".join(lines)


def _format_change_block(change: LessonChange) -> str:
    previous_content, new_content = change.previous_content, change.new_content
    if previous_content is None and new_content is not None:
        return _("➕ {time_range}\n{content}").format(
            time_range=change.time_range, content=_format_change_lesson_content(new_content)
        )
    if new_content is None and previous_content is not None:
        return _("➖ {time_range} (cancelled)\n{content}").format(
            time_range=change.time_range, content=_format_change_lesson_content(previous_content)
        )
    assert previous_content is not None
    assert new_content is not None
    return _("✏️ {time_range}\n{previous}\n→\n{new}").format(
        time_range=change.time_range,
        previous=_format_change_lesson_content(previous_content),
        new=_format_change_lesson_content(new_content),
    )


def format_lesson_changes(changes: list[LessonChange]) -> str:
    by_weekday: dict[int, list[LessonChange]] = {}
    for change in changes:
        by_weekday.setdefault(change.weekday, []).append(change)

    sections = [_("🔔 <b>Schedule changes</b>")]
    for weekday in sorted(by_weekday):
        day_changes = sorted(by_weekday[weekday], key=lambda change: change.time_range)
        day_lines = [_("📅 <b>{day}</b>").format(day=weekday_full(weekday))]
        for change in day_changes:
            day_lines.append("")
            day_lines.append(_format_change_block(change))
        sections.append("\n".join(day_lines))

    return "\n\n".join(sections)
