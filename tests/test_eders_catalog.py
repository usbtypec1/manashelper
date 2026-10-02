import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from manashelper.localization.i18n import i18n
from manashelper.scraping.eders_parser import (
    EdersGradesUnavailableError,
    EdersParseError,
    parse_activity_details,
    parse_course_activities,
    parse_course_grades,
)
from manashelper.scraping.eders_urls import EDERS_BASE_URL
from manashelper.services.eders import filter_activities
from manashelper.services.eders_catalog import catalog_courses, find_grades, find_materials
from manashelper.services.eders_catalog_formatter import format_catalog_page
from manashelper.services.eders_formatter import format_activity_page, format_eders_event
from manashelper.services.eders_models import (
    ActivityDate,
    ActivityKind,
    DeadlineFilter,
    EdersActivity,
    EdersCourse,
    EdersGrade,
    EdersSnapshot,
    GradingStatus,
    QuizAttempt,
    SubmissionStatus,
)
from manashelper.services.eders_serialization import deserialize_snapshot, serialize_snapshot
from manashelper.services.eders_tracking import EdersSettings, plan_content_events

NOW = datetime(2026, 10, 1, tzinfo=UTC)
COURSE = EdersCourse(10, "Math & <test>")
FIXTURES = Path(__file__).parent / "fixtures/eders"
SETTINGS = EdersSettings(True, True, True, True, True)


def item(**changes):
    return replace(
        EdersActivity(
            22,
            COURSE,
            ActivityKind.RESOURCE,
            "Reading",
            f"{EDERS_BASE_URL}/mod/resource/view.php?id=22",
            section="Week 1",
        ),
        **changes,
    )


def grade(**changes):
    return replace(
        EdersGrade(
            301,
            COURSE,
            "Work",
            f"{EDERS_BASE_URL}/mod/assign/view.php?id=20",
            grade="0",
            feedback="Good",
            visible_fields=("grade", "feedback"),
        ),
        **changes,
    )


def snapshot(activities=(), grades=(), **changes):
    return replace(EdersSnapshot(tuple(activities), NOW, tuple(grades), True, True, (COURSE,)), **changes)


def test_grade_report_handles_zero_missing_and_optional_columns_and_safe_links() -> None:
    html = (FIXTURES / "grades.html").read_text(encoding="utf-8")
    items = parse_course_grades(html, COURSE)
    assert [g.id for g in items] == [301, 302]
    assert items[0].grade == "0.00" and items[0].percentage == "0.00 %"
    assert items[0].feedback == "Please revise <section>"
    assert items[0].weight == "20 %" and items[0].range == "0–100" and items[0].contribution == "0.00 %"
    assert items[0].url == f"{EDERS_BASE_URL}/mod/assign/view.php?id=20"
    assert items[1].grade is None and items[1].feedback is None
    assert items[1].percentage is None and "percentage" not in items[1].visible_fields
    unsafe = html.replace("/mod/assign/view.php?id=20", "/mod/assign/view.php?id=20&amp;sesskey=secret")
    assert parse_course_grades(unsafe, COURSE)[0].url == f"{EDERS_BASE_URL}/grade/report/user/index.php?id=10"


@pytest.mark.parametrize(
    "html",
    [
        '<main id="region-main"></main>',
        '<input name="logintoken">',
        '<main id="region-main"><table class="user-grade"><tr><th>Broken row</th>'
        '<td headers="grade99">0</td></tr></table></main>',
    ],
)
def test_broken_grade_markup_is_not_observed_as_empty_report(html) -> None:
    with pytest.raises(EdersParseError):
        parse_course_grades(html, COURSE)


def test_known_hidden_grade_report_is_distinct_from_parse_failure_and_zero_grade() -> None:
    html = '<main id="region-main"><div class="alert-danger">Cannot view grades.</div></main>'
    with pytest.raises(EdersGradesUnavailableError):
        parse_course_grades(html, COURSE)


