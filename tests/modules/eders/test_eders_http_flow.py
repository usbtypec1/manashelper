"""Run with the local Postman simulation; never contacts real student accounts."""

import base64
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from manashelper.modules.eders.errors import EdersFetchError, EdersSessionExpiredError
from manashelper.modules.eders.infrastructure import client as eders_client
from manashelper.modules.eders.infrastructure.repositories.eders import EdersRepository
from manashelper.modules.eders.infrastructure.serialization import serialize_snapshot
from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.errors import ObisLoginError, ObisParseError
from manashelper.modules.obis.infrastructure import client as obis_client
from manashelper.modules.obis.infrastructure.client import OBIS_BASE_URL, ObisClient
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.repositories.credentials import ObisCredentialsRepository
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.modules.users.queries import UsersQuery
from tests.modules.eders.application_factories import build_eders_service, build_eders_tracking_service
from tests.modules.eders.factories import make_eders_client
from tests.modules.obis.factories import build_obis

PORT = os.environ.get("MANASHELPER_EDERS_SIMULATION_PORT")
pytestmark = pytest.mark.skipif(
    not PORT, reason="Start postman/simulations/eders.sim.yaml and set MANASHELPER_EDERS_SIMULATION_PORT"
)


class SimulationTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.network = httpx.AsyncHTTPTransport()
        self.paths = []

    async def handle_async_request(self, request):
        assert request.url.host in {"obistest.manas.edu.kg", "eders.manas.edu.kg"}
        self.paths.append((request.method, request.url.path))
        # Retain the client's real URL and cookie/redirect logic; only route the socket locally.
        target = request.url.copy_with(scheme="http", host="127.0.0.1", port=int(PORT))
        forwarded = httpx.Request(
            request.method,
            target,
            headers={**request.headers, "x-mock-slug": "eders"},
            content=await request.aread(),
            extensions=request.extensions,
        )
        return await self.network.handle_async_request(forwarded)

    async def aclose(self):
        await self.network.aclose()


def install_client(monkeypatch, mode="normal"):
    transports = []

    def factory():
        transport = SimulationTransport()
        transports.append(transport)
        return httpx.AsyncClient(
            base_url=OBIS_BASE_URL,
            follow_redirects=True,
            transport=transport,
            headers={"x-fixture-mode": mode},
            timeout=5,
        )

    monkeypatch.setattr(eders_client, "new_http_client", factory)
    return transports


async def test_http_login_ajax_pagination_courses_and_details(monkeypatch):
    transports = install_client(monkeypatch)
    snapshot = await make_eders_client().fetch_snapshot("fake-student")
    assert len(snapshot.activities) == 3 and [course.id for course in snapshot.courses] == [10]
    assert transports[0].paths.count(("POST", "/lib/ajax/service.php")) == 2
    assert ("GET", "/mod/assign/view.php") in transports[0].paths
    assert ("GET", "/mod/quiz/view.php") in transports[0].paths
    assert transports[0].paths[:4] == [
        ("GET", "/login/index.php"),
        ("POST", "/login/index.php"),
        ("GET", "/login/index.php"),
        ("GET", "/my/courses.php"),
    ]
    assert not any(path.startswith("/site/") for _, path in transports[0].paths)
    assert "fake-sso" not in serialize_snapshot(snapshot) and "fakekey" not in serialize_snapshot(snapshot)


@pytest.mark.parametrize("mode", ["html-error", "invalid-json"])
async def test_http_ajax_failure_never_returns_partial_snapshot(monkeypatch, mode):
    install_client(monkeypatch, mode)
    with pytest.raises(EdersFetchError):
        await make_eders_client().fetch_snapshot("fake-student")


async def test_http_expired_session_retries_once(monkeypatch):
    transports = install_client(monkeypatch, "expired")
    with pytest.raises(EdersSessionExpiredError):
        await make_eders_client().fetch_snapshot("fake-student")
    assert len(transports) == 2


