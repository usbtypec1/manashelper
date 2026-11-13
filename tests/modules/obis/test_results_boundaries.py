from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from manashelper.modules.obis.application.credentials import ObisCredentials, ObisCredentialsQuery
from manashelper.modules.obis.application.models import (
    AttendanceRecord,
    ExamModel,
    LessonAttendanceModel,
    LessonExamsModel,
)
from manashelper.modules.obis.application.ports import (
    AttendanceStore,
    CredentialsStore,
    ExamGradeStore,
    ResultsSource,
    SnapshotStore,
)
from manashelper.modules.obis.application.queries import ObisResultsQuery
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.application.use_cases.refresh_obis_attendance import RefreshObisAttendanceUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_grades import RefreshObisGradesUseCase
from manashelper.modules.obis.errors import ObisParseError, ObisSessionExpiredError, ObisSnapshotNotReadyError

COOKIES = {"PHPSESSID": "session"}


def _sessions(active=True):
    sessions = AsyncMock(spec=ObisSessions)
    sessions.get_cookies.return_value = COOKIES
    sessions.has_session.return_value = active
    return sessions


@pytest.mark.parametrize("kind", ["exam_grades", "attendance"])
async def test_refresh_locks_then_fetches_then_saves_snapshot_and_comparison_baseline(kind):
    credentials = AsyncMock(spec=ObisCredentialsQuery)
    store = AsyncMock(spec=CredentialsStore)
    source = AsyncMock(spec=ResultsSource)
    snapshots = AsyncMock(spec=SnapshotStore)
    baseline = AsyncMock(spec=ExamGradeStore if kind == "exam_grades" else AttendanceStore)
    order = []

    async def lock(user_id):
        assert user_id == 123
        order.append("lock")

    async def account(user_id):
        assert user_id == 123
        order.append("credentials")
        return ObisCredentials("student", "password", "marker")

    grades = [LessonExamsModel("Math", "MATH", [ExamModel("Final", "90")])]
    attendance = [AttendanceRecord("Math", "MATH", 23.75, None)]
    expected = grades if kind == "exam_grades" else [LessonAttendanceModel("Math", "MATH", 23.75, None, 0, None)]

    async def fetch(cookies):
        assert cookies == COOKIES
        order.append("fetch")
        return grades if kind == "exam_grades" else attendance

    async def save(user_id, snapshot):
        assert user_id == 123
        order.append("snapshot")
        assert snapshot.credential_marker == "marker"
        assert snapshot.lessons == expected
        assert before <= snapshot.fetched_at <= datetime.now(UTC)

    async def read_baseline(user_id):
        assert user_id == 123
        order.append("read_baseline")
        return []

    async def save_baseline(user_id, records):
        assert user_id == 123 and len(records) == 1
        order.append("save_baseline")

    store.lock.side_effect = lock
    credentials.get_credentials.side_effect = account
    getattr(source, f"fetch_{kind}").side_effect = fetch
    getattr(snapshots, f"save_{kind}").side_effect = save
    baseline.get_all_by_user_id.side_effect = read_baseline
    baseline.save_all.side_effect = save_baseline
    before = datetime.now(UTC)
    cls = RefreshObisGradesUseCase if kind == "exam_grades" else RefreshObisAttendanceUseCase
    recorder = AsyncMock()
    args = [credentials, store, source, _sessions(), snapshots, baseline]
    if kind == "attendance":
        args.append(recorder)
    result = await cls(*args).execute(123)
    if kind == "attendance":
        recorder.execute.assert_awaited_once_with(123, "student", expected)
    assert result.lessons == expected
    assert result.changes == []
    assert order == ["lock", "credentials", "fetch", "snapshot", "read_baseline", "save_baseline"]


@pytest.mark.parametrize("kind", ["exam_grades", "attendance"])
async def test_cached_reads_pass_account_marker(kind):
    credentials = AsyncMock(spec=ObisCredentialsQuery)
    credentials.get_credentials.return_value = ObisCredentials("student", "password", "marker")
    store = AsyncMock(spec=SnapshotStore)
    read = getattr(store, f"get_{kind}")
    read.return_value = None
    query = ObisResultsQuery(credentials, store, _sessions())
    with pytest.raises(ObisSnapshotNotReadyError):
        await getattr(query, f"get_{kind}")(123)
    read.assert_awaited_once_with(123, "marker")
    with pytest.raises(ObisSessionExpiredError):
        await getattr(ObisResultsQuery(credentials, store, _sessions(active=False)), f"get_{kind}")(123)
    read.return_value = []
    assert await getattr(query, f"get_{kind}")(123) == []


@pytest.mark.parametrize("kind", ["exam_grades", "attendance"])
async def test_failed_source_does_not_write_snapshot_or_comparison_baseline(kind):
    credentials = AsyncMock(spec=ObisCredentialsQuery)
    credentials.get_credentials.return_value = ObisCredentials("student", "password", "marker")
    store = AsyncMock(spec=CredentialsStore)
    source = AsyncMock(spec=ResultsSource)
    getattr(source, f"fetch_{kind}").side_effect = ObisParseError("Invalid upstream page")
    snapshots = AsyncMock(spec=SnapshotStore)
    baseline = AsyncMock(spec=ExamGradeStore if kind == "exam_grades" else AttendanceStore)
    cls = RefreshObisGradesUseCase if kind == "exam_grades" else RefreshObisAttendanceUseCase
    recorder = AsyncMock()
    args = [credentials, store, source, _sessions(), snapshots, baseline]
    if kind == "attendance":
        args.append(recorder)
    with pytest.raises(ObisParseError):
        await cls(*args).execute(123)
    recorder.execute.assert_not_awaited()
    snapshots.save_exam_grades.assert_not_awaited()
    snapshots.save_attendance.assert_not_awaited()
    baseline.save_all.assert_not_awaited()
