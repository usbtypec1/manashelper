from manashelper.services.lesson_search import LessonSearchResult
from manashelper.services.lesson_search_formatter import GROUPS_PER_PAGE, format_lesson_search_page, total_page_count


def _make_result(index: int) -> LessonSearchResult:
    return LessonSearchResult(
        course_id=index,
        course_number=1,
        faculty_name="Факультет",
        department_name="Направление",
        weekday=1,
        content=f"Предмет {index}",
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

    assert first_page.count("Предмет ") == GROUPS_PER_PAGE
    assert second_page.count("Предмет ") == GROUPS_PER_PAGE
    assert third_page.count("Предмет ") == 2
    assert "страница 1/3" in first_page
    assert "страница 2/3" in second_page
    assert "страница 3/3" in third_page
    assert all("Найдено: 16" in page for page in (first_page, second_page, third_page))


def test_format_lesson_search_page_omits_page_indicator_for_single_page() -> None:
    results = [_make_result(i) for i in range(3)]

    page = format_lesson_search_page(results, 0)

    assert "страница" not in page
    assert "Найдено: 3" in page
