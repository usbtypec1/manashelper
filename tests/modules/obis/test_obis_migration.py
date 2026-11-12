import base64
import hashlib
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, User
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dishka import make_async_container

from manashelper.core.database import Base
from manashelper.core.provider import CoreProvider
from manashelper.jobs.scheduler import create_scheduler
from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.gamification.provider import GamificationProvider
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.obis import jobs
from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.models import (
    ExamModel,
    LessonAttendanceModel,
    LessonExamsModel,
    ObisCaptcha,
    ObisLoginAttempt,
    PendingObisLogin,
    RefreshResult,
)
from manashelper.modules.obis.application.notification import (
    ExamGradeChange,
    LessonSkipChange,
    SkipType,
)
from manashelper.modules.obis.application.ports import (
    AttendanceStore,
    CredentialsStore,
    ExamGradeStore,
    ObisAuthenticator,
    PasswordCipher,
    ResultsSource,
    SessionStore,
    SnapshotStore,
)
from manashelper.modules.obis.application.queries import ObisResultsQuery
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.application.use_cases.clear_obis_credentials import ClearObisCredentialsUseCase
from manashelper.modules.obis.application.use_cases.complete_obis_login import CompleteObisLoginUseCase
from manashelper.modules.obis.application.use_cases.poll_obis_user import PollObisUserUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_attendance import RefreshObisAttendanceUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_captcha import RefreshObisCaptchaUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_grades import RefreshObisGradesUseCase
from manashelper.modules.obis.application.use_cases.start_obis_login import StartObisLoginUseCase
from manashelper.modules.obis.errors import (
    DecryptionError,
    ObisCaptchaError,
    ObisLoginError,
    ObisParseError,
    ObisSessionExpiredError,
    UserHasNoCredentialsError,
    UserNotFoundError,
)
from manashelper.modules.obis.infrastructure import crypto as crypto_module
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.repositories.credentials import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.repositories.session import ObisSessionRepository
from manashelper.modules.obis.infrastructure.repositories.user_exam_grade import UserExamGradeRepository
from manashelper.modules.obis.infrastructure.repositories.user_lesson_attendance import UserLessonAttendanceRepository
from manashelper.modules.obis.presentation import router as router
from manashelper.modules.obis.presentation.callbacks import ObisAction, ObisCallback, ObisResultsPageCallback
from manashelper.modules.obis.presentation.formatter import format_exam_grade_change
from manashelper.modules.obis.presentation.keyboards import build_login_keyboard
from manashelper.modules.obis.presentation.sender import TelegramObisNotificationSender
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.users.infrastructure.models.user import User as DbUser
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.outbox.provider import OutboxProvider
from tests.modules.eders.application_factories import build_eders_service
from tests.modules.obis.factories import build_obis

KEY = bytes(range(32))


@pytest.fixture
def crypto():
    return CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(KEY).decode()))


@pytest.fixture
def credentials(session, crypto):
    client = AsyncMock(spec=ObisClient)
    return build_obis(session, client, crypto)


async def test_credentials_verify_before_storage_and_keep_cipher_format(session, credentials, crypto):
    old = crypto.encrypt("old password")
    user = DbUser(id=975001, full_name="Student", student_number="old", encrypted_password=old)
    session.add(user)
    await session.flush()

    async def verify(attempt, student_number, password, code):
        assert (student_number, password, code) == ("new", "fake-password", "code")
        assert (user.student_number, user.encrypted_password) == ("old", old)
        return {"PHPSESSID": "fake-session"}

    credentials.client.complete_login.side_effect = verify
    await credentials.login(975001, "new", "fake-password")
    assert user.student_number == "new" and crypto.decrypt(user.encrypted_password) == "fake-password"
    assert len(base64.b64decode(user.encrypted_password)) == 12 + len("fake-password") + 16
    assert await credentials.account.has_credentials(975001)
    await credentials.clear.execute(975001)
    assert (user.student_number, user.encrypted_password) == (None, None)
    assert not await credentials.account.has_credentials(975001)


@pytest.mark.parametrize("operation", ["save", "has", "clear"])
async def test_unknown_user_never_attempts_login(credentials, operation):
    with pytest.raises(UserNotFoundError) as error:
        if operation == "save":
            await credentials.login(975001, "fake-student", "fake-password")
        elif operation == "has":
            await credentials.account.has_credentials(975001)
        else:
            await credentials.clear.execute(975001)
    assert error.value.user_id == 975001
    credentials.client.start_login.assert_not_awaited()
    credentials.client.complete_login.assert_not_awaited()


