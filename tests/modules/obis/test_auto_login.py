import base64
import threading
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.models import ObisCaptcha, ObisLoginAttempt, PendingObisLogin, RefreshResult
from manashelper.modules.obis.application.ports import CaptchaRecognizer
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.application.use_cases.auto_login_obis import AutoLoginObisUseCase
from manashelper.modules.obis.application.use_cases.complete_obis_login import CompleteObisLoginUseCase
from manashelper.modules.obis.application.use_cases.poll_obis_user import PollObisUserUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_captcha import RefreshObisCaptchaUseCase
from manashelper.modules.obis.application.use_cases.start_obis_login import StartObisLoginUseCase
from manashelper.modules.obis.errors import ObisCaptchaError, ObisLoginError, ObisParseError, ObisSessionExpiredError
from manashelper.modules.obis.infrastructure import captcha
from manashelper.modules.obis.infrastructure.captcha import LocalCaptchaRecognizer
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.repositories.credentials import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.repositories.session import ObisSessionRepository
from manashelper.modules.obis.infrastructure.repositories.snapshot import ObisSnapshotRepository
from manashelper.modules.users.infrastructure.models.user import User
from tests.paths import FIXTURES_DIR

PENDING = PendingObisLogin("test-student", "encrypted-password", ObisLoginAttempt({"PHPSESSID": "first"}, "csrf-first"))
CHALLENGE = ObisCaptcha(PENDING, b"png-first", 3347)


@pytest.fixture
def auto():
    start = AsyncMock(spec=StartObisLoginUseCase)
    complete = AsyncMock(spec=CompleteObisLoginUseCase)
    refresh = AsyncMock(spec=RefreshObisCaptchaUseCase)
    recognizer = AsyncMock(spec=CaptchaRecognizer)
    start.execute.return_value = CHALLENGE
    recognizer.solve.return_value = "qinug"
    sequence = []

    async def fresh(pending):
        attempt = ObisLoginAttempt({"PHPSESSID": f"form-{len(sequence)}"}, f"csrf-{len(sequence)}")
        challenge = ObisCaptcha(replace(pending, attempt=attempt), f"png-{len(sequence)}".encode(), 3347)
        sequence.append(challenge)
        return challenge

    refresh.execute.side_effect = fresh
    return SimpleNamespace(
        service=AutoLoginObisUseCase(start, complete, refresh, recognizer),
        start=start,
        complete=complete,
        refresh=refresh,
        recognizer=recognizer,
        refreshed=sequence,
    )


async def test_auto_login_completes_the_same_form_and_returns_no_manual_challenge(auto):
    assert await auto.service.execute(123, "student", "password") is None
    auto.start.execute.assert_awaited_once_with(123, "student", "password")
    auto.recognizer.solve.assert_awaited_once_with(b"png-first", 3347)
    auto.complete.execute.assert_awaited_once_with(123, PENDING, "qinug")
    auto.refresh.execute.assert_not_awaited()


async def test_missing_hash_keeps_unsubmitted_manual_challenge(auto):
    captcha = replace(CHALLENGE, expected_hash=None)
    auto.start.execute.return_value = captcha
    assert await auto.service.execute(123) is captcha
    auto.recognizer.solve.assert_not_awaited()
    auto.complete.execute.assert_not_awaited()


async def test_uncertain_answer_fetches_another_challenge_without_submitting(auto):
    auto.recognizer.solve.side_effect = [None, "qinug"]
    assert await auto.service.execute(123) is None
    auto.complete.execute.assert_awaited_once_with(123, auto.refreshed[0].pending, "qinug")
    assert auto.refreshed[0].pending.attempt != PENDING.attempt


async def test_rejected_captchas_have_a_bounded_post_count_and_fresh_manual_fallback(auto):
    auto.complete.execute.side_effect = ObisCaptchaError()
    fallback = await auto.service.execute(123)
    assert auto.complete.execute.await_count == 3
    assert auto.refresh.execute.await_count == 3
    submitted = [call.args[1] for call in auto.complete.execute.await_args_list]
    assert len({pending.attempt.csrf_token for pending in submitted}) == 3
    assert fallback is auto.refreshed[-1] and fallback.pending not in submitted


async def test_three_uncertain_answers_do_not_make_any_login_posts(auto):
    auto.recognizer.solve.return_value = None
    fallback = await auto.service.execute(123)
    assert fallback is auto.refreshed[-1]
    assert auto.recognizer.solve.await_count == 3 and auto.refresh.execute.await_count == 2
    auto.complete.execute.assert_not_awaited()


