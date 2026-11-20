import asyncio
import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from manashelper.modules.obis.application.access import ObisAccessService
from manashelper.modules.obis.application.models import RefreshResult, StoredObisAuthState
from manashelper.modules.obis.application.ports import AuthStateStore, CredentialsStore
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.application.use_cases.auto_login_obis import AutoLoginObisUseCase
from manashelper.modules.obis.application.use_cases.poll_obis_user import PollObisUserUseCase
from manashelper.modules.obis.errors import (
    ObisLoginError,
    ObisManualLoginRequiredError,
    ObisParseError,
    ObisRetryLaterError,
    ObisSessionExpiredError,
)
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.repositories.auth_state import ObisAuthStateRepository
from manashelper.modules.obis.infrastructure.repositories.credentials import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.repositories.session import ObisSessionRepository
from manashelper.modules.users.infrastructure.models.user import User
from tests.modules.obis.factories import SESSION_COOKIES, build_obis


@pytest.fixture
def access():
    saved = {}
    states = AsyncMock(spec=AuthStateStore)

    async def get(user_id):
        return saved.get(user_id)

    async def save(user_id, state):
        saved[user_id] = state

    async def remove(user_id):
        saved.pop(user_id, None)

    states.get.side_effect, states.save.side_effect, states.delete.side_effect = get, save, remove
    sessions = AsyncMock(spec=ObisSessions)
    sessions.get_cookies.return_value = dict(SESSION_COOKIES)
    login = AsyncMock(spec=AutoLoginObisUseCase)
    login.execute.return_value = None
    store = AsyncMock(spec=CredentialsStore)
    return SimpleNamespace(
        service=ObisAccessService(store, sessions, login, states),
        store=store,
        sessions=sessions,
        login=login,
        states=states,
        saved=saved,
    )


async def test_existing_session_does_not_login_and_locks_before_read(access):
    operation = AsyncMock(return_value="data")
    assert await access.service.with_session(42, operation) == "data"
    access.store.lock.assert_awaited_once_with(42)
    access.login.execute.assert_not_awaited()
    operation.assert_awaited_once_with(SESSION_COOKIES)


async def test_missing_session_logs_in_before_first_fetch(access):
    access.sessions.get_cookies.side_effect = [ObisSessionExpiredError(), dict(SESSION_COOKIES)]
    operation = AsyncMock(return_value=[])
    assert await access.service.with_session(42, operation) == []
    access.login.execute.assert_awaited_once_with(42)
    operation.assert_awaited_once_with(SESSION_COOKIES)


async def test_expired_session_retries_only_the_failed_read_once(access):
    access.sessions.get_cookies.side_effect = [{"PHPSESSID": "old"}, {"PHPSESSID": "new"}]
    operation = AsyncMock(side_effect=[ObisSessionExpiredError(), "data"])
    assert await access.service.with_session(42, operation) == "data"
    assert [call.args[0] for call in operation.await_args_list] == [
        {"PHPSESSID": "old"},
        {"PHPSESSID": "new"},
    ]
    access.login.execute.assert_awaited_once_with(42)


async def test_rejected_recovered_session_stops_without_a_second_recovery(access):
    operation = AsyncMock(side_effect=ObisSessionExpiredError)
    with pytest.raises(ObisManualLoginRequiredError):
        await access.service.with_session(42, operation)
    access.login.execute.assert_awaited_once_with(42)
    assert operation.await_count == 2
    assert access.saved[42].reason == "session_rejected"


@pytest.mark.parametrize("error", [None, ObisLoginError()])
async def test_manual_outcome_pauses_across_service_instances_and_notice_is_claimed_once(access, error):
    access.sessions.get_cookies.side_effect = ObisSessionExpiredError
    access.login.execute.return_value = object()
    access.login.execute.side_effect = error
    operation = AsyncMock()
    with pytest.raises(ObisManualLoginRequiredError):
        await access.service.with_session(42, operation)
    restarted = replace(access.service)
    with pytest.raises(ObisManualLoginRequiredError):
        await restarted.with_session(42, operation)
    assert access.login.execute.await_count == 1
    operation.assert_not_awaited()
    assert await restarted.claim_manual_login_notice(42)
    assert not await access.service.claim_manual_login_notice(42)


