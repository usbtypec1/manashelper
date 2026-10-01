from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from manashelper.localization.i18n import i18n
from manashelper.scraping import eders_client
from manashelper.scraping.eders_client import EdersClient, EdersFetchError, EdersSessionExpiredError
from manashelper.scraping.eders_parser import (
    EdersParseError,
    parse_account_timezone,
    parse_activity_details,
    parse_course_activities,
    parse_courses,
)
from manashelper.scraping.eders_urls import EDERS_BASE_URL, EdersUnsafeUrlError, safe_eders_url
from manashelper.scraping.obis_client import OBIS_BASE_URL
from manashelper.services.eders import filter_activities
from manashelper.services.eders_formatter import format_activity_page
from manashelper.services.eders_models import (
    ActivityDate,
    ActivityKind,
    DeadlineFilter,
    EdersActivity,
    EdersCourse,
    EdersSnapshot,
    GradingStatus,
    SubmissionStatus,
)
from manashelper.services.eders_serialization import deserialize_snapshot, serialize_snapshot
from manashelper.services.eders_tracking import EdersSettings, plan_events
from manashelper.services.schedule import ScheduleLessonModel
from manashelper.services.study_week import StudyWeek
from manashelper.services.study_week_formatter import format_study_week

FIXTURES = Path(__file__).parent / "fixtures/eders"
NOW = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
SETTINGS = EdersSettings(True, True, True, True, True)


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


def activity(**changes) -> EdersActivity:
    item = EdersActivity(
        20,
        EdersCourse(10, "Sample course"),
        ActivityKind.ASSIGNMENT,
        "Work",
        f"{EDERS_BASE_URL}/mod/assign/view.php?id=20",
        ActivityDate(NOW + timedelta(hours=1)),
        ActivityDate(NOW + timedelta(days=3)),
    )
    return replace(item, **changes)


def test_course_and_activity_links_are_deduplicated_and_canonical() -> None:
    courses = parse_courses(fixture("courses"))
    assert [item.id for item in courses] == [10, 11]
    items = parse_course_activities(fixture("course"), courses[0])
    assert [item.id for item in items] == [20, 21, 22]
    assert items[0].name == "Work 01.10.2026"
    assert items[0].url == f"{EDERS_BASE_URL}/mod/assign/view.php?id=20"
    assert items[0].submission == SubmissionStatus.UNKNOWN


@pytest.mark.parametrize(
    "href",
    [
        "http://eders.manas.edu.kg/mod/assign/view.php?id=1",
        "https://evil.example/mod/assign/view.php?id=1",
        "/mod/assign/view.php?id=1&sesskey=x",
        "/mod/assign/view.php?id=1&action=submit",
        "/mod/assign/view.php?id=1&id=2",
        "/mod/quiz/startattempt.php?id=1",
        "/mod/assign/view.php?id=0",
        "/mod/assign/view.php?id=1#fragment",
        "https://user@eders.manas.edu.kg/mod/assign/view.php?id=1",
    ],
)
def test_action_and_external_links_are_rejected(href: str) -> None:
    with pytest.raises(EdersUnsafeUrlError):
        safe_eders_url(href, {"/mod/assign/view.php", "/mod/quiz/view.php"})


@pytest.mark.parametrize(
    "html",
    [
        "<html></html>",
        '<main id="region-main"><input name="logintoken"></main>',
        '<main id="region-main"><div class="alert-danger">Error</div></main>',
    ],
)
def test_changed_markup_and_login_pages_are_not_empty_snapshots(html: str) -> None:
    with pytest.raises(EdersParseError):
        parse_courses(html)


def test_account_timezone_and_midnight_conversion_preserve_calendar_day() -> None:
    timezone = parse_account_timezone(fixture("profile"))
    assert timezone == ZoneInfo("Europe/Istanbul")
    item = parse_course_activities(fixture("course"), EdersCourse(10, "Course"), timezone)[0]
    item = parse_activity_details(fixture("assignment"), item, timezone)
    assert item.closes.instant.isoformat() == "2026-10-02T02:30:00+06:00"
    assert item.submission == SubmissionStatus.DRAFT
    assert item.grading == GradingStatus.NOT_GRADED
    assert item.title_date_mismatch


def test_unverified_timezone_and_source_conflict_remain_unknown() -> None:
    item = parse_course_activities(fixture("course"), EdersCourse(10, "Course"))[0]
    assert item.closes.instant is None
    assert "October 2026" in item.closes.source_text
    changed = fixture("assignment").replace("11:30 PM", "10:30 PM")
    item = parse_activity_details(changed, item)
    assert item.closes.conflict and item.closes.instant is None
    assert filter_activities((item,), DeadlineFilter.NEXT_SEVEN_DAYS, NOW) == []


