import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_eders_tracking import NOW, item

from manashelper.db.models import User
from manashelper.modules.eders.application.eders import filter_activities
from manashelper.modules.eders.application.models import ActivityKind, DeadlineFilter, EdersCourse, EdersSnapshot
from manashelper.modules.eders.application.tracking import EdersEvent, EdersSetting, EdersTrackingService
from manashelper.modules.eders.errors import EdersParseError
from manashelper.modules.eders.infrastructure.parser import parse_course_activities, parse_enrolled_courses
from manashelper.modules.eders.infrastructure.repository import EdersRepository
from manashelper.modules.eders.infrastructure.serialization import deserialize_snapshot, serialize_snapshot
from manashelper.modules.eders.presentation.formatter import format_material_events
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.i18n.catalog import i18n


@pytest.fixture
async def tracking(session):
    session.add(User(id=980_001, full_name="Test", username=None))
    await session.flush()
    return EdersTrackingService(EdersRepository(session), UsersQuery(UserRepository(session)))


async def test_new_material_is_pending_until_sent_and_not_repeated(tracking):
    await tracking.observe(980_001, "a", EdersSnapshot((item(),), NOW))
    resource = item(id=22, kind=ActivityKind.FOLDER)
    snapshot = EdersSnapshot((item(), resource), NOW + timedelta(minutes=30))
    await tracking.observe(980_001, "a", snapshot)
    first = await tracking.pending_events(980_001, snapshot.fetched_at)
    assert [event.event_type for event in first] == ["material_new"]
    later = replace(snapshot, fetched_at=NOW + timedelta(hours=1))
    await tracking.observe(980_001, "a", later)
    assert [event.key for event in await tracking.pending_events(980_001, later.fetched_at)] == [first[0].key]
    await tracking.mark_sent(980_001, first[0].key, later.fetched_at)
    await tracking.observe(980_001, "a", replace(later, fetched_at=NOW + timedelta(hours=2)))
    assert await tracking.pending_events(980_001, later.fetched_at) == []


async def test_new_course_and_legacy_snapshot_are_silent_baselines(tracking):
    await tracking.observe(980_001, "a", EdersSnapshot((item(),), NOW, schema_version=1))
    resource = item(id=22, kind=ActivityKind.FOLDER)
    await tracking.observe(980_001, "a", EdersSnapshot((item(), resource), NOW + timedelta(minutes=30)))
    assert await tracking.pending_events(980_001, NOW + timedelta(minutes=30)) == []
    other = item(id=99, kind=ActivityKind.RESOURCE, course=EdersCourse(99, "Other"))
    result = await tracking.observe(980_001, "a", EdersSnapshot((item(), resource, other), NOW + timedelta(hours=1)))
    assert result.activities[-1].first_seen is None
    assert await tracking.pending_events(980_001, NOW + timedelta(hours=1)) == []


async def test_empty_known_course_detects_first_material_and_toggle_cancels(tracking):
    course = EdersCourse(10, "Course")
    await tracking.observe(980_001, "a", EdersSnapshot((), NOW, courses=(course,)))
    snapshot = EdersSnapshot((item(kind=ActivityKind.RESOURCE),), NOW + timedelta(minutes=30), courses=(course,))
    await tracking.observe(980_001, "a", snapshot)
    assert len(await tracking.pending_events(980_001, snapshot.fetched_at)) == 1
    await tracking.toggle(980_001, EdersSetting.NEW_MATERIALS)
    assert await tracking.pending_events(980_001, snapshot.fetched_at) == []


async def test_text_changes_notify_but_reordering_and_section_move_do_not(tracking):
    resource = item(kind=ActivityKind.LABEL, description="Reading")
    await tracking.observe(980_001, "a", EdersSnapshot((resource,), NOW))
    moved = replace(resource, section="Week 2")
    await tracking.observe(980_001, "a", EdersSnapshot((moved,), NOW + timedelta(minutes=30)))
    assert await tracking.pending_events(980_001, NOW + timedelta(minutes=30)) == []
    changed = replace(moved, description="Updated reading")
    await tracking.observe(980_001, "a", EdersSnapshot((changed,), NOW + timedelta(hours=1)))
    events = await tracking.pending_events(980_001, NOW + timedelta(hours=1))
    assert [event.event_type for event in events] == ["material_changed"]


