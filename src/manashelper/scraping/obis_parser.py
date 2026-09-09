from dataclasses import dataclass

from bs4 import BeautifulSoup
from bs4.element import Tag


class ObisParseError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ScrapedExam:
    name: str | None
    score: str | None


@dataclass(frozen=True, slots=True)
class ScrapedLessonExams:
    lesson_name: str | None
    lesson_code: str | None
    exams: list[ScrapedExam]


@dataclass(frozen=True, slots=True)
class ScrapedLessonAttendance:
    lesson_name: str
    lesson_code: str
    theory_skips_percentage: float | None
    practice_skips_percentage: float | None


def parse_login_page_csrf_token(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    csrf_input = soup.select_one("form input[name=_csrf]")
    if csrf_input is None:
        raise ObisParseError("CSRF токен не найден на странице логина OBIS.")

    token = csrf_input.get("value")
    if not isinstance(token, str) or not token:
        raise ObisParseError("CSRF токен не найден на странице логина OBIS.")
    return token


def parse_exam_grades_page(html: str) -> list[ScrapedLessonExams]:
    soup = BeautifulSoup(html, "lxml")
    table_bodies = soup.select("tbody")
    if not table_bodies:
        raise ObisParseError("На странице в OBIS отсутствует таблица с оценками.")

    rows = table_bodies[-1].select(":scope > tr")

    lessons: list[ScrapedLessonExams] = []
    i = 0
    while i < len(rows):
        cells = rows[i].select(":scope > td")

        if len(cells) != 5:
            i += 1
            continue

        lesson_code = _text_or_none(cells[1])
        lesson_name = _text_or_none(cells[2])

        rowspan_attr = cells[0].get("rowspan")
        rowspan = int(rowspan_attr) if isinstance(rowspan_attr, str) else 1

        exams = [ScrapedExam(name=_text_or_none(cells[3]), score=_text_or_none(cells[4]))]

        for j in range(1, rowspan):
            if i + j >= len(rows):
                break
            next_cells = rows[i + j].select(":scope > td")
            if len(next_cells) == 2:
                exams.append(ScrapedExam(name=_text_or_none(next_cells[0]), score=_text_or_none(next_cells[1])))

        lessons.append(ScrapedLessonExams(lesson_name=lesson_name, lesson_code=lesson_code, exams=exams))
        i += rowspan

    return lessons


def parse_attendance_page(html: str) -> list[ScrapedLessonAttendance]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table")
    if table is None:
        raise ObisParseError("На странице в OBIS отсутствует таблица с посещаемостью.")

    rows = table.select("tr")
    lessons: list[ScrapedLessonAttendance] = []

    for row in rows[1:]:
        cells = row.select("td")
        if len(cells) != 9:
            continue

        lesson_code = cells[1].get_text().strip()
        lesson_name = cells[2].get_text().strip()
        theory_percentage = cells[4].get_text().replace("%", "").strip()
        practice_percentage = cells[6].get_text().replace("%", "").strip()

        lessons.append(
            ScrapedLessonAttendance(
                lesson_name=lesson_name,
                lesson_code=lesson_code,
                theory_skips_percentage=_try_parse_float(theory_percentage),
                practice_skips_percentage=_try_parse_float(practice_percentage),
            )
        )

    return lessons


def _text_or_none(cell: Tag) -> str | None:
    text = cell.get_text().strip()
    return text or None


def _try_parse_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None