async def test_failed_login_does_not_replace_existing_credentials(session, credentials):
    user = DbUser(id=975001, full_name="Student", student_number="old", encrypted_password="old-ciphertext")
    session.add(user)
    await session.flush()
    credentials.client.complete_login.side_effect = ObisLoginError("denied")
    with pytest.raises(ObisLoginError):
        await credentials.login(975001, "new", "fake-password")
    assert not await credentials.sessions.has_session(975001)
    assert (user.student_number, user.encrypted_password) == ("old", "old-ciphertext")
    await session.commit()
    await session.refresh(user)
    assert (user.student_number, user.encrypted_password) == ("old", "old-ciphertext")


async def test_encryption_failure_does_not_replace_existing_credentials(session, credentials, crypto, monkeypatch):
    user = DbUser(id=975001, full_name="Student", student_number="old", encrypted_password="old-ciphertext")
    session.add(user)
    await session.flush()

    def fail(_):
        raise RuntimeError("Encryption unavailable")

    monkeypatch.setattr(crypto, "encrypt", fail)
    with pytest.raises(RuntimeError, match="Encryption unavailable"):
        await credentials.login(975001, "new", "fake-password")
    credentials.client.start_login.assert_not_awaited()
    assert (user.student_number, user.encrypted_password) == ("old", "old-ciphertext")
    await session.commit()
    await session.refresh(user)
    assert (user.student_number, user.encrypted_password) == ("old", "old-ciphertext")


@pytest.mark.parametrize("ciphertext", [None, "not-ciphertext"])
async def test_missing_or_corrupt_credentials_never_fetch_data(session, credentials, ciphertext):
    session.add(DbUser(id=975001, full_name="Student", student_number="fake-student", encrypted_password=ciphertext))
    await session.flush()
    with pytest.raises(UserHasNoCredentialsError) as error:
        await credentials.results.get_exam_grades(975001)
    assert (error.value.__cause__ is not None) is (ciphertext is not None)
    credentials.client.fetch_exam_grades_html.assert_not_awaited()


def test_aes_gcm_legacy_wire_format_and_random_nonce(crypto, monkeypatch):
    one, two = crypto.encrypt("пароль"), crypto.encrypt("пароль")
    assert one != two and crypto.decrypt(one) == "пароль"
    nonce = bytes(range(12))
    legacy = base64.b64encode(nonce + AESGCM(KEY).encrypt(nonce, "пароль".encode(), None)).decode()
    assert crypto.decrypt(legacy) == "пароль"
    monkeypatch.setattr(crypto_module.os, "urandom", lambda size: nonce)
    assert crypto.encrypt("пароль") == legacy


@pytest.mark.parametrize("ciphertext", ["", "invalid", "AA=="])
def test_crypto_errors_keep_generic_message_without_plaintext(crypto, ciphertext):
    with pytest.raises(DecryptionError, match="^Failed to decrypt value$"):
        crypto.decrypt(ciphertext)


@pytest.mark.parametrize("score", [None, "80"])
async def test_first_grade_snapshot_is_silent_and_subsequent_changes_notify(session, score):
    session.add(DbUser(id=975001, full_name="Student"))
    await session.flush()
    source = AsyncMock()
    source.fetch_exam_grades.return_value = [LessonExamsModel("Math", "MATH", [ExamModel("Midterm", score)])]
    account = AsyncMock(spec=ObisCredentialsQuery)
    account.get_credentials.return_value = SimpleNamespace(
        student_number="student", plain_password="password", credential_marker="marker"
    )
    service = RefreshObisGradesUseCase(
        account, AsyncMock(), source, AsyncMock(), AsyncMock(), UserExamGradeRepository(session)
    )
    first = (await service.execute(975001)).changes
    assert first == []
    await session.flush()
    saved = await UserExamGradeRepository(session).get_all_by_user_id(975001)
    assert [(grade.lesson_code, grade.exam_name, grade.score) for grade in saved] == [("MATH", "Midterm", score)]
    assert (await service.execute(975001)).changes == []
    source.fetch_exam_grades.return_value = [LessonExamsModel("Math", "MATH", [ExamModel("Midterm", None)])]
    assert (await service.execute(975001)).changes == []
    source.fetch_exam_grades.return_value = [LessonExamsModel("Math", "MATH", [ExamModel("Midterm", "85")])]
    assert [change.score for change in (await service.execute(975001)).changes] == ["85"]
    source.fetch_exam_grades.return_value = [
        LessonExamsModel("Math", "MATH", [ExamModel("Midterm", "85"), ExamModel("Final", "90")])
    ]
    assert [(change.exam_name, change.score) for change in (await service.execute(975001)).changes] == [("Final", "90")]
    await session.flush()
    assert (await service.execute(975001)).changes == []


