from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import User
from manashelper.repositories.eders_repository import EdersRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.eders import EdersService
from manashelper.services.eders_catalog import find_grades
from manashelper.services.eders_models import (
    ActivityDate,
    ActivityKind,
    EdersActivity,
    EdersCourse,
    EdersGrade,
    EdersSnapshot,
    SubmissionStatus,
)
from manashelper.services.eders_tracking import EdersSetting, EdersTrackingService
from manashelper.services.obis import UserHasNoCredentialsError

NOW = datetime(2026, 10, 1, tzinfo=UTC)


@pytest.fixture
async def tracking(session: AsyncSession):
    session.add(User(id=980_001, full_name="Test", username=None))
    await session.flush()
    return EdersTrackingService(EdersRepository(session), UserRepository(session))


def item(**changes):
    return replace(
        EdersActivity(
            20,
            EdersCourse(10, "Course"),
            ActivityKind.ASSIGNMENT,
            "Work",
            "https://eders.manas.edu.kg/mod/assign/view.php?id=20",
            opens=ActivityDate(NOW + timedelta(days=1)),
            closes=ActivityDate(NOW + timedelta(days=3)),
        ),
        **changes,
    )


async def test_baseline_delivery_is_deduplicated_and_failed_delivery_remains_pending(tracking):
    baseline = EdersSnapshot((item(),), NOW)
    await tracking.observe(980_001, "account-a", baseline)
    assert await tracking.pending_events(980_001, NOW) == []
    crossing = replace(baseline, fetched_at=NOW + timedelta(days=2, minutes=15))
    await tracking.observe(980_001, "account-a", crossing)
    events = await tracking.pending_events(980_001, crossing.fetched_at)
    assert [event.event_type for event in events] == ["before_24"]
    # No success acknowledgement: a later observation must preserve the same event.
    later = replace(crossing, fetched_at=crossing.fetched_at + timedelta(minutes=30))
    await tracking.observe(980_001, "account-a", later)
    retry = await tracking.pending_events(980_001, later.fetched_at)
    assert [event.key for event in retry] == [event.key for event in events]
    await tracking.mark_sent(980_001, retry[0].key, later.fetched_at)
    await tracking.observe(980_001, "account-a", replace(later, fetched_at=later.fetched_at + timedelta(minutes=30)))
    assert await tracking.pending_events(980_001, later.fetched_at + timedelta(minutes=30)) == []


async def test_submission_cancels_pending_openings_and_reminders(tracking):
    await tracking.observe(980_001, "a", EdersSnapshot((item(),), NOW))
    submitted = item(submission=SubmissionStatus.SUBMITTED)
    await tracking.observe(980_001, "a", EdersSnapshot((submitted,), NOW + timedelta(hours=1)))
    assert await tracking.pending_events(980_001, NOW + timedelta(days=2)) == []


async def test_changed_deadline_cancels_old_schedule_and_records_old_and_new(tracking):
    await tracking.observe(980_001, "a", EdersSnapshot((item(),), NOW))
    moved = item(closes=ActivityDate(NOW + timedelta(days=5)))
    updated = EdersSnapshot((moved,), NOW + timedelta(hours=1))
    await tracking.observe(980_001, "a", updated)
    events = await tracking.pending_events(980_001, updated.fetched_at)
    assert [event.event_type for event in events] == ["changed"]
    assert events[0].previous_deadline == NOW + timedelta(days=3)
    assert events[0].event_time == NOW + timedelta(days=5)
    await tracking.mark_sent(980_001, events[0].key, updated.fetched_at)
    await tracking.observe(980_001, "a", replace(updated, fetched_at=NOW + timedelta(days=2)))
    assert all(
        event.event_type != "before_24" for event in await tracking.pending_events(980_001, NOW + timedelta(days=2))
    )


async def test_settings_persist_and_disabled_events_are_cancelled(tracking):
    assert (await tracking.get_settings(980_001)).day_before
    await tracking.observe(980_001, "a", EdersSnapshot((item(),), NOW))
    await tracking.toggle(980_001, EdersSetting.DAY_BEFORE)
    assert not (await tracking.get_settings(980_001)).day_before
    await tracking.observe(980_001, "a", EdersSnapshot((item(),), NOW + timedelta(hours=1)))
    assert all(
        event.event_type != "before_24" for event in await tracking.pending_events(980_001, NOW + timedelta(days=2))
    )