@pytest.mark.parametrize("error", [ObisLoginError(), ObisParseError(), httpx.ReadTimeout("timeout")])
async def test_credential_and_unknown_outcomes_never_retry_a_post(auto, error):
    auto.complete.execute.side_effect = error
    with pytest.raises(type(error)):
        await auto.service.execute(123)
    auto.complete.execute.assert_awaited_once()
    auto.refresh.execute.assert_not_awaited()


async def test_local_recognizer_offloads_cpu_and_preserves_abstention(monkeypatch):
    recognizer = LocalCaptchaRecognizer()
    main_thread = threading.get_ident()
    threads = []

    def solve(image, expected_hash):
        threads.append(threading.get_ident())
        return None

    monkeypatch.setattr(captcha, "solve", solve)
    assert await recognizer.solve(b"image", 3347) is None
    assert threads and threads[0] != main_thread


async def test_poll_recovers_expired_session_and_resumes_refresh_without_a_reminder():
    grades, attendance, transcript, sessions, login, sender = [AsyncMock() for _ in range(6)]
    grades.execute.side_effect = [ObisSessionExpiredError(), RefreshResult([], ["grade"])]
    attendance.execute.return_value = RefreshResult([], ["skip"])
    login.execute.return_value = None
    await PollObisUserUseCase(grades, attendance, transcript, sessions, login).execute(123, True, True, sender)
    login.execute.assert_awaited_once_with(123)
    assert grades.execute.await_count == 2
    sender.exam_grade_changed.assert_awaited_once_with("grade")
    sender.lesson_skips_changed.assert_awaited_once_with("skip")
    sessions.expire.assert_not_awaited()
    sender.session_expired.assert_not_awaited()


async def test_poll_transport_failure_preserves_session_and_does_not_repeat_login():
    grades, attendance, transcript, sessions, login, sender = [AsyncMock() for _ in range(6)]
    grades.execute.side_effect = ObisSessionExpiredError()
    login.execute.side_effect = httpx.ReadTimeout("timeout")
    with pytest.raises(httpx.ReadTimeout):
        await PollObisUserUseCase(grades, attendance, transcript, sessions, login).execute(123, True, True, sender)
    login.execute.assert_awaited_once()
    sessions.expire.assert_not_awaited()
    sender.session_expired.assert_not_awaited()


async def test_real_solver_form_cookies_and_encrypted_database_login(session, monkeypatch):
    """Real library and PostgreSQL; only the external site is replaced by a deterministic transport."""
    requests = []
    image = (FIXTURES_DIR / "obis/auto-captcha.png").read_bytes()
    page = (FIXTURES_DIR / "obis/login.html").read_text(encoding="utf-8").replace("{captcha_error}", "")
    page += '<script>yii.validation.captcha(value, messages, {"hash":3347,"caseSensitive":false});</script>'

    def handler(request):
        requests.append(request)
        if request.method == "GET" and request.url.path == "/site/login":
            return httpx.Response(200, text=page, headers={"set-cookie": "PHPSESSID=form; path=/; secure"})
        if request.url.path == "/site/captcha":
            assert "PHPSESSID=form" in request.headers["cookie"]
            return httpx.Response(200, content=image, headers={"content-type": "image/png"})
        if request.method == "POST":
            assert "PHPSESSID=form" in request.headers["cookie"]
            form = dict(httpx.QueryParams(request.content.decode()))
            assert form["LoginForm[verifyCode]"] == "qinug" and form["_csrf"] == "fixture-csrf-token"
            assert form["LoginForm[username]"] == "student" and form["LoginForm[password_hash]"] == "password"
            return httpx.Response(
                302, headers={"location": "/", "set-cookie": "PHPSESSID=authenticated; path=/; secure"}
            )
        return httpx.Response(200, text='<form action="/site/logout" method="post"></form>')

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    user = User(id=978900, full_name="Automatic login test")
    session.add(user)
    await session.flush()
    cipher = CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(AESGCM.generate_key(256)).decode()))
    store = ObisCredentialsRepository(session)
    account = ObisCredentialsQuery(store, cipher)
    sessions = ObisSessions(ObisSessionRepository(session), cipher)
    client = ObisClient()
    service = AutoLoginObisUseCase(
        StartObisLoginUseCase(account, client, cipher),
        CompleteObisLoginUseCase(account, store, client, cipher, ObisSnapshotRepository(session), sessions),
        RefreshObisCaptchaUseCase(client),
        LocalCaptchaRecognizer(),
    )
    assert await service.execute(user.id, "student", "password") is None
    await session.flush()
    assert user.student_number == "student" and cipher.decrypt(user.encrypted_password) == "password"
    assert await sessions.get_cookies(user.id) == {"PHPSESSID": "authenticated"}
    assert sum(request.method == "POST" for request in requests) == 1
