import pytest

from manashelper.localization.i18n import i18n
from manashelper.services.obis import ExamModel, LessonAttendanceModel, LessonExamsModel
from manashelper.services.obis_formatter import (
    MAX_PAGE_BODY_CHARS,
    MAX_PAGE_BODY_LINES,
    format_attendance_pages,
    format_exam_grades_pages,
)


@pytest.fixture(autouse=True)
def _en_locale():
    with i18n.context(), i18n.use_locale("en"):
        yield


def test_grades_pages_keep_every_subject_and_handle_missing_values_as_plain_text() -> None:
    lessons = [
        LessonExamsModel(f"Subject <b>& {index}", f"CODE{index}", [ExamModel("Final", "95")]) for index in range(5)
    ]
    lessons.append(LessonExamsModel(None, None, [ExamModel(None, None)]))
    pages = format_exam_grades_pages(lessons)
    assert len(pages) == 3
    assert "Subject <b>& 0 (CODE0)" in pages[0]
    assert "Subject <b>& 2" not in pages[0]
    assert "Subject <b>& 2" in pages[1]
    assert "None" not in pages[-1]
    assert "Exam: -" in pages[-1]
    for index in range(5):
        assert sum(f"Subject <b>& {index}" in page for page in pages) == 1


def test_attendance_keeps_threshold_warnings_percentages_and_remaining_skips() -> None:
    lessons = [
        LessonAttendanceModel("Critical", "C1", 25.0, None, 0, None),
        LessonAttendanceModel("Warning", "C2", 18.75, 12.5, 1, 1),
        LessonAttendanceModel("Safe", "C3", 0, 0, 4, 3),
    ]
    pages = format_attendance_pages(lessons)
    assert len(pages) == 2
    assert "❗ Critical" in pages[0]
    assert "25%" in pages[0] and "Practice: -%" in pages[0]
    assert "⚠️ Warning" in pages[0] and "1 skip left" in pages[0]
    assert "Safe" in pages[1] and "4 skips left" in pages[1]


def test_long_subjects_and_many_exams_fit_pages_without_losing_data() -> None:
    lessons = [
        LessonExamsModel("L" * 4000, "LONG", [ExamModel(f"Unique exam {index}", str(index)) for index in range(40)])
    ]
    pages = format_exam_grades_pages(lessons)
    assert len(pages) > 3
    assert sum(page.count("L") for page in pages) >= 4000
    for index in range(40):
        assert sum(f"Unique exam {index}: {index}" in page for page in pages) == 1
    for page in pages:
        assert len(page.encode("utf-16-le")) // 2 < 4096
        assert len(page) < MAX_PAGE_BODY_CHARS + 100
        assert len(page.split("\n")) <= MAX_PAGE_BODY_LINES + 4


def test_single_page_omits_counter_and_empty_results_are_localized() -> None:
    assert "page" not in format_attendance_pages([LessonAttendanceModel("One", "O1", None, None, None, None)])[0]
    for locale in ("en", "ru", "ky", "tr", "zh"):
        with i18n.use_locale(locale):
            assert i18n.gettext("obis.no_grades") in format_exam_grades_pages([])[0]
            assert i18n.gettext("obis.no_subjects") in format_attendance_pages([])[0]
