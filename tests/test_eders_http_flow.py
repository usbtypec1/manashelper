"""Run with the local Postman simulation; never contacts real student accounts."""

import base64
import os
from types import SimpleNamespace

import httpx
import pytest

from manashelper.db.models import User
from manashelper.modules.obis.application.credentials import ObisCredentialsService
from manashelper.modules.obis.application.obis import ObisService
from manashelper.modules.obis.errors import ObisLoginError, ObisParseError
from manashelper.modules.obis.infrastructure import client
from manashelper.modules.obis.infrastructure.client import OBIS_BASE_URL, ObisClient
from manashelper.modules.obis.infrastructure.credentials_repository import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.scraping import eders_client
from manashelper.scraping.eders_client import EdersClient, EdersFetchError, EdersSessionExpiredError
from manashelper.services.eders_serialization import serialize_snapshot

PORT = os.environ.get("EDERS_SIMULATION_PORT")
pytestmark = pytest.mark.skipif(
    not PORT, reason="Start postman/simulations/eders.sim.yaml and set EDERS_SIMULATION_PORT"
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
    snapshot = await EdersClient().fetch_snapshot("fake-student", "fake-password")
    assert len(snapshot.activities) == 3 and [course.id for course in snapshot.courses] == [10]
    assert transports[0].paths.count(("POST", "/lib/ajax/service.php")) == 2
    assert ("GET", "/mod/assign/view.php") in transports[0].paths
    assert ("GET", "/mod/quiz/view.php") in transports[0].paths
    assert "fake-sso" not in serialize_snapshot(snapshot) and "fakekey" not in serialize_snapshot(snapshot)


@pytest.mark.parametrize("mode", ["html-error", "invalid-json"])
async def test_http_ajax_failure_never_returns_partial_snapshot(monkeypatch, mode):
    install_client(monkeypatch, mode)
    with pytest.raises(EdersFetchError):
        await EdersClient().fetch_snapshot("fake-student", "fake-password")


async def test_http_expired_session_retries_once(monkeypatch):
    transports = install_client(monkeypatch, "expired")
    with pytest.raises(EdersSessionExpiredError):
        await EdersClient().fetch_snapshot("fake-student", "fake-password")
    assert len(transports) == 2


def install_obis_client(monkeypatch, mode="normal"):
    transports = install_client(monkeypatch, mode)
    monkeypatch.setattr(client, "new_http_client", eders_client.new_http_client)
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
    service = ObisService(account, obis)
    await service.save_credentials(user.id, "fake-student", "fake-password")
    assert user.encrypted_password != "fake-password" and crypto.decrypt(user.encrypted_password) == "fake-password"
    grades = await service.get_exam_grades(user.id)
    attendance = await service.get_attendance(user.id)
    assert grades[0].exams[0].score == "80" and grades[0].lesson_code == "MATH"
    assert attendance[0].theory_skips_percentage == 12.5 and attendance[0].practice_skips_percentage == 6.25
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