async def test_material_discovery_and_account_change_reset_baseline(tracking):
    baseline = EdersSnapshot((item(),), NOW)
    await tracking.observe(980_001, "a", baseline)
    reading = item(id=22, kind=ActivityKind.RESOURCE, opens=ActivityDate(), closes=ActivityDate())
    current = EdersSnapshot((item(), reading), NOW + timedelta(minutes=30))
    discovered = await tracking.observe(980_001, "a", current)
    assert discovered.activities[0].first_seen is None
    assert discovered.activities[1].first_seen == current.fetched_at
    reset = await tracking.observe(980_001, "b", replace(current, fetched_at=NOW + timedelta(hours=1)))
    assert all(activity.first_seen is None for activity in reset.activities)
    assert await tracking.pending_events(980_001, reset.fetched_at) == []


async def test_deleted_activity_and_conflicting_deadline_cancel_reminders(tracking):
    await tracking.observe(980_001, "a", EdersSnapshot((item(),), NOW))
    conflicted = item(closes=ActivityDate(source_text="Two conflicting dates", conflict=True))
    await tracking.observe(980_001, "a", EdersSnapshot((conflicted,), NOW + timedelta(hours=1)))
    due = await tracking.pending_events(980_001, NOW + timedelta(days=2, hours=23))
    assert all(not event.event_type.startswith("before_") for event in due)
    await tracking.observe(980_001, "a", EdersSnapshot((), NOW + timedelta(days=3)))
    assert await tracking.pending_events(980_001, NOW + timedelta(days=3)) == []


async def test_after_outage_only_nearest_deadline_reminder_is_sent(tracking):
    await tracking.observe(980_001, "a", EdersSnapshot((item(),), NOW))
    current = EdersSnapshot((item(),), NOW + timedelta(days=2, hours=23))
    await tracking.observe(980_001, "a", current)
    events = await tracking.pending_events(980_001, current.fetched_at)
    assert [event.event_type for event in events] == ["before_2"]
    await tracking.mark_sent(980_001, events[0].key, current.fetched_at)
    await tracking.observe(980_001, "a", replace(current, fetched_at=current.fetched_at + timedelta(minutes=30)))
    assert await tracking.pending_events(980_001, current.fetched_at + timedelta(minutes=30)) == []


async def test_missing_credentials_do_not_make_network_requests(session, tracking):
    client, crypto = AsyncMock(), AsyncMock()
    service = EdersService(UserRepository(session), client, crypto, tracking)
    with pytest.raises(UserHasNoCredentialsError):
        await service.get_snapshot(980_001)
    client.fetch_snapshot.assert_not_awaited()


async def test_repeated_deadline_change_is_a_new_notification(tracking):
    initial, moved = item(), item(closes=ActivityDate(NOW + timedelta(days=5)))
    await tracking.observe(980_001, "a", EdersSnapshot((initial,), NOW))
    for minute, activity in ((30, moved), (60, initial), (90, moved)):
        observed = NOW + timedelta(minutes=minute)
        await tracking.observe(980_001, "a", EdersSnapshot((activity,), observed))
        events = await tracking.pending_events(980_001, observed)
        assert len(events) == 1 and events[0].event_type == "changed"
        await tracking.mark_sent(980_001, events[0].key, observed)


def grade(**changes):
    return replace(
        EdersGrade(
            301,
            EdersCourse(10, "Course"),
            "Work",
            "https://eders.manas.edu.kg/mod/assign/view.php?id=20",
            grade="0",
            feedback="Good",
            visible_fields=("grade", "feedback"),
        ),
        **changes,
    )


def content_snapshot(activities=(), grades=(), minutes=0):
    return EdersSnapshot(tuple(activities), NOW + timedelta(minutes=minutes), tuple(grades), True, True)


async def test_material_and_grade_delivery_retry_survives_observation_and_is_deduplicated(tracking):
    reading = item(id=22, kind=ActivityKind.RESOURCE, opens=ActivityDate(), closes=ActivityDate())
    await tracking.observe(980_001, "a", content_snapshot([reading], [grade(grade=None, feedback=None)]))
    assert await tracking.pending_events(980_001, NOW) == []
    current = content_snapshot([reading, replace(reading, id=23)], [grade()], 30)
    await tracking.observe(980_001, "a", current)
    events = await tracking.pending_events(980_001, current.fetched_at)
    assert {event.event_type for event in events} == {"material_new", "grade_changed"}
    grade_event = next(event for event in events if event.grade)
    assert grade_event.grade.grade == "0" and grade_event.previous_grade.grade is None
    later = replace(current, fetched_at=current.fetched_at + timedelta(days=5))
    await tracking.observe(980_001, "a", later)
    retry = await tracking.pending_events(980_001, later.fetched_at)
    assert {event.key for event in retry} == {event.key for event in events}
    for event in retry:
        await tracking.mark_sent(980_001, event.key, later.fetched_at)
    await tracking.observe(980_001, "a", replace(later, fetched_at=later.fetched_at + timedelta(minutes=30)))
    assert await tracking.pending_events(980_001, later.fetched_at + timedelta(minutes=30)) == []