@pytest.mark.parametrize("completed", [True, False])
async def test_http_manual_completion_uses_authenticated_json_contract(monkeypatch, completed):
    transports = install_client(monkeypatch)
    await make_eders_client().set_activity_completion("fake-student", 20, completed)
    assert len(transports) == 1
    assert transports[0].paths[-1] == ("POST", "/lib/ajax/service.php")
    assert transports[0].paths[:2] == [("GET", "/login/index.php"), ("POST", "/login/index.php")]


@pytest.mark.parametrize("completed", [True, False])
async def test_http_manual_completion_supports_obis_sso(monkeypatch, completed):
    transports = install_client(monkeypatch)
    await make_eders_client().set_activity_completion("fake-student", 20, completed, "fake-password")
    assert transports[0].paths[0] == ("GET", "/site/login")
    assert transports[0].paths[-1] == ("POST", "/lib/ajax/service.php")


@pytest.mark.parametrize("mode", ["completion-denied", "completion-false", "invalid-json", "html-error"])
async def test_http_manual_completion_never_accepts_unconfirmed_success(monkeypatch, mode):
    transports = install_client(monkeypatch, mode)
    with pytest.raises(EdersFetchError):
        await make_eders_client().set_activity_completion("fake-student", 20, True)
    assert len(transports) == 1


@pytest.mark.parametrize("mode", ["completion-expired", "expired"])
async def test_http_manual_completion_reauthenticates_at_most_once(monkeypatch, mode):
    transports = install_client(monkeypatch, mode)
    with pytest.raises(EdersSessionExpiredError):
        await make_eders_client().set_activity_completion("fake-student", 20, True)
    assert len(transports) == 2


@pytest.mark.parametrize("mode", ["eders-login-denied", "eders-token-missing"])
async def test_http_login_failure_stops_before_reading_user_data(monkeypatch, mode):
    transports = install_client(monkeypatch, mode)
    with pytest.raises(EdersFetchError):
        await make_eders_client().fetch_snapshot("fake-student")
    assert len(transports) == 1
    assert all(path == "/login/index.php" for _, path in transports[0].paths)


def install_obis_client(monkeypatch, mode="normal"):
    transports = install_client(monkeypatch, mode)
    monkeypatch.setattr(obis_client, "new_http_client", eders_client.new_http_client)
    return transports


async def test_obis_http_verification_uses_a_fresh_login_for_each_call(monkeypatch):
    transports = install_obis_client(monkeypatch)
    client = ObisClient()
    await client.verify_credentials("fake-student", "fake-password")
    await client.verify_credentials("fake-student", "fake-password")
    assert len(transports) == 2
    assert all(
        transport.paths == [("GET", "/site/login"), ("POST", "/site/login"), ("GET", "/")] for transport in transports
    )


async def test_obis_http_credentials_grades_and_attendance_run_through_real_client(session, monkeypatch):
    transports = install_obis_client(monkeypatch)
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    user = User(id=975101, full_name="Fixture student")
    session.add(user)
    await session.flush()
    obis = ObisClient()
    service = build_obis(session, obis, crypto)
    await service.save.execute(user.id, "fake-student", "fake-password")
    assert user.encrypted_password != "fake-password" and crypto.decrypt(user.encrypted_password) == "fake-password"
    grades = (await service.grades.execute(user.id)).lessons
    attendance = (await service.attendance.execute(user.id)).lessons
    assert grades[0].exams[0].score == "80" and grades[0].lesson_code == "MATH"
    assert attendance[0].theory_skips_percentage == 12.5 and attendance[0].practice_skips_percentage == 6.25
    assert await service.results.get_exam_grades(user.id) == grades
    assert await service.results.get_attendance(user.id) == attendance
    assert len(transports) == 3
    assert transports[1].paths[-1] == ("GET", "/vs-ders/taken-grades")
    assert transports[2].paths[-1] == ("GET", "/vs-ders/taken-lessons")


@pytest.mark.parametrize(
    "mode,error",
    [("login-denied", ObisLoginError), ("csrf-missing", ObisParseError), ("html-error", httpx.HTTPStatusError)],
)
async def test_obis_http_failure_preserves_error_type(monkeypatch, mode, error):
    install_obis_client(monkeypatch, mode)
    with pytest.raises(error):
        await ObisClient().fetch_exam_grades_html("fake-student", "fake-password")


