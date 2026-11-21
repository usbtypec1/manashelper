import base64
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.models import ObisCaptcha, ObisLoginAttempt, PendingObisLogin
from manashelper.modules.obis.application.ports import CaptchaRecognizer
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.application.use_cases.auto_login_obis import AutoLoginObisUseCase
from manashelper.modules.obis.application.use_cases.complete_obis_login import CompleteObisLoginUseCase
from manashelper.modules.obis.application.use_cases.poll_obis_user import PollObisUserUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_captcha import RefreshObisCaptchaUseCase
from manashelper.modules.obis.application.use_cases.start_obis_login import StartObisLoginUseCase
from manashelper.modules.obis.errors import (
    ObisCaptchaError,
    ObisLoginError,
    ObisManualLoginRequiredError,
    ObisParseError,
    ObisRetryLaterError,
)
from manashelper.modules.obis.infrastructure.captcha import LocalCaptchaRecognizer
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.repositories.auth_state import ObisAuthStateRepository
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
    progress = AsyncMock()
    assert await auto.service.execute(123, on_recognition_started=progress) is captcha
    progress.assert_not_awaited()
    auto.recognizer.solve.assert_not_awaited()
    auto.complete.execute.assert_not_awaited()


async def test_uncertain_answer_fetches_another_challenge_without_submitting(auto):
    progress = AsyncMock()
    answers = iter((None, "qinug"))

    async def solve(*args):
        progress.assert_awaited_once()
        return next(answers)

    auto.recognizer.solve.side_effect = solve
    assert await auto.service.execute(123, on_recognition_started=progress) is None
    auto.complete.execute.assert_awaited_once_with(123, auto.refreshed[0].pending, "qinug")
    assert auto.refreshed[0].pending.attempt != PENDING.attempt


async def test_rejected_captchas_have_a_bounded_post_count_and_fresh_manual_fallback(auto):
    auto.complete.execute.side_effect = ObisCaptchaError()
    fallback = await auto.service.execute(123)
    assert auto.complete.execute.await_count == 5
    assert auto.refresh.execute.await_count == 5
    submitted = [call.args[1] for call in auto.complete.execute.await_args_list]
    assert len({pending.attempt.csrf_token for pending in submitted}) == 5
    assert len({pending.attempt.cookies["PHPSESSID"] for pending in submitted}) == 5
    assert fallback is auto.refreshed[-1] and fallback.pending not in submitted


async def test_five_uncertain_answers_do_not_make_any_login_posts(auto):
    auto.recognizer.solve.return_value = None
    fallback = await auto.service.execute(123)
    assert fallback is auto.refreshed[-1]
    assert auto.recognizer.solve.await_count == 5 and auto.refresh.execute.await_count == 4
    auto.complete.execute.assert_not_awaited()


@pytest.mark.parametrize("rejected", [False, True])
async def test_auto_login_can_succeed_on_the_fifth_fresh_captcha(auto, rejected):
    if rejected:
        auto.complete.execute.side_effect = [ObisCaptchaError() for _ in range(4)] + [None]
    else:
        auto.recognizer.solve.side_effect = [None, None, None, None, "qinug"]
    assert await auto.service.execute(123) is None
    assert auto.refresh.execute.await_count == 4
    assert auto.recognizer.solve.await_count == 5
    assert auto.complete.execute.await_count == (5 if rejected else 1)
    assert auto.complete.execute.await_args.args[1] is auto.refreshed[-1].pending
    images = [call.args[0] for call in auto.recognizer.solve.await_args_list]
    assert len(set(images)) == 5


@pytest.mark.parametrize("error", [ObisLoginError(), ObisParseError(), httpx.ReadTimeout("timeout")])
async def test_credential_and_unknown_outcomes_never_retry_a_post(auto, error):
    auto.complete.execute.side_effect = error
    with pytest.raises(type(error)):
        await auto.service.execute(123)
    auto.complete.execute.assert_awaited_once()
    auto.refresh.execute.assert_not_awaited()


@pytest.mark.parametrize("notify", [False, True])
async def test_poll_consumes_manual_outcome_and_only_sends_a_claimed_notice(notify):
    grades, attendance, transcript, access, sender = [AsyncMock() for _ in range(5)]
    grades.execute.side_effect = ObisManualLoginRequiredError()
    access.claim_manual_login_notice.return_value = notify
    await PollObisUserUseCase(grades, attendance, transcript, access).execute(123, True, True, sender)
    access.claim_manual_login_notice.assert_awaited_once_with(123)
    assert sender.session_expired.await_count == int(notify)
    attendance.execute.assert_not_awaited()
    transcript.execute.assert_not_awaited()


async def test_poll_consumes_deferred_outcome_without_requesting_manual_login():
    grades, attendance, transcript, access, sender = [AsyncMock() for _ in range(5)]
    grades.execute.side_effect = ObisRetryLaterError()
    await PollObisUserUseCase(grades, attendance, transcript, access).execute(123, True, True, sender)
    access.claim_manual_login_notice.assert_not_awaited()
    sender.session_expired.assert_not_awaited()
    attendance.execute.assert_not_awaited()
    transcript.execute.assert_not_awaited()


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
        StartObisLoginUseCase(account, client, cipher, store),
        CompleteObisLoginUseCase(
            account, store, client, cipher, ObisSnapshotRepository(session), sessions, ObisAuthStateRepository(session)
        ),
        RefreshObisCaptchaUseCase(client),
        LocalCaptchaRecognizer(),
    )
    assert await service.execute(user.id, "student", "password") is None
    await session.flush()
    assert user.student_number == "student" and cipher.decrypt(user.encrypted_password) == "password"
    assert await sessions.get_cookies(user.id) == {"PHPSESSID": "authenticated"}
    assert sum(request.method == "POST" for request in requests) == 1
