"""Structured parts of one timetable slot and the lookup keys derived from them."""

import re
from dataclasses import dataclass
from enum import StrEnum

from manashelper.modules.schedule.application.text_normalization import fold_turkish

SLOT_SEPARATOR = " | "
TEACHER_SEPARATOR = " — "
ROOM_SEPARATOR = ", "
ONLINE_ROOM_MARKER = "online"

_CODE_AND_NAME_PATTERN = re.compile(r"^(\S+)\s+(.*)$")
_NON_ALPHANUMERIC = re.compile(r"[^0-9a-z]")
_PARENTHESIZED = re.compile(r"\([^)]*\)")
_SECTION_SUFFIX = re.compile(r"\.\d+$")


class LessonKind(StrEnum):
    THEORY = "theory"
    PRACTICE = "practice"


@dataclass(frozen=True, slots=True)
class LessonItemModel:
    code: str | None
    name: str
    teacher: str
    room: str


def format_item(item: LessonItemModel) -> str:
    code_prefix = f"{item.code} " if item.code else ""
    return f"{code_prefix}{item.name}{TEACHER_SEPARATOR}{item.teacher}{ROOM_SEPARATOR}{item.room}"


def format_items(items: list[LessonItemModel]) -> str:
    return SLOT_SEPARATOR.join(format_item(item) for item in items)


def parse_slot_content(content: str) -> list[LessonItemModel]:
    """Inverse of :func:`format_items` for slots stored before structured items existed."""
    items: list[LessonItemModel] = []
    for part in content.split(SLOT_SEPARATOR):
        title, separator, teacher_and_room = part.rpartition(TEACHER_SEPARATOR)
        if not separator:
            title, teacher_and_room = part, ""
        teacher, room_separator, room = teacher_and_room.rpartition(ROOM_SEPARATOR)
        if not room_separator:
            teacher, room = teacher_and_room, ""
        match = _CODE_AND_NAME_PATTERN.match(title)
        code, name = (match.group(1), match.group(2)) if match else (None, title)
        items.append(LessonItemModel(code=code, name=name, teacher=teacher, room=room))
    return items


def room_key(room: str) -> str:
    """Spelling-insensitive room identity: "MFFB 127", "MFFB-127" and "mffb127" share one key."""
    return _NON_ALPHANUMERIC.sub("", fold_turkish(room))


def teacher_key(teacher: str) -> str:
    return " ".join(fold_turkish(teacher).split())


def subject_key(code: str | None) -> str | None:
    """Course code without section and theory/practice markers: "BİL-107.02 (U)" -> "bil107"."""
    if not code:
        return None
    base = _SECTION_SUFFIX.sub("", _PARENTHESIZED.sub("", code).strip())
    return _NON_ALPHANUMERIC.sub("", fold_turkish(base)) or None


def lesson_kind(code: str | None, name: str) -> LessonKind:
    folded = fold_turkish(f"{code or ''} {name}")
    if "(u)" in folded or "uygulama" in folded:
        return LessonKind.PRACTICE
    return LessonKind.THEORY


def is_reserved(item: LessonItemModel) -> bool:
    """The site's "Ayrılmış (Reserved)" placeholder blocks a slot without being a real lesson."""
    return "ayrilmis" in fold_turkish(f"{item.code or ''} {item.name}") and not item.teacher and not item.room


def is_bookable_room(room: str) -> bool:
    """Physical rooms only; online placeholders are never free classrooms."""
    key = room_key(room)
    return bool(key) and ONLINE_ROOM_MARKER not in key


def building_of(room: str) -> str:
    """Building prefix as written on the site: "MFFB-127" -> "MFFB", "İİBF A-205" -> "İİBF"."""
    head = re.split(r"[\s\-]", room.strip(), maxsplit=1)[0]
    return head.upper() if head else room.strip()