def test_active_quiz_attempt_takes_precedence_over_finished_zero_grade() -> None:
    item = activity(kind=ActivityKind.QUIZ, id=21, url=f"{EDERS_BASE_URL}/mod/quiz/view.php?id=21")
    parsed = parse_activity_details(
        fixture("quiz"), replace(item, opens=ActivityDate(), closes=ActivityDate()), ZoneInfo("Europe/Istanbul")
    )
    assert parsed.submission == SubmissionStatus.IN_PROGRESS
    assert parsed.grading == GradingStatus.NOT_GRADED
    assert parsed.closes.instant.hour == 3
    assert parsed.closes.instant.day == 2


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("No attempt", SubmissionStatus.NOT_SUBMITTED),
        ("Nothing has been submitted for this assignment", SubmissionStatus.NOT_SUBMITTED),
        ("This assignment does not require you to submit anything online", SubmissionStatus.UNKNOWN),
    ],
)
def test_explicit_unsubmitted_status_does_not_confuse_offline_assignments(text, expected) -> None:
    html = fixture("assignment").replace('class="submissionstatusdraft"', "").replace("Draft (not submitted)", text)
    assert parse_activity_details(html, activity()).submission == expected


def test_ambiguous_dst_time_is_not_used_for_deadline_filters() -> None:
    html = fixture("assignment").replace("Thursday, 1 October 2026, 11:30 PM", "Sunday, 25 October 2026, 2:30 AM")
    result = parse_activity_details(
        html, replace(activity(), opens=ActivityDate(), closes=ActivityDate()), ZoneInfo("Europe/Berlin")
    )
    assert result.closes.instant is None


def test_filters_distinguish_waiting_grades_from_unknown_and_archive() -> None:
    submitted = activity(submission=SubmissionStatus.SUBMITTED, grading=GradingStatus.NOT_GRADED)
    unknown = activity(id=30, closes=ActivityDate(source_text="Unverified date"))
    archive = activity(id=40, closes=ActivityDate(NOW - timedelta(days=400)))
    current = activity(id=50, opens=ActivityDate(NOW - timedelta(days=1)))
    items = (submitted, unknown, archive, current)
    assert filter_activities(items, DeadlineFilter.AWAITING_GRADE, NOW) == [submitted]
    assert filter_activities(items, DeadlineFilter.AVAILABLE, NOW) == [current]
    assert filter_activities(items, DeadlineFilter.UNKNOWN_DEADLINE, NOW) == [unknown]
    assert archive not in filter_activities(items, DeadlineFilter.ALL, NOW)
    assert archive in filter_activities(items, DeadlineFilter.ALL, NOW, False)


def test_baseline_never_backfills_old_events_but_schedules_future_reminders() -> None:
    old = activity(id=30, opens=ActivityDate(NOW - timedelta(days=300)), closes=ActivityDate(NOW - timedelta(days=200)))
    urgent = activity(
        id=40, opens=ActivityDate(NOW - timedelta(hours=1)), closes=ActivityDate(NOW + timedelta(hours=1))
    )
    snapshot = EdersSnapshot((old, urgent, activity()), NOW)
    events = plan_events(snapshot, None, SETTINGS)
    assert {event.activity.id for event in events} == {20}
    assert {event.event_type for event in events} == {"opened", "before_24", "before_2"}
    after = replace(snapshot, fetched_at=NOW + timedelta(minutes=30))
    assert all(event.activity.id != 40 for event in plan_events(after, snapshot, SETTINGS))


def test_deadline_change_reschedules_and_submission_suppresses_reminders() -> None:
    previous = EdersSnapshot((activity(),), NOW)
    moved = activity(closes=ActivityDate(NOW + timedelta(days=4)), submission=SubmissionStatus.SUBMITTED)
    events = plan_events(EdersSnapshot((moved,), NOW + timedelta(minutes=30)), previous, SETTINGS)
    assert len(events) == 1 and events[0].event_type == "changed"
    assert events[0].previous_deadline == previous.activities[0].closes.instant
    assert plan_events(EdersSnapshot((moved,), NOW), None, SETTINGS) == []


def test_serialization_and_html_formatting_keep_only_public_activity_urls() -> None:
    item = activity(name="<tag> & work", course=EdersCourse(10, "Course & <x>"))
    snapshot = EdersSnapshot((item,), NOW)
    assert deserialize_snapshot(serialize_snapshot(snapshot)) == snapshot
    with i18n.context(), i18n.use_locale("en"):
        text = format_activity_page([item], 0)
    assert "&lt;tag&gt; &amp; work" in text and "Course &amp; &lt;x&gt;" in text
    assert len(text) < 4096