def test_quiz_final_result_comes_from_result_block_without_overriding_active_attempt() -> None:
    html = (
        (FIXTURES / "quiz.html")
        .read_text(encoding="utf-8")
        .replace("</main>", '<div id="feedback"><h3>Your final grade for this quiz is 0.00/100</h3></div></main>')
    )
    quiz = item(kind=ActivityKind.QUIZ, id=21, url=f"{EDERS_BASE_URL}/mod/quiz/view.php?id=21")
    parsed = parse_activity_details(html, quiz)
    assert parsed.quiz_result == "Your final grade for this quiz is 0.00/100"
    assert parsed.submission == SubmissionStatus.IN_PROGRESS


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
def test_long_quiz_details_stay_within_telegram_limit(locale) -> None:
    enormous = item(
        kind=ActivityKind.QUIZ,
        name="&" * 5000,
        section="&" * 5000,
        course=EdersCourse(10, "&" * 5000),
        opens=ActivityDate(source_text="&" * 5000),
        closes=ActivityDate(source_text="&" * 5000, conflict=True),
        quiz_result="&" * 5000,
        attempts=tuple(
            QuizAttempt("&" * 5000, SubmissionStatus.SUBMITTED, GradingStatus.GRADED, "&" * 5000) for _ in range(5)
        ),
    )
    with i18n.context(), i18n.use_locale(locale):
        assert len(format_activity_page([enormous], 0)) < 4096


def test_materials_capture_sections_pages_books_folders_labels_and_quizzes() -> None:
    modules = [("page", 31), ("book", 32), ("folder", 33), ("url", 34), ("quiz", 35), ("h5pactivity", 36)]
    rows = "".join(
        '<li class="activity"><div class="activityname">'
        f'<a href="/mod/{kind}/view.php?id={identifier}">'
        f'<span class="instancename">Topic {identifier}</span></a></div></li>'
        for kind, identifier in modules
    )
    html = (
        '<main id="region-main"><div class="course-content"><ul><li class="section">'
        f'<h3 class="sectionname">Week 2: Probability</h3><ul>{rows}'
        '<li class="activity modtype_label" id="module-37">'
        '<div class="contentwithoutlink">Video introduction</div></li></ul></li></ul></div></main>'
    )
    items = parse_course_activities(html, COURSE)
    assert len(items) == 7 and all(i.section == "Week 2: Probability" for i in items)
    assert items[-1].kind == ActivityKind.LABEL
    assert items[-1].url == f"{EDERS_BASE_URL}/course/view.php?id=10"
    data = snapshot(items)
    assert len(find_materials(data, 10, "probability")) == 7
    assert len(find_materials(data, query="topic 31")) == 1
    assert find_materials(data, 11) == []
    assert find_materials(data, query="ＰＲＯＢＡＢＩＬＩＴＹ") == find_materials(data, query="probability")
    assert catalog_courses(data) == [COURSE]


def test_quiz_attempts_preserve_separate_zero_and_active_attempt_status() -> None:
    quiz = item(kind=ActivityKind.QUIZ, id=21, url=f"{EDERS_BASE_URL}/mod/quiz/view.php?id=21")
    result = parse_activity_details((FIXTURES / "quiz.html").read_text(encoding="utf-8"), quiz)
    assert len(result.attempts) == 2
    assert result.attempts[0].grade == "0.00" and result.attempts[0].grading == GradingStatus.GRADED
    assert result.attempts[1].grade is None and result.submission == SubmissionStatus.IN_PROGRESS
    data = snapshot([result], [grade()])
    assert deserialize_snapshot(serialize_snapshot(data)) == data


def test_snapshot_upgrade_has_no_grade_or_material_notification_flood() -> None:
    new = snapshot([item()], [grade()])
    old_json = json.loads(serialize_snapshot(new))
    for key in ("grades", "grades_observed", "catalog_observed", "courses"):
        old_json.pop(key)
    for value in old_json["activities"]:
        for key in ("section", "attempts", "quiz_result"):
            value.pop(key)
    old = deserialize_snapshot(json.dumps(old_json))
    assert not old.grades_observed and old.grades == ()
    assert plan_content_events(new, old, SETTINGS) == []
    assert plan_content_events(new, None, SETTINGS) == []
    assert plan_content_events(new, new, SETTINGS) == []