def test_material_messages_group_by_course_split_safely_and_escape_html():
    events = [
        EdersEvent(str(n), item(id=n, name="<file>" * 50, section="A&B"), "material_new", NOW, NOW) for n in range(30)
    ]
    with i18n.context(), i18n.use_locale("en"):
        messages = format_material_events(events)
    assert len(messages) > 1
    assert [event.key for _, batch in messages for event in batch] == [event.key for event in events]
    assert all(len(text) <= 3500 and "&lt;file&gt;" in text and "A&amp;B" in text for text, _ in messages)


def test_snapshot_backward_compatibility_and_material_filters():
    material = item(kind=ActivityKind.RESOURCE, first_seen=NOW, section="Week 1", description="Read")
    snapshot = EdersSnapshot((item(), material), NOW)
    assert deserialize_snapshot(serialize_snapshot(snapshot)) == snapshot
    old = json.loads(serialize_snapshot(snapshot))
    for key in ("schema_version", "courses"):
        old.pop(key)
    for entry in old["activities"]:
        entry.pop("section")
        entry.pop("description")
    assert deserialize_snapshot(json.dumps(old)).schema_version == 1
    assert filter_activities(snapshot.activities, DeadlineFilter.NEW_MATERIALS, NOW) == [material]
    assert len(filter_activities(snapshot.activities, DeadlineFilter.MATERIALS, NOW)) == 2


@pytest.mark.parametrize(
    "payload",
    [None, {}, [], [{"error": True}], [{"data": {}}], [{"data": {"courses": [{"id": -1, "fullname": "Bad"}]}}]],
)
def test_invalid_ajax_never_becomes_empty_snapshot(payload):
    with pytest.raises(EdersParseError):
        parse_enrolled_courses(payload)


def test_ajax_course_names_and_pagination():
    courses, offset = parse_enrolled_courses(
        [{"data": {"courses": [{"id": 10, "fullname": "Course"}], "nextoffset": 1}}]
    )
    assert courses == [EdersCourse(10, "Course")] and offset == 1


def test_actual_theme_turkish_dates_labels_and_folders():
    html = (Path(__file__).parent / "fixtures/eders/actual-theme.html").read_text()
    items = parse_course_activities(html, EdersCourse(10, "Course"))
    assert {entry.kind for entry in items} == {ActivityKind.ASSIGNMENT, ActivityKind.LABEL, ActivityKind.FOLDER}
    assignment = next(entry for entry in items if entry.kind == ActivityKind.ASSIGNMENT)
    assert assignment.closes.instant == datetime(2026, 10, 2, 1, tzinfo=assignment.closes.instant.tzinfo)
    assert assignment.section == "Week 1"
    assert all("fake" not in entry.url for entry in items)
    assert next(entry for entry in items if entry.kind == ActivityKind.LABEL).description == "Reading & notes"
    unknown = parse_course_activities(html.replace('"usertimezone":"Asia\\/Bishkek"', ""), EdersCourse(10, "Course"))
    assert all(entry.closes.instant is None for entry in unknown)


def test_today_uses_bishkek_date_and_unsubmitted_excludes_unknown():
    from manashelper.modules.eders.application.models import ActivityDate, SubmissionStatus

    now = datetime(2026, 10, 1, 20, tzinfo=UTC)  # Already October 2 in Bishkek.
    due = item(closes=ActivityDate(datetime(2026, 10, 1, 23, tzinfo=UTC)), submission=SubmissionStatus.DRAFT)
    tomorrow = item(id=21, closes=ActivityDate(datetime(2026, 10, 2, 23, tzinfo=UTC)))
    assert filter_activities((due, tomorrow), DeadlineFilter.TODAY, now) == [due]
    assert filter_activities((due, tomorrow), DeadlineFilter.NOT_SUBMITTED, now) == [due]


def test_activity_details_effective_timezone_overrides_profile_fallback():
    from zoneinfo import ZoneInfo

    from manashelper.modules.eders.infrastructure.parser import parse_activity_details

    html = """<html><head><script>M.cfg={"usertimezone":"Asia/Bishkek"}</script></head>
    <body id="page-mod-assign-view"><main id="region-main"><div data-region="activity-dates">
    <div><strong>Due:</strong> Friday, 2 October 2026, 1:00 AM</div></div></main></body></html>"""
    from manashelper.modules.eders.application.models import ActivityDate

    result = parse_activity_details(html, item(closes=ActivityDate()), ZoneInfo("Europe/Istanbul"))
    assert result.closes.instant.hour == 1
    assert not result.closes.conflict
