import hashlib
from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from manashelper.modules.eders.application.eders import EdersService
from manashelper.modules.eders.application.models import EdersSnapshot
from manashelper.modules.eders.errors import EdersFetchError, EdersLoginError, EdersSnapshotNotReadyError
from manashelper.modules.eders.infrastructure.orm import EdersState
from manashelper.modules.obis.application.credentials import ObisCredentials
from manashelper.modules.obis.errors import UserHasNoCredentialsError
from manashelper.modules.users.infrastructure.user import User
from tests.modules.eders.factories import NOW, item


async def test_eders_cache_miss_never_fetches_and_empty_snapshot_is_ready(tracking):
    credentials, client = AsyncMock(), AsyncMock()
    credentials.get_student_number.return_value = "student"
    service = EdersService(credentials, client, tracking)
    with pytest.raises(EdersSnapshotNotReadyError):
        await service.get_snapshot(980_001)
    client.fetch_snapshot.assert_not_awaited()
    client.fetch_snapshot.return_value = EdersSnapshot((), NOW)
    result = await service.refresh_snapshot(980_001)
    client.reset_mock()
    assert await service.get_snapshot(980_001) == result
    client.fetch_snapshot.assert_not_awaited()


async def test_eders_reads_last_success_even_when_old_or_upstream_is_down(tracking):
    credentials, client = AsyncMock(), AsyncMock()
    credentials.get_student_number.return_value = "student"
    service = EdersService(credentials, client, tracking)
    client.fetch_snapshot.return_value = EdersSnapshot((item(),), NOW - timedelta(days=1))
    previous = await service.refresh_snapshot(980_001)
    client.fetch_snapshot.side_effect = EdersFetchError("unavailable")
    with pytest.raises(EdersFetchError):
        await service.refresh_snapshot(980_001)
    assert await service.get_snapshot(980_001) == previous


async def test_eders_account_change_hides_previous_snapshot_and_rebaselines(tracking):
    credentials, client = AsyncMock(), AsyncMock()
    credentials.get_student_number.return_value = "student-a"
    client.fetch_snapshot.return_value = EdersSnapshot((item(),), NOW)
    service = EdersService(credentials, client, tracking)
    await service.refresh_snapshot(980_001)
    credentials.get_student_number.return_value = "student-b"
    with pytest.raises(EdersSnapshotNotReadyError):
        await service.get_snapshot(980_001)
    client.fetch_snapshot.return_value = replace(
        client.fetch_snapshot.return_value, fetched_at=NOW + timedelta(minutes=15)
    )
    await service.refresh_snapshot(980_001)
    assert await tracking.pending_events(980_001, NOW + timedelta(minutes=15)) == []


async def test_missing_eders_settings_are_read_without_creating_locked_state(session, tracking):
    from manashelper.modules.eders.infrastructure.orm import EdersState

    assert (await tracking.get_settings(980_001)).day_before
    assert await session.get(EdersState, 980_001) is None
    user = await session.get(User, 980_001)
    user.student_number = "student"
    await tracking.observe(user.id, hashlib.sha256(b"student").hexdigest(), EdersSnapshot((), NOW))
    assert await tracking.get_snapshot(user.id, hashlib.sha256(b"student").hexdigest()) == EdersSnapshot((), NOW)


@pytest.mark.parametrize("failure", [None, EdersFetchError("read failed")])
async def test_direct_login_does_not_decrypt_obis_password(tracking, failure):
    credentials, client = AsyncMock(), AsyncMock()
    credentials.get_student_number.return_value = "student"
    client.fetch_snapshot.return_value = EdersSnapshot((), NOW)
    client.fetch_snapshot.side_effect = failure
    service = EdersService(credentials, client, tracking)
    if failure:
        with pytest.raises(EdersFetchError, match="read failed"):
            await service.refresh_snapshot(980_001)
    else:
        await service.refresh_snapshot(980_001)
    credentials.get_credentials.assert_not_awaited()
    client.fetch_snapshot.assert_awaited_once_with("student")


@pytest.mark.parametrize("failure", [None, EdersFetchError("OBIS unavailable"), UserHasNoCredentialsError(980_001)])
async def test_only_login_failure_uses_obis_fallback_and_preserves_cached_snapshot(session, tracking, failure):
    credentials, client = AsyncMock(), AsyncMock()
    credentials.get_student_number.return_value = "student"
    credentials.get_credentials.return_value = ObisCredentials("student", "obis-password", "ciphertext-marker")
    previous = EdersSnapshot((item(),), NOW - timedelta(minutes=15))
    client.fetch_snapshot.return_value = previous
    service = EdersService(credentials, client, tracking)
    await service.refresh_snapshot(980_001)
    client.reset_mock()
    current = EdersSnapshot((), NOW)
    client.fetch_snapshot.side_effect = [EdersLoginError("form failed"), failure or current]
    if isinstance(failure, UserHasNoCredentialsError):
        credentials.get_credentials.side_effect = failure

    if failure:
        with pytest.raises(type(failure)):
            await service.refresh_snapshot(980_001)
        assert await service.get_snapshot(980_001) == previous
    else:
        assert await service.refresh_snapshot(980_001) == current
        assert await service.get_snapshot(980_001) == current
        state = await session.get(EdersState, 980_001)
        assert state.credential_marker == hashlib.sha256(b"student").hexdigest()
    credentials.get_credentials.assert_awaited_once_with(980_001)
    assert client.fetch_snapshot.await_args_list[0].args == ("student",)
    if not isinstance(failure, UserHasNoCredentialsError):
        assert client.fetch_snapshot.await_args_list[1].args == ("student", "obis-password")
        assert client.fetch_snapshot.await_count == 2
