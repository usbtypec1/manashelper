import math

from manashelper.services.lesson_search import LessonSearchResult
from manashelper.services.timetable_formatter import WEEKDAY_LABELS

GROUPS_PER_PAGE = 7


def total_page_count(results: list[LessonSearchResult]) -> int:
    return max(1, math.ceil(len(results) / GROUPS_PER_PAGE))


def _format_result(result: LessonSearchResult) -> list[str]:
    weekday_label = WEEKDAY_LABELS.get(result.weekday, "?")
    lines = [
        f"🏫 {result.faculty_name} — {result.department_name}, {result.course_number} курс",
        f"📅 {weekday_label}",
        result.content,
    ]
    lines.extend(f"- {time_range}" for time_range in result.time_ranges)
    return lines


def format_lesson_search_page(results: list[LessonSearchResult], page: int) -> str:
    total = len(results)
    total_pages = total_page_count(results)
    start = page * GROUPS_PER_PAGE
    chunk = results[start : start + GROUPS_PER_PAGE]

    header = f"🔎 Найдено: {total}"
    if total_pages > 1:
        header += f" (страница {page + 1}/{total_pages})"
    lines = [header, ""]

    for result in chunk:
        lines.extend(_format_result(result))
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