def test_week_combines_classes_opens_deadlines_and_new_materials() -> None:
    item = activity(opens=ActivityDate(NOW), closes=ActivityDate(NOW))
    reading = activity(
        id=22, kind=ActivityKind.RESOURCE, name="Reading", first_seen=NOW, opens=ActivityDate(), closes=ActivityDate()
    )
    week = StudyWeek(
        NOW.date(),
        (ScheduleLessonModel(4, "9:00-9:50", "Class <x>"),),
        EdersSnapshot((item, replace(item, id=21), reading), NOW),
        True,
    )
    with i18n.context(), i18n.use_locale("en"):
        chunks = format_study_week(week)
    text = "\n".join(chunks)
    assert "Class &lt;x&gt;" in text and "Opens:" in text and "Deadline:" in text
    assert "Deadlines today: 2" in text and "Newly discovered material:" in text
    assert all(len(chunk) <= 3500 for chunk in chunks)


async def test_client_authenticates_once_and_retries_expired_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = []
    clients = []
    expired = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal expired
        requests.append(request)
        path = request.url.path
        if path == "/site/login":
            if request.method == "GET":
                return httpx.Response(200, text='<form><input name="_csrf" value="test"></form>')
            return httpx.Response(302, headers={"location": "/"})
        if request.url.host == "obistest.manas.edu.kg" and path == "/":
            return httpx.Response(200, text="Logged in")
        if path == "/site/eders":
            return httpx.Response(302, headers={"location": f"{EDERS_BASE_URL}/auth/userkey/login.php?key=fake-secret"})
        if path == "/auth/userkey/login.php":
            return httpx.Response(303, headers={"location": "/my/"})
        if path == "/my/":
            return httpx.Response(200, text="Welcome")
        if path == "/user/profile.php":
            return httpx.Response(200, text=fixture("profile"))
        if path == "/grade/report/overview/index.php":
            if not expired:
                expired = True
                return httpx.Response(302, headers={"location": "/login/index.php"})
            return httpx.Response(200, text=fixture("courses"))
        if path == "/course/view.php":
            return httpx.Response(
                200,
                text=fixture("course")
                if request.url.params["id"] == "10"
                else '<main id="region-main"><div class="course-content"></div></main>',
            )
        if path == "/mod/assign/view.php":
            return httpx.Response(200, text=fixture("assignment"))
        if path == "/mod/quiz/view.php":
            return httpx.Response(200, text=fixture("quiz"))
        raise AssertionError(f"Unexpected request: {request.method} {path}")

    def factory():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        clients.append(client)
        return client

    monkeypatch.setattr(eders_client, "_new_http_client", factory)
    result = await EdersClient().fetch_snapshot("fake-student", "fake-password")
    assert len(result.activities) == 3
    assert all(client.is_closed for client in clients)
    assert len(clients) == 2
    assert all(
        str(request.url).startswith(f"{OBIS_BASE_URL}/site/login") for request in requests if request.method == "POST"
    )
    assert "fake-secret" not in serialize_snapshot(result)
    assert not any(request.url.path == "/login/index.php" for request in requests)


async def test_redirect_allowlist_blocks_actions_before_request_and_hides_secrets() -> None:
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(302, headers={"location": f"{EDERS_BASE_URL}/mod/assign/view.php?id=1&action=submit"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EdersUnsafeUrlError):
            await eders_client._request(client, f"{OBIS_BASE_URL}/site/eders", "sso")
    assert paths == ["/site/eders"]

    def failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"URL contains fake-secret: {request.url}", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(failure)) as client:
        with pytest.raises(EdersFetchError) as error:
            await eders_client._request(client, f"{EDERS_BASE_URL}/auth/userkey/login.php?key=fake-secret", "sso")
    assert "fake-secret" not in str(error.value) and error.value.__suppress_context__


async def test_persistent_session_expiry_stops_after_one_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    authenticate = []

    async def login(client, student, password):
        authenticate.append(student)

    def handler(request):
        return httpx.Response(200, text='<input name="logintoken">')

    monkeypatch.setattr(eders_client, "_authenticate", login)
    monkeypatch.setattr(
        eders_client, "_new_http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(EdersSessionExpiredError):
        await EdersClient().fetch_snapshot("fake-student", "fake-password")
    assert authenticate == ["fake-student", "fake-student"]
