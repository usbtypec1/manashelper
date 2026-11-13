import base64
import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from manashelper.modules.obis.application.models import (
    ExamModel,
    LessonAttendanceModel,
    LessonExamsModel,
    Snapshot,
)
from manashelper.modules.obis.errors import (
    ObisSessionExpiredError,
    ObisSnapshotNotReadyError,
    UserHasNoCredentialsError,
)
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.models.session import ObisSession
from manashelper.modules.obis.infrastructure.models.snapshot import ObisSnapshot
from manashelper.modules.obis.infrastructure.repositories.snapshot import ObisSnapshotRepository
from manashelper.modules.obis.infrastructure.repositories.user_exam_grade import UserExamGradeRepository
from manashelper.modules.users.infrastructure.models.user import User
from tests.modules.obis.factories import SESSION_COOKIES, build_obis
from tests.paths import FIXTURES_DIR


@pytest.fixture
async def cached_obis(session):
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    user = User(
        id=975201, full_name="Cache test", student_number="student", encrypted_password=crypto.encrypt("password")
    )
    session.add(user)
    await session.flush()
    client = AsyncMock(spec=ObisClient)
    client.fetch_exam_grades_html.return_value = (FIXTURES_DIR / "obis/grades.html").read_text(encoding="utf-8")
    client.fetch_attendance_html.return_value = (FIXTURES_DIR / "obis/attendance.html").read_text(encoding="utf-8")
    service = build_obis(session, client, crypto)
    await service.login(user.id)
    return service, client, user


async def test_cache_miss_never_fetches_and_successful_refresh_is_read_from_storage(session, cached_obis):
    service, client, user = cached_obis
    with pytest.raises(ObisSnapshotNotReadyError):
        await service.results.get_exam_grades(user.id)
    client.fetch_exam_grades_html.assert_not_awaited()
    grades = (await service.grades.execute(user.id)).lessons
    attendance = (await service.attendance.execute(user.id)).lessons
    await session.flush()
    client.reset_mock()
    assert await service.results.get_exam_grades(user.id) == grades
    assert await service.results.get_attendance(user.id) == attendance
    client.fetch_exam_grades_html.assert_not_awaited()
    client.fetch_attendance_html.assert_not_awaited()


async def test_failed_refresh_keeps_last_successful_snapshot(cached_obis):
    service, client, user = cached_obis
    previous = (await service.grades.execute(user.id)).lessons
    client.fetch_exam_grades_html.side_effect = httpx.ReadTimeout("upstream unavailable")
    with pytest.raises(httpx.ReadTimeout):
        await service.grades.execute(user.id)
    assert await service.results.get_exam_grades(user.id) == previous


async def test_queue_failure_rolls_back_snapshot_and_baseline_together(session, cached_obis):
    service, client, user = cached_obis
    previous = (await service.grades.execute(user.id)).lessons
    await session.flush()
    client.fetch_exam_grades_html.return_value = client.fetch_exam_grades_html.return_value.replace("80", "85")
    sender = AsyncMock()
    sender.exam_grade_changed.side_effect = RuntimeError("Queue unavailable")
    with pytest.raises(RuntimeError, match="Queue unavailable"):
        async with session.begin_nested():
            await service.poll.execute(user.id, True, True, sender)
    assert await service.results.get_exam_grades(975201) == previous
    saved = await UserExamGradeRepository(session).get_all_by_user_id(975201)
    assert any(record.score == "80" for record in saved)
    assert all(record.score != "85" for record in saved)
    retry = await service.grades.execute(975201)
    assert [change.score for change in retry.changes] == ["85"]


async def test_disabled_notifications_still_refresh_and_advance_comparison_baseline(session, cached_obis):
    service, client, user = cached_obis
    polling, sender = service.poll, AsyncMock()
    await polling.execute(user.id, False, False, sender)
    assert await service.results.get_exam_grades(user.id)
    assert await service.results.get_attendance(user.id)
    client.fetch_exam_grades_html.return_value = client.fetch_exam_grades_html.return_value.replace("80", "85")
    await polling.execute(user.id, False, False, sender)
    await polling.execute(user.id, True, True, sender)
    sender.exam_grade_changed.assert_not_awaited()
    sender.lesson_skips_changed.assert_not_awaited()