@pytest.mark.parametrize(
    "failure_mode,error", [("html-error", httpx.HTTPStatusError), ("transcript-malformed", ObisParseError)]
)
async def test_obis_transcript_http_awards_and_failed_refresh_preserves_progress(
    session, monkeypatch, failure_mode, error
):
    from manashelper.modules.gamification.application.queries import GamificationQuery
    from manashelper.modules.gamification.application.use_cases.record_transcript import RecordTranscriptUseCase
    from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
    from manashelper.modules.obis.application.use_cases.refresh_obis_transcript import RefreshObisTranscriptUseCase
    from manashelper.modules.obis.infrastructure.results_source import ObisResultsSource

    transports = install_obis_client(monkeypatch)
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    user = User(
        id=975105,
        full_name="Transcript fixture",
        student_number="fake-student",
        encrypted_password=crypto.encrypt("fake-password"),
    )
    session.add(user)
    await session.flush()
    credentials = ObisCredentialsRepository(session)
    repo = AchievementRepository(session)
    await repo.set_enabled(user.id, True)
    refresh = RefreshObisTranscriptUseCase(
        ObisCredentialsQuery(credentials, crypto),
        credentials,
        ObisResultsSource(ObisClient()),
        RecordTranscriptUseCase(repo),
        GamificationQuery(repo),
    )
    await refresh.execute(user.id)
    await session.flush()
    before = await repo.academic_progress(user.id)
    assert before[0] and before[1] is not None and before[2] is not None
    assert set(await repo.get_awards(user.id)) == {"formula_one", "champion", "comeback"}
    assert transports[0].paths == [
        ("GET", "/site/login"),
        ("POST", "/site/login"),
        ("GET", "/"),
        ("GET", "/vs-ders/transkript-detailed"),
    ]
    install_obis_client(monkeypatch, failure_mode)
    with pytest.raises(error):
        await refresh.execute(user.id)
    assert await repo.academic_progress(user.id) == before


async def test_eders_background_refresh_persists_snapshot_and_read_survives_upstream_failure(session, monkeypatch):
    transports = install_client(monkeypatch)
    user = User(id=975102, full_name="Cache fixture", student_number="fake-student")
    session.add(user)
    await session.flush()
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    account = ObisCredentialsQuery(ObisCredentialsRepository(session), crypto)
    tracking = build_eders_tracking_service(EdersRepository(session), UsersQuery(UserRepository(session)), AsyncMock())
    service = build_eders_service(account, make_eders_client(), tracking)
    refreshed = await service.refresh_snapshot(user.id)
    await session.flush()
    assert len(refreshed.activities) == 3
    assert await service.get_snapshot(user.id) == refreshed
    assert len(transports) == 1
    failed_transports = install_client(monkeypatch, "html-error")
    with pytest.raises(EdersFetchError):
        await service.refresh_snapshot(user.id)
    paths = list(failed_transports[0].paths)
    assert await service.get_snapshot(user.id) == refreshed
    assert failed_transports[0].paths == paths


