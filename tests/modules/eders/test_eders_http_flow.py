"""Run with the local Postman simulation; never contacts real student accounts."""

import base64
import os
from types import SimpleNamespace

import httpx
import pytest

from manashelper.modules.eders.application.eders import EdersService
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.errors import EdersFetchError, EdersSessionExpiredError
from manashelper.modules.eders.infrastructure import client as eders_client
from manashelper.modules.eders.infrastructure.repository import EdersRepository
from manashelper.modules.eders.infrastructure.serialization import serialize_snapshot
from manashelper.modules.obis.application.credentials import ObisCredentialsService
from manashelper.modules.obis.application.obis import ObisService
from manashelper.modules.obis.errors import ObisLoginError, ObisParseError
from manashelper.modules.obis.infrastructure import client as obis_client
from manashelper.modules.obis.infrastructure.client import OBIS_BASE_URL, ObisClient
from manashelper.modules.obis.infrastructure.credentials_repository import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.snapshot_repository import ObisSnapshotRepository
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.queries import UsersQuery
from tests.modules.eders.factories import make_eders_client

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
    account = ObisCredentialsService(ObisCredentialsRepository(session), obis, crypto)
    service = ObisService(account, obis, ObisSnapshotRepository(session))
    await service.save_credentials(user.id, "fake-student", "fake-password")
    assert user.encrypted_password != "fake-password" and crypto.decrypt(user.encrypted_password) == "fake-password"
    grades = await service.refresh_exam_grades(user.id)
    attendance = await service.refresh_attendance(user.id)
    assert grades[0].exams[0].score == "80" and grades[0].lesson_code == "MATH"
    assert attendance[0].theory_skips_percentage == 12.5 and attendance[0].practice_skips_percentage == 6.25
    assert await service.get_exam_grades(user.id) == grades
    assert await service.get_attendance(user.id) == attendance
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


async def test_eders_background_refresh_persists_snapshot_and_read_survives_upstream_failure(session, monkeypatch):
    transports = install_client(monkeypatch)
    user = User(id=975102, full_name="Cache fixture", student_number="fake-student")
    session.add(user)
    await session.flush()
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    account = ObisCredentialsService(ObisCredentialsRepository(session), ObisClient(), crypto)
    tracking = EdersTrackingService(EdersRepository(session), UsersQuery(UserRepository(session)))
    service = EdersService(account, make_eders_client(), tracking)
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
    account = ObisCredentialsService(ObisCredentialsRepository(session), ObisClient(), crypto)
    tracking = EdersTrackingService(EdersRepository(session), UsersQuery(UserRepository(session)))
    service = EdersService(account, make_eders_client(), tracking)
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
    account = ObisCredentialsService(ObisCredentialsRepository(session), ObisClient(), crypto)
    tracking = EdersTrackingService(EdersRepository(session), UsersQuery(UserRepository(session)))
    service = EdersService(account, make_eders_client(), tracking)
    previous = await service.refresh_snapshot(user.id)
    await session.flush()
    transports = install_client(monkeypatch, mode)
    with pytest.raises(EdersFetchError):
        await service.refresh_snapshot(user.id)
    assert await service.get_snapshot(user.id) == previous
    assert len(transports) == (3 if mode == "sso-expired" else 2)
    assert not any(path == "/lib/ajax/service.php" for transport in transports for _, path in transport.paths)
