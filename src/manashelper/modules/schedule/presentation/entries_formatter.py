"""Telegram HTML for teacher, room and personal "now / next" timetables."""

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum

from aiogram.utils.i18n import gettext as _

from manashelper.localization.weekdays import weekday_abbr, weekday_full
from manashelper.modules.schedule.application.campus import FreeRoom, FreeRooms, RoomInfo
from manashelper.modules.schedule.application.time_ranges import format_minutes
from manashelper.modules.schedule.application.timetable_entries import (
    EntryBlock,
    NowNext,
    TimetableEntry,
    group_blocks,
)
from manashelper.modules.schedule.presentation.labels import course_label
from manashelper.platform.telegram.html import escape_html

MAX_MESSAGE_CHARS = 3800
CURRENT_EMOJI = "🔥"
UPCOMING_EMOJI = "⏰"


class Perspective(StrEnum):
    """Which details a line repeats; the viewed teacher or room is already in the header."""

    PERSONAL = "personal"
    TEACHER = "teacher"
    ROOM = "room"


def block_span(block: EntryBlock) -> str:
    return f"{format_minutes(block.start_minutes)}–{format_minutes(block.end_minutes)}"


def _title(entry: TimetableEntry) -> str:
    code = f"{entry.code} " if entry.code else ""
    return f"<b>{escape_html(code + entry.name)}</b>"


def _details(entry: TimetableEntry, perspective: Perspective) -> str:
    group = f"{entry.department_name}, {course_label(entry.course_number, entry.course_level)}"
    parts: list[str] = []
    if perspective != Perspective.TEACHER and entry.teacher:
        parts.append(f"👨‍🏫 {escape_html(entry.teacher)}")
    if perspective != Perspective.ROOM and entry.room:
        parts.append(f"🚪 {escape_html(entry.room)}")
    if perspective != Perspective.PERSONAL:
        parts.append(f"🎓 {escape_html(group)}")
    return " · ".join(parts)


def format_block_entries(block: EntryBlock, perspective: Perspective) -> list[str]:
    lines: list[str] = []
    for entry in block.entries:
        lines.append(_title(entry))
        details = _details(entry, perspective)
        if details:
            lines.append(details)
    return lines


def _truncate(lines: list[str]) -> str:
    text = "\n".join(lines)
    if len(text) <= MAX_MESSAGE_CHARS:
        return text
    kept: list[str] = []
    for line in lines:
        if len("\n".join([*kept, line])) > MAX_MESSAGE_CHARS - 10:
            break
        kept.append(line)
    return "\n".join([*kept, "…"])


def format_day_entries(
    weekday: int, entries: Sequence[TimetableEntry], perspective: Perspective, now: datetime
) -> list[str]:
    blocks = [block for block in group_blocks(entries) if block.weekday == weekday]
    lines = [_("schedule.day_header").format(day=weekday_full(weekday)), ""]
    if not blocks:
        lines.append(_("schedule.no_classes"))
        return lines
    minutes = now.hour * 60 + now.minute
    for block in blocks:
        marker = ""
        if weekday == now.isoweekday():
            if block.start_minutes <= minutes < block.end_minutes:
                marker = f"{CURRENT_EMOJI} "
            elif 0 < block.start_minutes - minutes <= 45:
                marker = f"{UPCOMING_EMOJI} "
        lines.append(f"{marker}🕘 {block_span(block)}")
        lines.extend(format_block_entries(block, perspective))
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _upcoming_when(block: EntryBlock, now_next: NowNext, now: datetime) -> str:
    start = format_minutes(block.start_minutes)
    if now_next.upcoming_is_today:
        left = block.start_minutes - (now.hour * 60 + now.minute)
        return _("schedule.now.today_at").format(time=start, minutes=left)
    return f"{weekday_abbr(block.weekday)} {start}"


def format_status(now_next: NowNext, perspective: Perspective, now: datetime, *, idle_text: str) -> list[str]:
    lines: list[str] = []
    if now_next.current is not None:
        block = now_next.current
        lines.append(_("schedule.now.current").format(until=format_minutes(block.end_minutes)))
        lines.extend(format_block_entries(block, perspective))
    else:
        lines.append(idle_text)
    if now_next.upcoming is not None:
        lines.append("")
        lines.append(_("schedule.now.next").format(when=_upcoming_when(now_next.upcoming, now_next, now)))
        lines.extend(format_block_entries(now_next.upcoming, perspective))
    return lines


def format_now_next(now_next: NowNext, now: datetime) -> str:
    lines = [_("schedule.now.header"), ""]
    if now_next.current is None and now_next.upcoming is None:
        lines.append(_("schedule.not_loaded"))
        return "\n".join(lines)
    lines.extend(format_status(now_next, Perspective.PERSONAL, now, idle_text=_("schedule.now.idle")))
    return _truncate(lines)


def format_teacher(name: str, entries: Sequence[TimetableEntry], weekday: int, now_next: NowNext, now: datetime) -> str:
    lines = [f"👨‍🏫 <b>{escape_html(name)}</b>", ""]
    lines.extend(format_status(now_next, Perspective.TEACHER, now, idle_text=_("schedule.teacher.idle")))
    lines.append("")
    lines.extend(format_day_entries(weekday, entries, Perspective.TEACHER, now))
    return _truncate(lines)


def _capacity(capacity: int | None) -> str:
    return _("schedule.rooms.capacity").format(capacity=capacity) if capacity else ""


def format_room(
    room: RoomInfo, entries: Sequence[TimetableEntry], weekday: int, now_next: NowNext, now: datetime
) -> str:
    capacity = _capacity(room.capacity)
    header = f"🚪 <b>{escape_html(room.name)}</b>" + (f" · {capacity}" if capacity else "")
    lines = [header, ""]
    lines.extend(format_status(now_next, Perspective.ROOM, now, idle_text=_("schedule.rooms.idle")))
    lines.append("")
    lines.extend(format_day_entries(weekday, entries, Perspective.ROOM, now))
    return _truncate(lines)


def _free_room_line(room: FreeRoom) -> str:
    parts = [f"<b>{escape_html(room.name)}</b>"]
    capacity = _capacity(room.capacity)
    if capacity:
        parts.append(capacity)
    if room.free_until_minutes is None:
        parts.append(_("schedule.rooms.free_all_day"))
    else:
        parts.append(_("schedule.rooms.free_until").format(time=format_minutes(room.free_until_minutes)))
    return "• " + " · ".join(parts)


def _free_rooms_header(result: FreeRooms, building: str) -> list[str]:
    title = (
        _("schedule.rooms.free_building_header").format(building=escape_html(building))
        if building
        else _("schedule.rooms.free_header")
    )
    when = f"📅 {weekday_full(result.weekday)} · {result.time_range}" if result.periods else ""
    return [title, when, ""]


def format_free_rooms(result: FreeRooms, building: str) -> str:
    lines = _free_rooms_header(result, building)
    if not result.periods:
        lines.append(_("schedule.not_loaded"))
        return "\n".join(lines)
    rooms = [room for room in result.rooms if not building or room.building == building]
    if not rooms:
        lines.append(_("schedule.rooms.none_free"))
        return "\n".join(lines)
    if not building:
        lines.append(_("schedule.rooms.choose_building").format(count=len(rooms)))
        return "\n".join(lines)
    lines.extend(_free_room_line(room) for room in rooms)
    return _truncate(lines)