async def test_new_achievements_through_real_http_refresh_with_opt_in_and_failure_preservation(session, monkeypatch):
    from manashelper.modules.gamification.application.queries import GamificationQuery
    from manashelper.modules.gamification.application.use_cases.record_transcript import RecordTranscriptUseCase
    from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
    from manashelper.modules.obis.application.use_cases.refresh_obis_transcript import RefreshObisTranscriptUseCase
    from manashelper.modules.obis.infrastructure.results_source import ObisResultsSource

    transports = install_obis_client(monkeypatch, "achievement-progress")
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    user = User(
        id=975106,
        full_name="Pilot fixture",
        student_number="fake-student",
        encrypted_password=crypto.encrypt("fake-password"),
    )
    session.add(user)
    await session.flush()
    repo = AchievementRepository(session)
    credentials = ObisCredentialsRepository(session)
    client = ObisClient()
    refresh = RefreshObisTranscriptUseCase(
        ObisCredentialsQuery(credentials, crypto),
        credentials,
        ObisResultsSource(client),
        RecordTranscriptUseCase(repo),
        GamificationQuery(repo),
    )
    await refresh.execute(user.id)
    assert transports == []  # Default off prevents the extra OBIS login/fetch entirely.
    await repo.set_enabled(user.id, True)
    await refresh.execute(user.id)
    attendance = build_obis(session, client, crypto).attendance
    await attendance.execute(user.id)
    await session.flush()
    awards = await repo.get_awards(user.id)
    assert set(awards) == {"formula_one", "champion", "comeback", "eldin_balasy", "thin_ice"}
    before = await repo.attendance_progress(user.id)
    assert before == (True, 5)
    assert transports[0].paths[-1] == ("GET", "/vs-ders/transkript-detailed")
    assert transports[1].paths[-1] == ("GET", "/vs-ders/taken-lessons")
    install_obis_client(monkeypatch, "html-error")
    with pytest.raises(httpx.HTTPStatusError):
        await attendance.execute(user.id)
    assert await repo.attendance_progress(user.id) == before
    assert await repo.get_awards(user.id) == awards


@pytest.mark.parametrize(
    "mode", ["eders-login-denied", "eders-token-missing", "eders-login-unavailable", "eders-sso-link"]
)
async def test_http_failed_direct_login_falls_back_to_obis_sso(session, monkeypatch, mode):
    transports = install_client(monkeypatch, mode)
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    user = User(
        id=975103,
        full_name="Fallback fixture",
        student_number="fake-student",
        encrypted_password=crypto.encrypt("fake-password"),
    )
    session.add(user)
    await session.flush()
    account = ObisCredentialsQuery(ObisCredentialsRepository(session), crypto)
    tracking = build_eders_tracking_service(EdersRepository(session), UsersQuery(UserRepository(session)), AsyncMock())
    service = build_eders_service(account, make_eders_client(), tracking)
    snapshot = await service.refresh_snapshot(user.id)
    await session.flush()

    assert len(snapshot.activities) == 3
    assert await service.get_snapshot(user.id) == snapshot
    assert len(transports) == 2
    assert transports[0].paths[0] == ("GET", "/login/index.php")
    assert all(path == "/login/index.php" for _, path in transports[0].paths)
    assert transports[1].paths[:6] == [
        ("GET", "/site/login"),
        ("POST", "/site/login"),
        ("GET", "/"),
        ("GET", "/site/eders"),
        ("GET", "/auth/userkey/login.php"),
        ("GET", "/my/index.php"),
    ]
    assert transports[1].paths.count(("POST", "/lib/ajax/service.php")) == 2
    assert await tracking.pending_events(user.id, snapshot.fetched_at) == []
    serialized = serialize_snapshot(snapshot)
    assert "fake-password" not in serialized and "fake-sso" not in serialized


@pytest.mark.parametrize("mode", ["both-logins-denied", "sso-expired"])
async def test_http_both_login_paths_fail_without_replacing_previous_snapshot(session, monkeypatch, mode):
    install_client(monkeypatch)
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    user = User(
        id=975104,
        full_name="Fallback failure",
        student_number="fake-student",
        encrypted_password=crypto.encrypt("fake-password"),
    )
    session.add(user)
    await session.flush()
    account = ObisCredentialsQuery(ObisCredentialsRepository(session), crypto)
    tracking = build_eders_tracking_service(EdersRepository(session), UsersQuery(UserRepository(session)), AsyncMock())
    service = build_eders_service(account, make_eders_client(), tracking)
    previous = await service.refresh_snapshot(user.id)
    await session.flush()
    transports = install_client(monkeypatch, mode)
    with pytest.raises(EdersFetchError):
        await service.refresh_snapshot(user.id)
    assert await service.get_snapshot(user.id) == previous
    assert len(transports) == (3 if mode == "sso-expired" else 2)
    assert not any(path == "/lib/ajax/service.php" for transport in transports for _, path in transport.paths)