async def test_attendance_baseline_is_silent_and_only_known_increases_notify(session):
    session.add(DbUser(id=975001, full_name="Student"))
    await session.flush()
    source = AsyncMock()
    source.fetch_attendance.return_value = [LessonAttendanceModel("Math", "MATH", 12.5, None, 2, None)]
    account = AsyncMock(spec=ObisCredentialsQuery)
    account.get_credentials.return_value = SimpleNamespace(
        student_number="student", plain_password="password", credential_marker="marker"
    )
    service = RefreshObisAttendanceUseCase(
        account, AsyncMock(), source, AsyncMock(), AsyncMock(), UserLessonAttendanceRepository(session), AsyncMock()
    )
    assert (await service.execute(975001)).changes == []
    await session.flush()
    source.fetch_attendance.return_value = [LessonAttendanceModel("Math", "MATH", 18.75, 6.25, 1, 2)]
    changes = (await service.execute(975001)).changes
    assert [(change.skip_type, change.skips_percentage) for change in changes] == [(SkipType.THEORY, 18.75)]
    source.fetch_attendance.return_value = [LessonAttendanceModel("Math", "MATH", 0, None, 4, None)]
    assert (await service.execute(975001)).changes == []


def test_obis_callbacks_fsm_private_and_password_mask_contract():
    assert ObisCallback(action=ObisAction.ACCEPT_TERMS).pack() == "obis:accept_terms"
    assert ObisResultsPageCallback(page=2).pack() == "obis_results_page:2"
    assert router.ObisCredentialsForm.student_number.state == "ObisCredentialsForm:student_number"
    assert router.ObisCredentialsForm.password.state == "ObisCredentialsForm:password"
    assert router.ObisCredentialsForm.captcha.state == "ObisCredentialsForm:captcha"
    assert ObisCallback(action=ObisAction.LOGIN).pack() == "obis:login"
    handlers = router.router.message.handlers + router.router.callback_query.handlers
    assert all(handler.flags["private_chat_only"] for handler in handlers)
    password = next(handler for handler in handlers if handler.callback.__name__ == "on_password_entered")
    assert password.flags["mask_logged_message"]


def _form_context(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    user = User(id=975001, is_bot=False, first_name="Student")
    message = Message(message_id=1, date=0, chat=Chat(id=user.id, type="private"), from_user=user).as_(bot)
    callback = CallbackQuery(id="obis", from_user=user, message=message, chat_instance="chat").as_(bot)
    request = AsyncMock(return_value=message)
    monkeypatch.setattr(bot.session, "make_request", request)
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=bot.id, chat_id=user.id, user_id=user.id))
    return user, message, callback, request, state


PENDING = PendingObisLogin("fake-student", "fake-ciphertext", ObisLoginAttempt({"PHPSESSID": "form"}, "csrf"))


@pytest.mark.parametrize("failure", [None, "unavailable", "missing"])
async def test_credentials_form_deletes_password_and_opens_captcha(monkeypatch, failure):
    user, message, callback, request, state = _form_context(monkeypatch)
    service = AsyncMock()
    service.execute.return_value = ObisCaptcha(PENDING, b"captcha-png")
    if failure:
        service.execute.side_effect = httpx.ConnectError("down") if failure == "unavailable" else UserNotFoundError(1)
    with i18n.context(), i18n.use_locale("en"):
        await router.on_accept_terms(callback, state)
        await router.on_student_number_entered(message.model_copy(update={"text": " fake-student "}), state)
        assert await state.get_state() == "ObisCredentialsForm:password"
        request.reset_mock()
        await router.on_password_entered(message.model_copy(update={"text": " fake-password "}), state, service)
    service.execute.assert_awaited_once_with(user.id, "fake-student", "fake-password")
    methods = [call.args[1] for call in request.await_args_list]
    assert methods[0].__api_method__ == "deleteMessage"
    assert all("fake-password" not in str(method.model_dump()) for method in methods)
    if failure:
        assert await state.get_state() is None
        return
    assert await state.get_state() == "ObisCredentialsForm:captcha"
    assert router.load_pending_login(await state.get_data()) == PENDING
    assert methods[-1].__api_method__ == "sendPhoto"