async def test_account_change_and_clear_invalidate_cached_data_and_notification_history(session, cached_obis):
    service, client, user = cached_obis
    await service.grades.execute(user.id)
    await session.flush()
    assert await UserExamGradeRepository(session).get_all_by_user_id(user.id)
    await service.login(user.id, "another-student", "new-password")
    with pytest.raises(ObisSnapshotNotReadyError):
        await service.results.get_exam_grades(user.id)
    assert await UserExamGradeRepository(session).get_all_by_user_id(user.id) == []
    assert (await service.grades.execute(user.id)).changes == []
    await service.clear.execute(user.id)
    assert not await service.sessions.has_session(user.id)
    with pytest.raises(UserHasNoCredentialsError):
        await service.results.get_exam_grades(user.id)
    assert await session.get(ObisSnapshot, (user.id, "grades")) is None


@pytest.mark.parametrize("kind", ["grades", "attendance"])
async def test_mismatched_account_is_rejected_before_decoding_snapshot(session, cached_obis, kind):
    service, client, user = cached_obis
    session.add(
        ObisSnapshot(
            user_id=user.id,
            kind=kind,
            credential_marker="previous-account",
            payload="invalid JSON from previous account",
            fetched_at=datetime.now(UTC),
        )
    )
    await session.flush()
    read = service.results.get_exam_grades if kind == "grades" else service.results.get_attendance
    with pytest.raises(ObisSnapshotNotReadyError):
        await read(user.id)
    client.fetch_exam_grades_html.assert_not_awaited()
    client.fetch_attendance_html.assert_not_awaited()


@pytest.mark.parametrize(
    ("kind", "payload", "expected"),
    [
        (
            "grades",
            '[{"lesson_name": "Математика", "lesson_code": null, "exams": [{"name": "Final", "score": null}]}]',
            [LessonExamsModel("Математика", None, [ExamModel("Final", None)])],
        ),
        (
            "attendance",
            '[{"lesson_name": "Математика", "lesson_code": "MATH", "theory_skips_percentage": 23.75, '
            '"practice_skips_percentage": null, "theory_skippable": 0, "practice_skippable": null}]',
            [LessonAttendanceModel("Математика", "MATH", 23.75, None, 0, None)],
        ),
    ],
)
async def test_snapshot_payload_keeps_legacy_format(session, cached_obis, kind, payload, expected):
    service, _, user = cached_obis
    marker = hashlib.sha256(user.encrypted_password.encode()).hexdigest()
    fetched_at = datetime.now(UTC)
    row = ObisSnapshot(user_id=user.id, kind=kind, credential_marker=marker, payload=payload, fetched_at=fetched_at)
    session.add(row)
    await session.flush()
    read = service.results.get_exam_grades if kind == "grades" else service.results.get_attendance
    assert await read(user.id) == expected

    repository = ObisSnapshotRepository(session)
    save = repository.save_exam_grades if kind == "grades" else repository.save_attendance
    await save(user.id, Snapshot(marker, expected, fetched_at))
    await session.flush()
    await session.refresh(row)
    assert json.loads(row.payload) == json.loads(payload)
    assert row.credential_marker == marker
    assert row.fetched_at == fetched_at


async def test_session_cookies_are_encrypted_at_rest(session, cached_obis):
    service, client, user = cached_obis
    await session.flush()
    row = await session.get(ObisSession, user.id)
    assert "fake-session" not in row.encrypted_cookies
    assert await service.sessions.get_cookies(user.id) == SESSION_COOKIES
    await service.grades.execute(user.id)
    client.fetch_exam_grades_html.assert_awaited_once_with(SESSION_COOKIES)


async def test_expired_session_notifies_once_stops_polling_and_keeps_cached_results(session, cached_obis):
    service, client, user = cached_obis
    grades = (await service.grades.execute(user.id)).lessons
    await session.flush()
    assert user.id in await service.results.get_poll_user_ids()
    client.fetch_exam_grades_html.side_effect = ObisSessionExpiredError
    sender = AsyncMock()
    await service.poll.execute(user.id, True, True, sender)
    await service.poll.execute(user.id, True, True, sender)
    sender.session_expired.assert_awaited_once_with()
    assert user.id not in await service.results.get_poll_user_ids()
    assert await service.results.get_exam_grades(user.id) == grades
    assert not await service.results.has_session(user.id)

    await service.login(user.id)
    await session.flush()
    assert user.id in await service.results.get_poll_user_ids()
    assert await service.results.get_exam_grades(user.id) == grades
