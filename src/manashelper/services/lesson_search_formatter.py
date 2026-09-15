import math

from aiogram.utils.i18n import gettext as _

from manashelper.services.lesson_search import LessonSearchResult
from manashelper.services.timetable_formatter import weekday_abbr

GROUPS_PER_PAGE = 7


def total_page_count(results: list[LessonSearchResult]) -> int:
    return max(1, math.ceil(len(results) / GROUPS_PER_PAGE))


def _format_result(result: LessonSearchResult) -> list[str]:
    course_year = _("Year {number}").format(number=result.course_number)
    lines = [
        _("🏫 {faculty} — {department}, {course_year}").format(
            faculty=result.faculty_name, department=result.department_name, course_year=course_year
        ),
        _("📅 {weekday}").format(weekday=weekday_abbr(result.weekday)),
        result.content,
    ]
    lines.extend(f"- {time_range}" for time_range in result.time_ranges)
    return lines


def format_lesson_search_page(results: list[LessonSearchResult], page: int) -> str:
    total = len(results)
    total_pages = total_page_count(results)
    start = page * GROUPS_PER_PAGE
    chunk = results[start : start + GROUPS_PER_PAGE]

    if total_pages > 1:
        header = _("🔎 Found: {total} (page {page}/{total_pages})").format(
            total=total, page=page + 1, total_pages=total_pages
        )
    else:
        header = _("🔎 Found: {total}").format(total=total)
    lines = [header, ""]

    for result in chunk:
        lines.extend(_format_result(result))
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