async def test_superseded_grade_cancels_old_retry_and_repeated_corrections_are_distinct(tracking):
    await tracking.observe(980_001, "a", content_snapshot(grades=[grade()]))
    keys = set()
    for minute, value in ((30, "90"), (60, "0"), (90, "90")):
        current = content_snapshot(grades=[grade(grade=value)], minutes=minute)
        await tracking.observe(980_001, "a", current)
        events = await tracking.pending_events(980_001, current.fetched_at)
        assert len(events) == 1 and events[0].grade.grade == value
        assert events[0].key not in keys
        keys.add(events[0].key)
    await tracking.mark_sent(980_001, events[0].key, current.fetched_at)
    assert await tracking.pending_events(980_001, current.fetched_at) == []


async def test_content_settings_cancel_pending_events_and_do_not_backfill_when_enabled(tracking):
    await tracking.observe(980_001, "a", content_snapshot(grades=[grade()]))
    current = content_snapshot([item(kind=ActivityKind.RESOURCE)], [grade(feedback="Changed")], 30)
    await tracking.observe(980_001, "a", current)
    assert len(await tracking.pending_events(980_001, current.fetched_at)) == 2
    await tracking.toggle(980_001, EdersSetting.NEW_MATERIALS)
    await tracking.toggle(980_001, EdersSetting.GRADE_CHANGES)
    assert await tracking.pending_events(980_001, current.fetched_at) == []
    await tracking.toggle(980_001, EdersSetting.NEW_MATERIALS)
    await tracking.toggle(980_001, EdersSetting.GRADE_CHANGES)
    await tracking.observe(980_001, "a", replace(current, fetched_at=current.fetched_at + timedelta(minutes=30)))
    assert await tracking.pending_events(980_001, current.fetched_at + timedelta(minutes=30)) == []


async def test_new_account_resets_grade_and_material_baselines_and_cancels_old_queue(tracking):
    await tracking.observe(980_001, "a", content_snapshot(grades=[grade()]))
    current = content_snapshot([item(kind=ActivityKind.RESOURCE)], [grade(grade="90")], 30)
    await tracking.observe(980_001, "a", current)
    assert len(await tracking.pending_events(980_001, current.fetched_at)) == 2
    await tracking.observe(980_001, "b", replace(current, fetched_at=current.fetched_at + timedelta(minutes=30)))
    assert await tracking.pending_events(980_001, current.fetched_at + timedelta(minutes=30)) == []


async def test_deadline_shortened_into_past_notifies_and_cancels_reminders(tracking):
    await tracking.observe(980_001, "a", EdersSnapshot((item(),), NOW))
    closed = item(closes=ActivityDate(NOW + timedelta(minutes=15)))
    current = EdersSnapshot((closed,), NOW + timedelta(minutes=30))
    await tracking.observe(980_001, "a", current)
    events = await tracking.pending_events(980_001, current.fetched_at)
    assert len(events) == 1 and events[0].event_type == "changed"
    assert events[0].previous_deadline == item().closes.instant


async def test_grade_permission_loss_preserves_baseline_and_pauses_retry_until_restored(tracking):
    await tracking.observe(980_001, "a", content_snapshot(grades=[grade()]))
    current = content_snapshot(grades=[grade(grade="90")], minutes=30)
    await tracking.observe(980_001, "a", current)
    event = (await tracking.pending_events(980_001, current.fetched_at))[0]
    hidden = replace(content_snapshot(minutes=60), unavailable_grade_courses=(10,))
    observed = await tracking.observe(980_001, "a", hidden)
    assert observed.grades == current.grades and find_grades(observed) == []
    assert await tracking.pending_events(980_001, hidden.fetched_at) == []
    restored = replace(current, fetched_at=NOW + timedelta(minutes=90))
    await tracking.observe(980_001, "a", restored)
    pending = await tracking.pending_events(980_001, restored.fetched_at)
    assert len(pending) == 1 and pending[0].key == event.key


async def test_first_available_grade_report_after_permission_failure_only_establishes_baseline(tracking):
    await tracking.observe(980_001, "a", replace(content_snapshot(), unavailable_grade_courses=(10,)))
    restored = content_snapshot(grades=[grade()], minutes=30)
    await tracking.observe(980_001, "a", restored)
    assert await tracking.pending_events(980_001, restored.fetched_at) == []
    current = content_snapshot(grades=[grade(grade="95")], minutes=60)
    await tracking.observe(980_001, "a", current)
    assert len(await tracking.pending_events(980_001, current.fetched_at)) == 1