@pytest.mark.parametrize("failure", [None, "captcha", "login"])
async def test_captcha_answer_completes_login_or_shows_new_captcha(monkeypatch, failure):
    user, message, _, request, state = _form_context(monkeypatch)
    await state.set_state(router.ObisCredentialsForm.captcha)
    await state.update_data({router.PENDING_LOGIN_KEY: router.pending_login_data(PENDING)})
    complete, refresh = AsyncMock(), AsyncMock()
    if failure:
        complete.execute.side_effect = ObisCaptchaError if failure == "captcha" else ObisLoginError
    renewed = PendingObisLogin("fake-student", "fake-ciphertext", ObisLoginAttempt({"PHPSESSID": "new"}, "csrf2"))
    refresh.execute.return_value = ObisCaptcha(renewed, b"new-png")
    with i18n.context(), i18n.use_locale("en"):
        await router.on_captcha_entered(message.model_copy(update={"text": " Ab3x9 "}), state, complete, refresh)
        expected_text = {None: "obis.logged_in", "captcha": "obis.captcha_invalid", "login": "obis.login_failed"}
        sent = request.await_args.args[1]
        assert (sent.caption if failure == "captcha" else sent.text) == i18n.gettext(expected_text[failure])
    complete.execute.assert_awaited_once_with(user.id, PENDING, "Ab3x9")
    if failure == "captcha":
        refresh.execute.assert_awaited_once_with(PENDING)
        assert await state.get_state() == "ObisCredentialsForm:captcha"
        assert router.load_pending_login(await state.get_data()) == renewed
    else:
        refresh.execute.assert_not_awaited()
        expected_state = "ObisCredentialsForm:student_number" if failure == "login" else None
        assert await state.get_state() == expected_state


async def test_login_button_reuses_saved_account_and_reports_missing_credentials(monkeypatch):
    user, _, callback, request, state = _form_context(monkeypatch)
    service = AsyncMock()
    service.execute.return_value = ObisCaptcha(PENDING, b"captcha-png")
    with i18n.context(), i18n.use_locale("en"):
        await router.on_login(callback, state, service)
        service.execute.assert_awaited_once_with(user.id)
        assert await state.get_state() == "ObisCredentialsForm:captcha"
        assert request.await_args.args[1].__api_method__ == "sendPhoto"

        await state.clear()
        service.execute.side_effect = UserHasNoCredentialsError(user.id)
        await router.on_login(callback, state, service)
        assert request.await_args.args[1].text == i18n.gettext("obis.credentials_missing")
    assert await state.get_state() is None


async def test_public_credentials_keep_ciphertext_marker_and_hide_secrets(session, credentials, crypto):
    user = DbUser(
        id=975001,
        full_name="Student",
        student_number="fake-student",
        encrypted_password=crypto.encrypt("fake-password"),
    )
    session.add(user)
    await session.flush()
    account = await credentials.account.get_credentials(user.id)
    assert account.student_number == "fake-student" and account.plain_password == "fake-password"
    assert account.credential_marker == hashlib.sha256(user.encrypted_password.encode()).hexdigest()
    assert all(
        secret not in repr(account)
        for secret in (account.student_number, account.plain_password, account.credential_marker)
    )
    client, tracking = AsyncMock(), AsyncMock()
    snapshot = object()
    client.fetch_snapshot.return_value = snapshot
    tracking.observe.return_value = snapshot
    assert await build_eders_service(credentials.account, client, tracking).refresh_snapshot(user.id) is snapshot
    client.fetch_snapshot.assert_awaited_once_with("fake-student")
    tracking.observe.assert_awaited_once_with(user.id, hashlib.sha256(b"fake-student").hexdigest(), snapshot)
    credentials.client.start_login.assert_not_awaited()