@pytest.mark.parametrize("error", [httpx.ReadTimeout("timeout"), ObisParseError("unknown login response")])
async def test_uncertain_login_defers_without_deleting_saved_session_or_repeating_post(access, error):
    access.sessions.get_cookies.side_effect = ObisSessionExpiredError
    access.login.execute.side_effect = error
    operation = AsyncMock()
    before = datetime.now(UTC)
    with pytest.raises(ObisRetryLaterError):
        await access.service.with_session(42, operation)
    state = access.saved[42]
    assert not state.manual_required and state.failures == 1
    assert before + timedelta(minutes=15) <= state.retry_at <= datetime.now(UTC) + timedelta(minutes=15)
    with pytest.raises(ObisRetryLaterError):
        await replace(access.service).with_session(42, operation)
    access.login.execute.assert_awaited_once()
    access.sessions.expire.assert_not_awaited()
    operation.assert_not_awaited()


async def test_transport_backoff_survives_restart_and_grows_after_another_failure(access):
    operation = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
    with pytest.raises(ObisRetryLaterError):
        await access.service.with_session(42, operation)
    access.saved[42] = replace(access.saved[42], retry_at=datetime.now(UTC) - timedelta(seconds=1))
    before = datetime.now(UTC)
    with pytest.raises(ObisRetryLaterError):
        await replace(access.service).with_session(42, operation)
    assert access.saved[42].failures == 2
    assert access.saved[42].retry_at >= before + timedelta(minutes=30)
    access.login.execute.assert_not_awaited()


async def test_authenticated_response_cookie_rotation_is_saved(access):
    async def operation(cookies):
        cookies["PHPSESSID"] = "rotated"
        return "data"

    assert await access.service.with_session(42, operation) == "data"
    access.sessions.update_cookies.assert_awaited_once_with(42, {"PHPSESSID": "rotated"})


async def test_partial_poll_success_preserves_consecutive_failure_backoff(access):
    grades, attendance, transcript, sender = [AsyncMock() for _ in range(4)]
    failing = AsyncMock(side_effect=httpx.ReadTimeout("attendance unavailable"))

    async def read_grades(user_id):
        return await access.service.with_session(user_id, AsyncMock(return_value=RefreshResult([], [])))

    async def read_attendance(user_id):
        return await access.service.with_session(user_id, failing)

    grades.execute.side_effect = read_grades
    attendance.execute.side_effect = read_attendance
    for failures, minutes in [(1, 15), (2, 30), (3, 60)]:
        before = datetime.now(UTC)
        # Recompose the worker like a new scheduled request.
        await PollObisUserUseCase(grades, attendance, transcript, replace(access.service)).execute(
            42, True, True, sender
        )
        assert access.saved[42].failures == failures
        assert access.saved[42].retry_at >= before + timedelta(minutes=minutes)
        access.saved[42] = replace(access.saved[42], retry_at=datetime.now(UTC) - timedelta(seconds=1))
    # A successful SSO/read also cannot erase failures from another refresh stage.
    await access.service.with_session(42, AsyncMock(return_value="SSO"))
    assert access.saved[42].failures == 3
    failing.side_effect = None
    failing.return_value = RefreshResult([], [])
    await PollObisUserUseCase(grades, attendance, transcript, access.service).execute(42, True, True, sender)
    assert 42 not in access.saved
    sender.session_expired.assert_not_awaited()


def cipher():
    return CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))


async def test_credentials_without_session_are_candidates_and_poll_creates_session(session):
    crypto = cipher()
    user = User(
        id=978901, full_name="Initial login", student_number="student", encrypted_password=crypto.encrypt("password")
    )
    session.add(user)
    await session.flush()
    client = AsyncMock()
    service = build_obis(session, client, crypto)
    client.start_login.return_value = replace(client.start_login.return_value, expected_hash=123)
    service.auto_login.recognizer.solve.return_value = "code"
    client.fetch_exam_grades_html.return_value = "<invalid>"
    # Test session bootstrap at the access boundary, independent of result parsing.
    assert user.id in await service.results.get_poll_user_ids()
    assert await service.access.with_session(user.id, AsyncMock(return_value=[])) == []
    await session.flush()
    assert await service.sessions.has_session(user.id)
    client.complete_login.assert_awaited_once()


