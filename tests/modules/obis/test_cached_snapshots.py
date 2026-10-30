import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from manashelper.modules.obis.application.credentials import ObisCredentialsService
from manashelper.modules.obis.application.notification import ObisNotificationService
from manashelper.modules.obis.application.obis import ObisService
from manashelper.modules.obis.application.polling import PollObisUser
from manashelper.modules.obis.errors import ObisSnapshotNotReadyError, UserHasNoCredentialsError
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.credentials_repository import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.snapshot_repository import ObisSnapshotRepository
from manashelper.modules.obis.infrastructure.user_exam_grade_repository import UserExamGradeRepository
from manashelper.modules.obis.infrastructure.user_lesson_attendance_repository import UserLessonAttendanceRepository
from manashelper.modules.users.infrastructure.user import User
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
    client.fetch_exam_grades_html.return_value = (FIXTURES_DIR / "obis/grades.html").read_text()
    client.fetch_attendance_html.return_value = (FIXTURES_DIR / "obis/attendance.html").read_text()
    credentials = ObisCredentialsService(ObisCredentialsRepository(session), client, crypto)
    service = ObisService(credentials, client, ObisSnapshotRepository(session))
    return service, client, user


async def test_cache_miss_never_fetches_and_successful_refresh_is_read_from_storage(session, cached_obis):
    service, client, user = cached_obis
    with pytest.raises(ObisSnapshotNotReadyError):
        await service.get_exam_grades(user.id)
    client.fetch_exam_grades_html.assert_not_awaited()
    grades = await service.refresh_exam_grades(user.id)
    attendance = await service.refresh_attendance(user.id)
    await session.flush()
    client.reset_mock()
    assert await service.get_exam_grades(user.id) == grades
    assert await service.get_attendance(user.id) == attendance
    client.fetch_exam_grades_html.assert_not_awaited()
    client.fetch_attendance_html.assert_not_awaited()


async def test_failed_refresh_keeps_last_successful_snapshot(cached_obis):
    service, client, user = cached_obis
    previous = await service.refresh_exam_grades(user.id)
    client.fetch_exam_grades_html.side_effect = httpx.ReadTimeout("upstream unavailable")
    with pytest.raises(httpx.ReadTimeout):
        await service.refresh_exam_grades(user.id)
    assert await service.get_exam_grades(user.id) == previous


async def test_disabled_notifications_still_refresh_and_advance_comparison_baseline(session, cached_obis):
    service, client, user = cached_obis
    notifications = ObisNotificationService(
        service, UserExamGradeRepository(session), UserLessonAttendanceRepository(session)
    )
    polling, sender = PollObisUser(notifications), AsyncMock()
    await polling.execute(user.id, False, False, sender)
    assert await service.get_exam_grades(user.id)
    assert await service.get_attendance(user.id)
    client.fetch_exam_grades_html.return_value = client.fetch_exam_grades_html.return_value.replace("80", "85")
    await polling.execute(user.id, False, False, sender)
    await polling.execute(user.id, True, True, sender)
    sender.exam_grade_changed.assert_not_awaited()
    sender.lesson_skips_changed.assert_not_awaited()


async def test_account_change_and_clear_invalidate_cached_data_and_notification_history(session, cached_obis):
    service, client, user = cached_obis
    notifications = ObisNotificationService(
        service, UserExamGradeRepository(session), UserLessonAttendanceRepository(session)
    )
    await notifications.check_exam_grade_changes(user.id)
    await session.flush()
    assert await UserExamGradeRepository(session).get_all_by_user_id(user.id)
    await service.save_credentials(user.id, "another-student", "new-password")
    with pytest.raises(ObisSnapshotNotReadyError):
        await service.get_exam_grades(user.id)
    assert await UserExamGradeRepository(session).get_all_by_user_id(user.id) == []
    assert await notifications.check_exam_grade_changes(user.id) == []
    await service.clear_credentials(user.id)
    with pytest.raises(UserHasNoCredentialsError):
        await service.get_exam_grades(user.id)
    assert await ObisSnapshotRepository(session).get(user.id, "grades") is None
