import re
from dataclasses import dataclass

from bs4 import BeautifulSoup
from bs4.element import Tag

_CODE_AND_NAME_PATTERN = re.compile(r"^(\S+)\s+(.*)$")


class TimetableParseError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ScrapedLessonSlot:
    lesson_code: str | None
    lesson_name: str
    teacher: str
    room: str


@dataclass(frozen=True, slots=True)
class ScrapedTimeSlot:
    weekday: int
    time_range: str
    lessons: list[ScrapedLessonSlot]


def parse_timetable_page(html: str) -> list[ScrapedTimeSlot]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.table-bordered")
    if table is None:
        raise TimetableParseError("Timetable table not found")

    rows = table.select("tr")
    if len(rows) < 2:
        raise TimetableParseError("Timetable table has no data rows")

    time_slots: list[ScrapedTimeSlot] = []
    for row in rows[1:]:
        cells = row.select(":scope > td")
        if len(cells) != 6:
            continue

        time_range = cells[0].get_text().strip()
        for weekday, cell in enumerate(cells[1:], start=1):
            lesson_divs = cell.select("div")
            if not lesson_divs:
                continue
            lessons = [_parse_lesson_div(div) for div in lesson_divs]
            time_slots.append(ScrapedTimeSlot(weekday=weekday, time_range=time_range, lessons=lessons))

    return time_slots


def _parse_lesson_div(div: Tag) -> ScrapedLessonSlot:
    lines = [line.strip() for line in div.get_text(separator="\n").split("\n")]
    lines = [line for line in lines if line]

    code_and_name = lines[0] if lines else ""
    teacher = lines[1] if len(lines) > 1 else ""
    room = lines[2] if len(lines) > 2 else ""

    match = _CODE_AND_NAME_PATTERN.match(code_and_name)
    if match is not None:
        lesson_code, lesson_name = match.group(1), match.group(2)
    else:
        lesson_code, lesson_name = None, code_and_name

    return ScrapedLessonSlot(lesson_code=lesson_code, lesson_name=lesson_name, teacher=teacher, room=room)