@pytest.mark.parametrize("mode", ["unknown", "missing", "empty"])
async def test_eders_missing_student_number_never_fetches(session, credentials, mode):
    if mode != "unknown":
        session.add(
            DbUser(
                id=975001,
                full_name="Student",
                student_number=None if mode == "missing" else "",
            )
        )
        await session.flush()
    client, tracking = AsyncMock(), AsyncMock()
    expected = UserNotFoundError if mode == "unknown" else UserHasNoCredentialsError
    with pytest.raises(expected) as error:
        await build_eders_service(credentials.account, client, tracking).refresh_snapshot(975001)
    assert error.value.__cause__ is None
    tracking.get_settings.assert_awaited_once_with(975001)
    client.fetch_snapshot.assert_not_awaited()
    tracking.observe.assert_not_awaited()


async def test_eders_checks_tracking_before_reading_credentials():
    account, client, tracking = AsyncMock(), AsyncMock(), AsyncMock()
    tracking.get_settings.side_effect = RuntimeError("Tracking failed")
    with pytest.raises(RuntimeError, match="Tracking failed"):
        await build_eders_service(account, client, tracking).refresh_snapshot(975001)
    account.get_student_number.assert_not_awaited()
    client.fetch_snapshot.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [
        None,
        UserNotFoundError(975001),
        UserHasNoCredentialsError(975001),
        ObisLoginError("denied"),
        ObisParseError("invalid markup"),
        httpx.ReadTimeout("timeout"),
        RuntimeError("unexpected"),
    ],
)
async def test_polling_use_case_keeps_expected_error_suppression_and_unexpected_abort(error):
    grades = AsyncMock(spec=RefreshObisGradesUseCase)
    attendance = AsyncMock(spec=RefreshObisAttendanceUseCase)
    grades.execute.return_value = RefreshResult([], ["grade"])
    attendance.execute.return_value = RefreshResult([], ["skip"])
    grades.execute.side_effect = error
    sender = AsyncMock()
    polling = PollObisUserUseCase(grades, attendance, AsyncMock(), AsyncMock())
    if isinstance(error, (httpx.HTTPError, RuntimeError)):
        with pytest.raises(type(error)):
            await polling.execute(975001, True, True, sender)
        attendance.execute.assert_not_awaited()
        sender.lesson_skips_changed.assert_not_awaited()
    else:
        await polling.execute(975001, True, True, sender)
        attendance.execute.assert_awaited_once_with(975001)
        sender.lesson_skips_changed.assert_awaited_once_with("skip")
    assert sender.exam_grade_changed.await_count == int(error is None)


@pytest.mark.parametrize("failure", [False, True])
async def test_telegram_sender_keeps_recipient_locale_and_queue_failure_boundary(failure):
    grades = AsyncMock(spec=RefreshObisGradesUseCase)
    attendance = AsyncMock(spec=RefreshObisAttendanceUseCase)
    grades.execute.return_value = RefreshResult(
        [],
        [
            ExamGradeChange("Math", "Midterm", "80"),
            ExamGradeChange("Math", "Final", "90"),
        ],
    )
    attendance.execute.return_value = RefreshResult([], [LessonSkipChange("Math", SkipType.THEORY, 25, 0)])
    bot = AsyncMock()
    if failure:
        bot.enqueue.side_effect = RuntimeError("Queue failed")
    sender = TelegramObisNotificationSender(bot, 975001, Locale.ZH, Theme.BASIC)
    with i18n.context(), i18n.use_locale("ru"):
        if not failure:
            await PollObisUserUseCase(grades, attendance, AsyncMock(), AsyncMock()).execute(975001, True, True, sender)
            assert bot.enqueue.await_count == 3
            assert all("Math" in call.args[1][0].text for call in bot.enqueue.await_args_list)
            with i18n.use_locale("zh"):
                expected = format_exam_grade_change(grades.execute.return_value.changes[0])
            assert bot.enqueue.await_args_list[0].args[1][0].text == expected
        else:
            with pytest.raises(RuntimeError, match="Queue failed"):
                await PollObisUserUseCase(grades, attendance, AsyncMock(), AsyncMock()).execute(
                    975001, True, True, sender
                )
            assert bot.enqueue.await_count == 1
            attendance.execute.assert_not_awaited()
        assert i18n.current_locale == "ru"


