import pytest

from manashelper.localization.i18n import i18n
from manashelper.services.lesson_search import LessonSearchResult
from manashelper.services.lesson_search_formatter import GROUPS_PER_PAGE, format_lesson_search_page, total_page_count


@pytest.fixture(autouse=True)
def _en_locale():
    with i18n.context(), i18n.use_locale("en"):
        yield


def _make_result(index: int) -> LessonSearchResult:
    return LessonSearchResult(
        course_id=index,
        course_number=1,
        faculty_name="Faculty",
        department_name="Department",
        weekday=1,
        content=f"Lesson {index}",
        time_ranges=["09:00-09:50"],
    )


def test_total_page_count_rounds_up() -> None:
    assert total_page_count([_make_result(i) for i in range(16)]) == 3
    assert total_page_count([_make_result(i) for i in range(GROUPS_PER_PAGE)]) == 1
    assert total_page_count([]) == 1


def test_format_lesson_search_page_shows_only_requested_page() -> None:
    results = [_make_result(i) for i in range(16)]

    first_page = format_lesson_search_page(results, 0)
    second_page = format_lesson_search_page(results, 1)
    third_page = format_lesson_search_page(results, 2)

    assert first_page.count("Lesson ") == GROUPS_PER_PAGE
    assert second_page.count("Lesson ") == GROUPS_PER_PAGE
    assert third_page.count("Lesson ") == 2
    assert "page 1/3" in first_page
    assert "page 2/3" in second_page
    assert "page 3/3" in third_page
    assert all("Found: 16" in page for page in (first_page, second_page, third_page))


def test_format_lesson_search_page_omits_page_indicator_for_single_page() -> None:
    results = [_make_result(i) for i in range(3)]

    page = format_lesson_search_page(results, 0)

    assert "page" not in page
    assert "Found: 3" in page
