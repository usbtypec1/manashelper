from dataclasses import dataclass, field
from datetime import datetime

from aiogram.utils.i18n import gettext as _

from manashelper.localization.weekdays import weekday_full
from manashelper.modules.schedule.application.lesson_items import LessonItemModel, parse_slot_content
from manashelper.modules.schedule.application.schedule import ScheduleLessonModel
from manashelper.modules.schedule.application.time_ranges import (
    LUNCH_END_MINUTES,
    LUNCH_START_MINUTES,
    MAX_GAP_MINUTES_TO_GROUP,
    format_minutes,
    parse_time_range_end_minutes,
    parse_time_range_start_minutes,
)
from manashelper.modules.schedule.application.timetable_sync import LessonChange
from manashelper.platform.telegram.html import escape_html

LATE_MORNING_THRESHOLD_MINUTES = 11 * 60 + 30

CURRENT_LESSON_EMOJI = "🔥"
UPCOMING_LESSON_EMOJI = "⏰"
UPCOMING_WINDOW_MINUTES = 45


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


def _item_title(item: LessonItemModel) -> str:
    code = f"{item.code} " if item.code else ""
    return escape_html(code + item.name)


def _item_details(item: LessonItemModel) -> str | None:
    if item.teacher and item.room:
        return escape_html(f"{item.teacher} - {item.room}")
    return escape_html(item.teacher or item.room) or None


def _format_items(items: list[LessonItemModel]) -> list[str]:
    lines: list[str] = []
    for item in items:
        lines.append(f"<b>{_item_title(item)}</b>")
        details = _item_details(item)
        if details:
            lines.append(details)
    return lines


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
    day_header = _("schedule.day_header").format(day=day_name)
    if not day_lessons:
        return f"{day_header}\n\n{_('schedule.no_classes')}"

    is_today = weekday == now.isoweekday()
    now_minutes = now.hour * 60 + now.minute
    blocks = _group_into_blocks(day_lessons, now_minutes, is_today)
    show_lunch = _should_show_lunch(day_lessons)
    lunch_label = _("schedule.lunch_break")

    lines = [day_header, ""]
    lunch_inserted = not show_lunch
    for block in blocks:
        if not lunch_inserted and block.start_minutes >= LUNCH_END_MINUTES:
            lines.append(lunch_label)
            lines.append("")
            lunch_inserted = True

        items = parse_slot_content(block.content)
        if len(items) == 1:
            lines.extend(_format_items(items))
        else:
            lines.append(f"<b>{escape_html(block.content)}</b>")
        lines.extend(block.periods)
        lines.append("")

    if not lunch_inserted:
        lines.append(lunch_label)

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class MergedChange:
    """Consecutive periods of one day that changed in exactly the same way."""

    weekday: int
    start_minutes: int
    end_minutes: int
    previous_content: str | None
    new_content: str | None

    @property
    def span(self) -> str:
        return f"{format_minutes(self.start_minutes)}–{format_minutes(self.end_minutes)}"


def merge_changes(changes: list[LessonChange]) -> list[MergedChange]:
    ordered = sorted(changes, key=lambda change: (change.weekday, parse_time_range_start_minutes(change.time_range)))
    merged: list[MergedChange] = []
    for change in ordered:
        start = parse_time_range_start_minutes(change.time_range)
        end = parse_time_range_end_minutes(change.time_range)
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and previous.weekday == change.weekday
            and (previous.previous_content, previous.new_content) == (change.previous_content, change.new_content)
            and start - previous.end_minutes <= MAX_GAP_MINUTES_TO_GROUP
        ):
            merged[-1] = MergedChange(
                previous.weekday, previous.start_minutes, end, previous.previous_content, previous.new_content
            )
        else:
            merged.append(MergedChange(change.weekday, start, end, change.previous_content, change.new_content))
    return merged


def _detail_changes(previous: list[LessonItemModel], new: list[LessonItemModel]) -> list[str] | None:
    """Room/teacher moves of the same lessons, or None when the lessons themselves changed."""
    if len(previous) != len(new) or any(
        (old.code, old.name) != (current.code, current.name) for old, current in zip(previous, new, strict=True)
    ):
        return None
    lines: list[str] = []
    for old, current in zip(previous, new, strict=True):
        if (old.teacher, old.room) == (current.teacher, current.room):
            continue
        lines.append(f"<b>{_item_title(current)}</b>")
        if old.room != current.room:
            lines.append(
                _("schedule.change_room").format(
                    previous=escape_html(old.room or "—"), new=escape_html(current.room or "—")
                )
            )
        if old.teacher != current.teacher:
            lines.append(
                _("schedule.change_teacher").format(
                    previous=escape_html(old.teacher or "—"), new=escape_html(current.teacher or "—")
                )
            )
    return lines or None


def _format_change_block(change: MergedChange) -> str:
    previous_content, new_content = change.previous_content, change.new_content
    if previous_content is None and new_content is not None:
        return _("schedule.change_added").format(
            time_range=change.span, content="\n".join(_format_items(parse_slot_content(new_content)))
        )
    if new_content is None and previous_content is not None:
        return _("schedule.change_cancelled").format(
            time_range=change.span, content="\n".join(_format_items(parse_slot_content(previous_content)))
        )
    assert previous_content is not None
    assert new_content is not None
    previous_items, new_items = parse_slot_content(previous_content), parse_slot_content(new_content)
    details = _detail_changes(previous_items, new_items)
    if details is not None:
        return _("schedule.change_details").format(time_range=change.span, content="\n".join(details))
    return _("schedule.change_updated").format(
        time_range=change.span,
        previous="\n".join(_format_items(previous_items)),
        new="\n".join(_format_items(new_items)),
    )


def format_lesson_changes(changes: list[LessonChange]) -> str:
    by_weekday: dict[int, list[MergedChange]] = {}
    for change in merge_changes(changes):
        by_weekday.setdefault(change.weekday, []).append(change)

    sections = [_("schedule.changes_header")]
    for weekday in sorted(by_weekday):
        day_lines = [_("schedule.day_header").format(day=weekday_full(weekday))]
        for change in by_weekday[weekday]:
            day_lines.append("")
            day_lines.append(_format_change_block(change))
        sections.append("\n".join(day_lines))

    return "\n\n".join(sections)