async def test_obis_provider_preserves_app_request_scopes_and_model_registry():
    from manashelper.modules.obis.infrastructure.models.user_exam_grade import UserExamGrade
    from manashelper.modules.obis.infrastructure.models.user_lesson_attendance import UserLessonAttendance

    assert Base.metadata.tables["obis_user_exam_grades"] is UserExamGrade.__table__
    assert Base.metadata.tables["obis_user_lesson_attendance"] is UserLessonAttendance.__table__
    dependencies = (
        ObisCredentialsRepository,
        ObisCredentialsQuery,
        ObisResultsQuery,
        RefreshObisGradesUseCase,
        RefreshObisAttendanceUseCase,
        StartObisLoginUseCase,
        RefreshObisCaptchaUseCase,
        CompleteObisLoginUseCase,
        ClearObisCredentialsUseCase,
        ObisSessions,
        ObisSessionRepository,
        SessionStore,
        UserExamGradeRepository,
        UserLessonAttendanceRepository,
        PollObisUserUseCase,
        SnapshotStore,
        CredentialsStore,
        ExamGradeStore,
        AttendanceStore,
    )
    async with make_async_container(
        CoreProvider(),
        ObisProvider(),
        GamificationProvider(),
        UsersProvider(),
        OutboxProvider(),
        NotificationsProvider(),
    ) as container:
        client, crypto = await container.get(ObisClient), await container.get(CryptoService)
        source = await container.get(ResultsSource)
        async with container() as request:
            first = [await request.get(dependency) for dependency in dependencies]
            for dependency, instance in zip(dependencies, first, strict=True):
                assert instance is await request.get(dependency)
            assert client is await request.get(ObisClient) and crypto is await request.get(CryptoService)
            assert source is await request.get(ResultsSource)
            assert await request.get(CredentialsStore) is await request.get(ObisCredentialsRepository)
            assert await request.get(SessionStore) is await request.get(ObisSessionRepository)
            assert await request.get(ExamGradeStore) is await request.get(UserExamGradeRepository)
            assert await request.get(AttendanceStore) is await request.get(UserLessonAttendanceRepository)
            assert client is await request.get(ObisAuthenticator)
            assert crypto is await request.get(PasswordCipher)
        async with container() as request:
            for dependency, instance in zip(dependencies, first, strict=True):
                assert instance is not await request.get(dependency)
            assert client is await request.get(ObisClient) and crypto is await request.get(CryptoService)
            assert source is await request.get(ResultsSource)
            assert client is await request.get(ObisAuthenticator)
            assert crypto is await request.get(PasswordCipher)


def test_obis_polling_refreshes_every_fifteen_minutes():
    scheduler = create_scheduler("container", "bot")
    matching = [job for job in scheduler.get_jobs() if job.func is jobs.poll_obis_notifications_job]
    assert len(matching) == 1 and matching[0].trigger.interval.total_seconds() == 900
    assert matching[0].args == ("container", "bot")


@pytest.mark.parametrize("age", [timedelta(hours=3), None])
async def test_expired_session_is_forgotten_and_reported_only_when_it_existed(age):
    grades = AsyncMock(spec=RefreshObisGradesUseCase)
    attendance = AsyncMock(spec=RefreshObisAttendanceUseCase)
    grades.execute.side_effect = ObisSessionExpiredError
    sessions = AsyncMock(spec=ObisSessions)
    sessions.expire.return_value = age
    sender = AsyncMock()
    await PollObisUserUseCase(grades, attendance, AsyncMock(), sessions).execute(975001, True, True, sender)
    sessions.expire.assert_awaited_once_with(975001)
    attendance.execute.assert_not_awaited()
    assert sender.session_expired.await_count == int(age is not None)


async def test_session_expired_notification_uses_recipient_locale_and_login_button():
    outbox = AsyncMock()
    sender = TelegramObisNotificationSender(outbox, 975001, Locale.ZH, Theme.BASIC)
    with i18n.context(), i18n.use_locale("ru"):
        await sender.session_expired()
        with i18n.use_locale("zh"):
            expected_text, expected_keyboard = i18n.gettext("obis.session_expired"), build_login_keyboard()
    (method,) = outbox.enqueue.await_args.args[1]
    assert method.text == expected_text and method.reply_markup == expected_keyboard
    assert outbox.enqueue.await_args.kwargs == {"category": "obis_session"}
