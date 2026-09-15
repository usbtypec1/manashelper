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


def _has_lunch_conflict(day_lessons: list[ScheduleLessonModel]) -> bool:
    return any(
        parse_time_range_start_minutes(lesson.time_range) < LUNCH_END_MINUTES
        and parse_time_range_end_minutes(lesson.time_range) > LUNCH_START_MINUTES
        for lesson in day_lessons
    )


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
    lunch_conflict = _has_lunch_conflict(day_lessons)
    show_lunch = not lunch_conflict and _should_show_lunch(day_lessons)
    lunch_label = _("😋 Lunch break. Find out what's for lunch - /yemek")
    lunch_conflict_label = _("😱 There should have been lunch here, but you have a lesson instead.")

    lines = [day_header, ""]
    lunch_inserted = not (show_lunch or lunch_conflict)
    for block in blocks:
        if not lunch_inserted and not lunch_conflict and block.start_minutes >= LUNCH_END_MINUTES:
            lines.append(lunch_label)
            lines.append("")
            lunch_inserted = True

        lesson_name, teacher_and_room = _split_lesson_content(block.content)
        lines.append(f"<b>{lesson_name}</b>")
        if teacher_and_room:
            lines.append(teacher_and_room)
        lines.extend(block.periods)
        lines.append("")

        if (
            not lunch_inserted
            and lunch_conflict
            and block.start_minutes < LUNCH_END_MINUTES
            and block.end_minutes > LUNCH_START_MINUTES
        ):
            lines.append(lunch_conflict_label)
            lines.append("")
            lunch_inserted = True

    if not lunch_inserted:
        lines.append(lunch_conflict_label if lunch_conflict else lunch_label)

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def format_lesson_changes(changes: list[LessonChange]) -> str:
    lines = [_("🔔 Schedule changes:")]
    for change in changes:
        day = weekday_abbr(change.weekday)
        if change.previous_content is None:
            lines.append(
                _("➕ {weekday} {time_range}: {content}").format(
                    weekday=day, time_range=change.time_range, content=change.new_content
                )
            )
        elif change.new_content is None:
            lines.append(
                _("➖ {weekday} {time_range}: {content} (cancelled)").format(
                    weekday=day, time_range=change.time_range, content=change.previous_content
                )
            )
        else:
            lines.append(
                _("✏️ {weekday} {time_range}: {previous} → {new}").format(
                    weekday=day,
                    time_range=change.time_range,
                    previous=change.previous_content,
                    new=change.new_content,
                )
            )
    return "\n".join(lines)
