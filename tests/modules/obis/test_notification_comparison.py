from uuid import UUID

import pytest

from manashelper.modules.obis.application.models import (
    AttendanceBaseline,
    ExamGradeRecord,
    ExamModel,
    LessonAttendanceModel,
    LessonExamsModel,
)
from manashelper.modules.obis.application.notification import (
    ExamGradeChange,
    LessonSkipChange,
    SkipType,
    compare_attendance,
    compare_exam_grades,
)


@pytest.mark.parametrize(
    ("old", "new", "expected_scores"),
    [(None, "80", ["80"]), ("80", "90", ["90"]), ("80", None, []), ("80", "80", [])],
)
def test_grade_comparison_keeps_inputs_and_reports_only_nonempty_changes(old, new, expected_scores):
    previous = ExamGradeRecord(UUID(int=1), "MATH", "Final", old)
    records, changes = compare_exam_grades([LessonExamsModel("Math", "MATH", [ExamModel("Final", new)])], [previous])
    assert previous.score == old
    assert [change.score for change in changes] == expected_scores
    assert records == ([] if old == new else [ExamGradeRecord(previous.id, "MATH", "Final", new)])


def test_first_grade_batch_is_silent_but_later_new_exam_notifies():
    lessons = [LessonExamsModel("Math", "MATH", [ExamModel("Final", "90")])]
    records, changes = compare_exam_grades(lessons, [])
    assert records == [ExamGradeRecord(None, "MATH", "Final", "90")]
    assert changes == []

    previous = [ExamGradeRecord(UUID(int=1), "MATH", "Midterm", None)]
    records, changes = compare_exam_grades(lessons, previous)
    assert records == [ExamGradeRecord(None, "MATH", "Final", "90")]
    assert changes == [ExamGradeChange("Math", "Final", "90")]


def test_missing_grades_do_not_delete_existing_baseline_or_notify():
    previous = [ExamGradeRecord(UUID(int=1), "MATH", "Final", "90")]
    assert compare_exam_grades([], previous) == ([], [])
    assert previous[0].score == "90"


@pytest.mark.parametrize(
    ("old", "new", "notify"),
    [(None, 12.5, False), (12.5, 18.75, True), (18.75, 12.5, False), (12.5, None, False), (12.5, 12.5, False)],
)
def test_attendance_only_known_increases_notify_and_inputs_stay_unchanged(old, new, notify):
    previous = AttendanceBaseline(UUID(int=1), "MATH", old, None)
    records, changes = compare_attendance([LessonAttendanceModel("Math", "MATH", new, None, 1, None)], [previous])
    assert previous.theory_skips_percentage == old
    assert records == ([] if old == new else [AttendanceBaseline(previous.id, "MATH", new, None)])
    assert changes == ([LessonSkipChange("Math", SkipType.THEORY, new, 1)] if notify else [])


def test_new_attendance_is_silent_and_theory_precedes_practice():
    lesson = LessonAttendanceModel("Math", "MATH", 18.75, 12.5, 1, 1)
    records, changes = compare_attendance([lesson], [])
    assert records == [AttendanceBaseline(None, "MATH", 18.75, 12.5)]
    assert changes == []

    previous = [AttendanceBaseline(UUID(int=1), "MATH", 12.5, 6.25)]
    _, changes = compare_attendance([lesson], previous)
    assert [change.skip_type for change in changes] == [SkipType.THEORY, SkipType.PRACTICE]


def test_duplicate_existing_grade_observations_compare_against_latest_value():
    previous = [ExamGradeRecord(UUID(int=1), "MATH", "Final", "80")]
    records, changes = compare_exam_grades(
        [LessonExamsModel("Math", "MATH", [ExamModel("Final", "90"), ExamModel("Final", "90")])], previous
    )
    assert len(records) == 1
    assert changes == [ExamGradeChange("Math", "Final", "90")]
    assert previous[0].score == "80"
