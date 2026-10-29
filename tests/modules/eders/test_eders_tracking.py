from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from manashelper.modules.eders.application.eders import EdersService
from manashelper.modules.eders.application.models import (
    ActivityDate,
    ActivityKind,
    EdersSnapshot,
    SubmissionStatus,
)
from manashelper.modules.eders.application.tracking import EdersSetting
from manashelper.modules.eders.infrastructure.repository import EdersRepository
from manashelper.modules.obis.errors import UserHasNoCredentialsError
from manashelper.modules.users.infrastructure.user import User
from tests.modules.eders.factories import NOW, item


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
    from manashelper.modules.obis.application.credentials import ObisCredentialsService
    from manashelper.modules.obis.infrastructure.credentials_repository import ObisCredentialsRepository

    account = ObisCredentialsService(ObisCredentialsRepository(session), AsyncMock(), crypto)
    service = EdersService(account, client, tracking)
    with pytest.raises(UserHasNoCredentialsError):
        await service.get_snapshot(980_001)
    client.fetch_snapshot.assert_not_awaited()


@pytest.mark.parametrize("encrypted_password", [None, "bad-ciphertext"])
async def test_eders_needs_only_student_number_and_polling_includes_it(session, tracking, encrypted_password):
    from manashelper.modules.obis.application.credentials import ObisCredentialsService
    from manashelper.modules.obis.infrastructure.credentials_repository import ObisCredentialsRepository

    user = await session.get(User, 980_001)
    user.student_number = "fake-student"
    user.encrypted_password = encrypted_password
    await session.flush()
    client, crypto = AsyncMock(), AsyncMock()
    client.fetch_snapshot.return_value = EdersSnapshot((item(),), NOW)
    account = ObisCredentialsService(ObisCredentialsRepository(session), AsyncMock(), crypto)
    result = await EdersService(account, client, tracking).get_snapshot(user.id)
    assert result.activities[0].id == 20
    client.fetch_snapshot.assert_awaited_once_with("fake-student")
    crypto.decrypt.assert_not_called()
    assert user.id in await EdersRepository(session).get_poll_user_ids()


async def test_repeated_deadline_change_is_a_new_notification(tracking):
    initial, moved = item(), item(closes=ActivityDate(NOW + timedelta(days=5)))
    await tracking.observe(980_001, "a", EdersSnapshot((initial,), NOW))
    for minute, activity in ((30, moved), (60, initial), (90, moved)):
        observed = NOW + timedelta(minutes=minute)
        await tracking.observe(980_001, "a", EdersSnapshot((activity,), observed))
        events = await tracking.pending_events(980_001, observed)
        assert len(events) == 1 and events[0].event_type == "changed"
        await tracking.mark_sent(980_001, events[0].key, observed)


@pytest.mark.parametrize("delta", [timedelta(), timedelta(minutes=-1)])
async def test_older_or_equal_snapshot_cannot_replace_persisted_observation(tracking, delta):
    baseline = EdersSnapshot((item(),), NOW)
    stored = await tracking.observe(980_001, "a", baseline)
    incoming = EdersSnapshot((), NOW + delta)
    assert await tracking.observe(980_001, "a", incoming) == stored
    assert await tracking.pending_events(980_001, NOW) == []