async def test_manual_notice_queue_failure_rolls_back_claim_and_success_resumes_polling(session):
    crypto = cipher()
    user = User(
        id=978902, full_name="Manual login", student_number="student", encrypted_password=crypto.encrypt("password")
    )
    session.add(user)
    await session.flush()
    service = build_obis(session, AsyncMock(), crypto)
    sender = AsyncMock()
    sender.session_expired.side_effect = RuntimeError("queue unavailable")
    with pytest.raises(RuntimeError, match="queue unavailable"):
        async with session.begin_nested():
            await service.poll.execute(978902, True, True, sender)
    assert await service.auth_states.get(978902) is None

    sender.session_expired.side_effect = None
    await service.poll.execute(978902, True, True, sender)
    await session.flush()
    assert 978902 not in await service.results.get_poll_user_ids()
    state = await ObisAuthStateRepository(session).get(978902)
    assert state.manual_required and state.notified
    await service.poll.execute(978902, True, True, sender)
    assert sender.session_expired.await_count == 2  # One rolled back enqueue and one successful enqueue.
    await service.login(978902)
    assert await service.auth_states.get(978902) is None
    assert 978902 in await service.results.get_poll_user_ids()


async def test_poll_selection_keeps_unnotified_manual_requests_and_due_retries(session):
    crypto = cipher()
    user = User(
        id=978903, full_name="Retry selection", student_number="student", encrypted_password=crypto.encrypt("password")
    )
    session.add(user)
    await session.flush()
    service = build_obis(session, AsyncMock(), crypto)
    states = service.auth_states
    await states.save(user.id, StoredObisAuthState(False, "transport", 1, datetime.now(UTC) + timedelta(hours=1)))
    assert user.id not in await service.results.get_poll_user_ids()
    await states.save(user.id, StoredObisAuthState(False, "transport", 1, datetime.now(UTC) - timedelta(seconds=1)))
    assert user.id in await service.results.get_poll_user_ids()
    await states.save(user.id, StoredObisAuthState(True, "captcha"))
    assert user.id in await service.results.get_poll_user_ids()
    user.is_blocked = True
    assert user.id not in await service.results.get_poll_user_ids()
    user.is_blocked = False
    assert user.id in await service.results.get_poll_user_ids()
    await states.save(user.id, StoredObisAuthState(True, "captcha", notified=True))
    assert user.id not in await service.results.get_poll_user_ids()


async def test_concurrent_workers_create_only_one_login_session(engine):
    user_id = 978904
    crypto = cipher()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as setup:
        setup.add(
            User(
                id=user_id,
                full_name="Serialized login",
                student_number="student",
                encrypted_password=crypto.encrypt("password"),
            )
        )
    entered, release, competing = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = []

    async def run():
        async with factory.begin() as session:
            sessions = ObisSessions(ObisSessionRepository(session), crypto)
            login = AsyncMock(spec=AutoLoginObisUseCase)

            async def authenticate(uid):
                calls.append(uid)
                entered.set()
                await release.wait()
                await sessions.save(uid, {"PHPSESSID": "shared"})

            login.execute.side_effect = authenticate
            access = ObisAccessService(
                ObisCredentialsRepository(session), sessions, login, ObisAuthStateRepository(session)
            )
            await session.connection()
            competing.set()
            return await access.with_session(user_id, AsyncMock(return_value="data"))

    first = second = None
    try:
        first = asyncio.create_task(run())
        await asyncio.wait_for(entered.wait(), 3)
        competing.clear()
        second = asyncio.create_task(run())
        await asyncio.wait_for(competing.wait(), 3)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(second), timeout=0.2)
        assert calls == [user_id]
        release.set()
        assert await asyncio.wait_for(asyncio.gather(first, second), 5) == ["data", "data"]
        assert calls == [user_id]
    finally:
        release.set()
        for task in (first, second):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(*(task for task in (first, second) if task is not None), return_exceptions=True)
        async with factory.begin() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
