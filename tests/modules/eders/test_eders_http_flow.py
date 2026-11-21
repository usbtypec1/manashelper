"""Run with the local Postman simulation; never contacts real student accounts."""

import base64
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from manashelper.modules.eders.errors import EdersFetchError, EdersSessionExpiredError
from manashelper.modules.eders.infrastructure import client as eders_client
from manashelper.modules.eders.infrastructure.repositories.eders import EdersRepository
from manashelper.modules.eders.infrastructure.serialization import serialize_snapshot
from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.errors import (
    ObisLoginError,
    ObisManualLoginRequiredError,
    ObisParseError,
    ObisRetryLaterError,
)
from manashelper.modules.obis.infrastructure import client as obis_client
from manashelper.modules.obis.infrastructure.client import OBIS_BASE_URL, OBIS_HOST, ObisClient
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.repositories.credentials import ObisCredentialsRepository
from manashelper.modules.users.application.queries import UsersQuery
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from tests.modules.eders.application_factories import build_eders_service, build_eders_tracking_service
from tests.modules.eders.factories import make_eders_client
from tests.modules.gamification.factories import build_awards
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
    flow = uuid4().hex

    def factory(cookies=None):
        transport = SimulationTransport()
        transports.append(transport)
        client = httpx.AsyncClient(
            base_url=OBIS_BASE_URL,
            follow_redirects=True,
            transport=transport,
            headers={"x-fixture-mode": mode, "x-fixture-flow": flow},
            timeout=5,
        )
        for name, value in (cookies or {}).items():
            client.cookies.set(name, value, domain=OBIS_HOST)
        return client

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
    await make_eders_client().set_activity_completion("fake-student", 20, completed, {"obis": "fixture"})
    assert transports[0].paths[0] == ("GET", "/site/eders")
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


async def test_obis_http_explicit_login_uses_fresh_captcha_forms(monkeypatch):
    transports = install_obis_client(monkeypatch)
    client = ObisClient()
    for _ in range(2):
        challenge = await client.start_login()
        assert challenge.expected_hash == 3347 and challenge.captcha_image
        cookies = await client.complete_login(challenge.attempt, "fake-student", "fake-password", "qinug")
        assert cookies["obis"] == "fixture"
    assert len(transports) == 4
    assert all(
        transport.paths == expected
        for transport, expected in zip(
            transports,
            [
                [("GET", "/site/login"), ("GET", "/site/captcha")],
                [("POST", "/site/login"), ("GET", "/")],
            ]
            * 2,
            strict=True,
        )
    )


async def test_obis_http_credentials_grades_and_attendance_run_through_real_client(session, monkeypatch):
    transports = install_obis_client(monkeypatch)
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    user = User(id=975101, full_name="Fixture student")
    session.add(user)
    await session.flush()
    obis = ObisClient()
    service = build_obis(session, obis, crypto)
    await service.login(user.id, "fake-student", "fake-password", code="qinug")
    assert user.encrypted_password != "fake-password" and crypto.decrypt(user.encrypted_password) == "fake-password"
    grades = (await service.grades.execute(user.id)).lessons
    attendance = (await service.attendance.execute(user.id)).lessons
    assert grades[0].exams[0].score == "80" and grades[0].lesson_code == "MATH"
    assert attendance[0].theory_skips_percentage == 12.5 and attendance[0].practice_skips_percentage == 6.25
    assert (await service.results.get_exam_grades(user.id)).lessons == grades
    assert (await service.results.get_attendance(user.id)).lessons == attendance
    assert len(transports) == 4
    assert transports[2].paths == [("GET", "/vs-ders/taken-grades")]
    assert transports[3].paths == [("GET", "/vs-ders/taken-lessons")]


@pytest.mark.parametrize(
    "mode,error",
    [("login-denied", ObisLoginError), ("csrf-missing", ObisParseError), ("html-error", httpx.HTTPStatusError)],
)
async def test_obis_http_failure_preserves_error_type(monkeypatch, mode, error):
    install_obis_client(monkeypatch, mode)
    with pytest.raises(error):
        client = ObisClient()
        challenge = await client.start_login()
        cookies = await client.complete_login(challenge.attempt, "fake-student", "fake-password", "qinug")
        await client.fetch_exam_grades_html(cookies)