def test_grade_appearance_correction_removal_and_comment_only_change() -> None:
    empty = snapshot(grades=[grade(grade=None, feedback=None)])
    populated = snapshot(grades=[grade()], fetched_at=NOW + timedelta(minutes=30))
    events = plan_content_events(populated, empty, SETTINGS)
    assert len(events) == 1 and events[0].grade.grade == "0"
    for changed in [grade(grade="95"), grade(feedback="Revised"), grade(grade=None)]:
        events = plan_content_events(snapshot(grades=[changed]), populated, SETTINGS)
        assert len(events) == 1 and events[0].previous_grade == grade()
    hidden = grade(grade=None, feedback=None, visible_fields=())
    assert plan_content_events(snapshot(grades=[hidden]), populated, SETTINGS) == []
    assert plan_content_events(populated, empty, replace(SETTINGS, grade_changes=False)) == []


def test_materials_detect_new_renamed_and_moved_items_but_not_unchanged_content() -> None:
    old = snapshot([item()])
    for changed in (item(name="Renamed"), item(section="Week 2")):
        events = plan_content_events(snapshot([changed]), old, SETTINGS)
        assert [e.event_type for e in events] == ["material_changed"]
    new = snapshot([item(), item(id=23, kind=ActivityKind.QUIZ)], fetched_at=NOW + timedelta(minutes=30))
    assert [e.event_type for e in plan_content_events(new, old, SETTINGS)] == ["material_new"]
    assert plan_content_events(new, old, replace(SETTINGS, new_materials=False)) == []


def test_submission_filters_distinguish_confirmed_states_from_drafts_and_unknown() -> None:
    statuses = [
        SubmissionStatus.NOT_SUBMITTED,
        SubmissionStatus.DRAFT,
        SubmissionStatus.IN_PROGRESS,
        SubmissionStatus.SUBMITTED,
        SubmissionStatus.UNKNOWN,
    ]
    work = tuple(
        item(id=index, kind=ActivityKind.ASSIGNMENT, submission=status) for index, status in enumerate(statuses)
    )
    assert len(filter_activities(work, DeadlineFilter.NOT_SUBMITTED, NOW)) == 3
    assert filter_activities(work, DeadlineFilter.SUBMITTED, NOW) == [work[3]]
    assert filter_activities(work, DeadlineFilter.UNKNOWN_STATUS, NOW) == [work[4]]
    assert filter_activities(work, DeadlineFilter.AWAITING_GRADE, NOW) == []
    waiting = replace(work[3], grading=GradingStatus.NOT_GRADED)
    graded = replace(work[3], grading=GradingStatus.GRADED)
    assert filter_activities((waiting, graded), DeadlineFilter.AWAITING_GRADE, NOW) == [waiting]
    assert filter_activities((waiting, graded), DeadlineFilter.GRADED, NOW) == [graded]


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
def test_catalog_and_notifications_are_localized_escaped_and_bounded(locale) -> None:
    data = snapshot(grades=[grade()])
    with i18n.context(), i18n.use_locale(locale):
        text = format_catalog_page(data.grades[0], grades=True, page=0, count=1, updated=NOW)
        assert "0" in text and "OBIS" in text and "eders" in text
        assert "&lt;test&gt;" in text and "eders.grade_" not in text
        huge = grade(name="<" * 5000, feedback="<" * 5000, grade="<" * 5000)
        events = plan_content_events(snapshot(grades=[huge]), snapshot(grades=[grade(feedback="<" * 5000)]), SETTINGS)
        assert len(format_eders_event(events[0])) < 4096
        assert len(format_catalog_page(huge, grades=True, page=0, count=1, updated=NOW)) < 4096
        assert len(format_activity_page([item(kind=ActivityKind.ASSIGNMENT)], 0)) < 4096
    assert find_grades(data, 10) == list(data.grades)
    assert find_grades(data, 11) == []
