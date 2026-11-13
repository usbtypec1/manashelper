import re
from dataclasses import dataclass

from bs4 import BeautifulSoup
from bs4.element import Tag

_CODE_AND_NAME_PATTERN = re.compile(r"^(\S+)\s+(.*)$")
_ROOM_OPTION_PATTERN = re.compile(r"^(.*?)\s+kapasitesi:\s*(\d+)\s*$", re.IGNORECASE)
ROOM_SELECT_ID = "timetablebundle_dersplangenerator_room"


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


@dataclass(frozen=True, slots=True)
class ScrapedRoom:
    id: int
    name: str
    capacity: int


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


def parse_timetable_title(html: str) -> str | None:
    """The page heading, e.g. "1 - sınıf Bilgisayar Mühendisliği" or "5 - sınıf LEE ... ABD".

    The site relabels graduate headings only with client-side JavaScript, so the raw text is returned.
    """
    heading = BeautifulSoup(html, "lxml").find("h3")
    if heading is None:
        return None
    title = " ".join(heading.get_text().split())
    return title or None


def parse_room_catalog(html: str) -> list[ScrapedRoom]:
    soup = BeautifulSoup(html, "lxml")
    select = soup.find("select", id=ROOM_SELECT_ID)
    if not isinstance(select, Tag):
        raise TimetableParseError("Room selector not found")

    rooms: list[ScrapedRoom] = []
    for option in select.find_all("option"):
        value = str(option.get("value") or "").strip()
        if not value.isdigit():
            continue
        text = " ".join(option.get_text().split())
        match = _ROOM_OPTION_PATTERN.match(text)
        name, capacity = (match.group(1), int(match.group(2))) if match else (text, 0)
        if name:
            rooms.append(ScrapedRoom(id=int(value), name=name, capacity=capacity))
    if not rooms:
        raise TimetableParseError("Room selector has no rooms")
    return rooms


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