@pytest.mark.parametrize(
    "failure_mode,error", [("html-error", ObisRetryLaterError), ("transcript-malformed", ObisParseError)]
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
    obis = build_obis(session, ObisClient(), crypto)
    refresh = RefreshObisTranscriptUseCase(
        ObisCredentialsQuery(credentials, crypto),
        credentials,
        ObisResultsSource(ObisClient()),
        obis.access,
        RecordTranscriptUseCase(repo, build_awards(session)),
        GamificationQuery(repo),
    )
    await refresh.execute(user.id)
    await session.flush()
    before = await repo.academic_progress(user.id)
    assert before[0] and before[1] is not None and before[2] is not None
    assert set(await repo.get_awards(user.id)) == {"formula_one", "champion", "comeback"}
    assert [path for transport in transports for path in transport.paths] == [
        ("GET", "/site/login"),
        ("GET", "/site/captcha"),
        ("POST", "/site/login"),
        ("GET", "/"),
        ("GET", "/vs-ders/transkript-detailed"),
    ]
    install_obis_client(monkeypatch, failure_mode)
    with pytest.raises(error):
        await refresh.execute(user.id)
    assert await repo.academic_progress(user.id) == before


@pytest.mark.parametrize("mode", ["captcha-fifth-success", "captcha-rejected"])
async def test_obis_http_automatic_login_tries_five_fresh_captchas(session, monkeypatch, mode):
    transports = install_obis_client(monkeypatch, mode)
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    user = User(
        id=975107,
        full_name="Five captcha attempts",
        student_number="fake-student",
        encrypted_password=crypto.encrypt("fake-password"),
    )
    session.add(user)
    await session.flush()
    service = build_obis(session, ObisClient(), crypto)
    if mode == "captcha-fifth-success":
        assert await service.auto_login.execute(user.id) is None
        assert await service.sessions.has_session(user.id)
    else:
        manual = await service.auto_login.execute(user.id)
        assert manual is not None
        assert not await service.sessions.has_session(user.id)
    paths = [path for transport in transports for path in transport.paths]
    assert paths.count(("POST", "/site/login")) == 5
    assert paths.count(("GET", "/site/captcha")) == (6 if mode == "captcha-rejected" else 5)
    challenges = [
        transport.paths for transport in transports if transport.paths and transport.paths[0] == ("GET", "/site/login")
    ]
    assert len(challenges) == (6 if mode == "captcha-rejected" else 5)


async def test_obis_http_rotated_cookies_are_persisted_without_another_login(session, monkeypatch):
    transports = install_obis_client(monkeypatch, "cookie-rotation")
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    user = User(
        id=975108,
        full_name="Cookie rotation",
        student_number="fake-student",
        encrypted_password=crypto.encrypt("fake-password"),
    )
    session.add(user)
    await session.flush()
    service = build_obis(session, ObisClient(), crypto)
    await service.grades.execute(user.id)
    assert (await service.sessions.get_cookies(user.id))["obis"] == "rotated"
    await service.attendance.execute(user.id)
    assert [path for transport in transports for path in transport.paths].count(("POST", "/site/login")) == 1


async def test_obis_http_expired_saved_session_recovers_before_retrying_data(session, monkeypatch):
    transports = install_obis_client(monkeypatch)
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    user = User(
        id=975109,
        full_name="Expired saved session",
        student_number="fake-student",
        encrypted_password=crypto.encrypt("fake-password"),
    )
    session.add(user)
    await session.flush()
    service = build_obis(session, ObisClient(), crypto)
    await service.sessions.save(user.id, {"obis": "expired"})
    result = await service.grades.execute(user.id)
    assert result.lessons and (await service.sessions.get_cookies(user.id))["obis"] == "fixture"
    paths = [path for transport in transports for path in transport.paths]
    assert paths.count(("POST", "/site/login")) == 1
    assert paths.count(("GET", "/vs-ders/taken-grades")) == 2


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
    obis = build_obis(session, client, crypto)
    refresh = RefreshObisTranscriptUseCase(
        ObisCredentialsQuery(credentials, crypto),
        credentials,
        ObisResultsSource(client),
        obis.access,
        RecordTranscriptUseCase(repo, build_awards(session)),
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
    assert transports[2].paths == [("GET", "/vs-ders/transkript-detailed")]
    assert transports[3].paths == [("GET", "/vs-ders/taken-lessons")]
    install_obis_client(monkeypatch, "html-error")
    with pytest.raises(ObisRetryLaterError):
        await attendance.execute(user.id)
    assert await repo.attendance_progress(user.id) == before
    assert await repo.get_awards(user.id) == awards


@pytest.mark.parametrize(
    "mode", ["eders-login-denied", "eders-token-missing", "eders-login-unavailable", "eders-sso-link"]
)
async def test_http_failed_direct_login_falls_back_to_obis_sso(session, monkeypatch, mode):
    transports = install_obis_client(monkeypatch, mode)
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
    obis = build_obis(session, ObisClient(), crypto)
    await obis.sessions.save(user.id, {"obis": "fixture"})
    service = build_eders_service(account, make_eders_client(), tracking, obis_access=obis.access)
    snapshot = await service.refresh_snapshot(user.id)
    await session.flush()

    assert len(snapshot.activities) == 3
    assert await service.get_snapshot(user.id) == snapshot
    assert len(transports) == 2
    assert transports[0].paths[0] == ("GET", "/login/index.php")
    assert all(path == "/login/index.php" for _, path in transports[0].paths)
    assert transports[1].paths[:3] == [
        ("GET", "/site/eders"),
        ("GET", "/auth/userkey/login.php"),
        ("GET", "/my/index.php"),
    ]
    assert not any(path == "/site/login" for transport in transports for _, path in transport.paths)
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
    obis = build_obis(session, ObisClient(), crypto)
    service = build_eders_service(account, make_eders_client(), tracking, obis_access=obis.access)
    previous = await service.refresh_snapshot(user.id)
    await session.flush()
    if mode == "sso-expired":
        await obis.sessions.save(user.id, {"obis": "fixture"})
    transports = install_obis_client(monkeypatch, mode)
    with pytest.raises((EdersFetchError, ObisManualLoginRequiredError)):
        await service.refresh_snapshot(user.id)
    assert await service.get_snapshot(user.id) == previous
    assert len(transports) == 3
    assert not any(path == "/lib/ajax/service.php" for transport in transports for _, path in transport.paths)


async def test_browser_login_hands_native_key_to_separate_browser_without_exposing_obis_session(session, monkeypatch):
    from urllib.parse import urlsplit

    from pydantic import SecretStr

    from manashelper.core.config import Settings
    from manashelper.localization.locale import Locale
    from manashelper.modules.eders.application.browser_login import EdersLoginTokens
    from manashelper.modules.eders.application.use_cases.issue_eders_login_link import IssueEdersLoginLinkUseCase
    from manashelper.modules.eders.application.use_cases.redeem_eders_login_link import RedeemEdersLoginLinkUseCase
    from manashelper.modules.eders.errors import InvalidEdersLoginLinkError
    from manashelper.modules.users.application.queries import UsersQuery
    from manashelper.modules.users.infrastructure.repositories.user import UserRepository

    transports = install_client(monkeypatch, "browser-login")
    crypto = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(bytes(range(32))).decode()))
    user = User(
        id=975120,
        full_name="Browser fixture",
        student_number="fake-student",
        encrypted_password=crypto.encrypt("fake-password"),
    )
    session.add(user)
    await session.flush()
    credentials = ObisCredentialsRepository(session)
    obis = build_obis(session, ObisClient(), crypto)
    await obis.sessions.save(user.id, {"obis": "fixture"})
    tokens = EdersLoginTokens()
    config = Settings.model_construct(public_url="https://bot.example.com", eders_password=SecretStr("fake-password"))
    link = await IssueEdersLoginLinkUseCase(credentials, tokens, config).execute(user.id, Locale.RU)
    redeem = RedeemEdersLoginLinkUseCase(
        credentials, tokens, make_eders_client(), obis.access, UsersQuery(UserRepository(session))
    )
    destination = await redeem.execute(urlsplit(link).fragment)
    assert transports[0].paths == [("GET", "/site/eders")]
    assert await obis.sessions.get_cookies(user.id) == {"obis": "rotated"}
    with pytest.raises(InvalidEdersLoginLinkError):
        await redeem.execute(urlsplit(link).fragment)
    async with eders_client.new_http_client() as browser:
        response = await browser.get(destination)
        assert response.status_code == 200 and response.url.path == "/my/index.php"
        assert browser.cookies.get("MoodleSession") == "fixture"
        assert browser.cookies.get("obis") is None
        assert (await browser.get(destination)).status_code == 401
    assert transports[1].paths[:2] == [("GET", "/auth/userkey/login.php"), ("GET", "/my/index.php")]
