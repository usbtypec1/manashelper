import base64
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage
from aiogram.types import CallbackQuery, Chat, Message, User
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dishka import make_async_container

from manashelper.core.database import Base
from manashelper.core.provider import CoreProvider
from manashelper.jobs.scheduler import create_scheduler
from manashelper.localization.locale import Locale
from manashelper.modules.eders.application.eders import EdersService
from manashelper.modules.obis import jobs
from manashelper.modules.obis.application.credentials import ObisCredentialsService
from manashelper.modules.obis.application.notification import (
    ExamGradeChange,
    LessonSkipChange,
    ObisNotificationService,
    SkipType,
)
from manashelper.modules.obis.application.obis import ExamModel, LessonAttendanceModel, LessonExamsModel, ObisService
from manashelper.modules.obis.application.polling import PollObisUser
from manashelper.modules.obis.errors import (
    DecryptionError,
    ObisLoginError,
    ObisParseError,
    UserHasNoCredentialsError,
    UserNotFoundError,
)
from manashelper.modules.obis.infrastructure import crypto as crypto_module
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.credentials_repository import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.user_exam_grade_repository import UserExamGradeRepository
from manashelper.modules.obis.infrastructure.user_lesson_attendance_repository import UserLessonAttendanceRepository
from manashelper.modules.obis.presentation import router as router
from manashelper.modules.obis.presentation.callbacks import ObisAction, ObisCallback, ObisResultsPageCallback
from manashelper.modules.obis.presentation.formatter import format_exam_grade_change
from manashelper.modules.obis.presentation.sender import TelegramObisNotificationSender
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.users.infrastructure.user import User as DbUser
from manashelper.platform.i18n.catalog import i18n

KEY = bytes(range(32))


@pytest.fixture
def crypto():
    return CryptoService(SimpleNamespace(obis_encryption_key=base64.b64encode(KEY).decode()))


@pytest.fixture
def credentials(session, crypto):
    client = AsyncMock(spec=ObisClient)
    account = ObisCredentialsService(ObisCredentialsRepository(session), client, crypto)
    return SimpleNamespace(service=ObisService(account, client), client=client, account=account)


async def test_credentials_verify_before_storage_and_keep_cipher_format(session, credentials, crypto):
    old = crypto.encrypt("old password")
    user = DbUser(id=975001, full_name="Student", student_number="old", encrypted_password=old)
    session.add(user)
    await session.flush()

    async def verify(student_number, password):
        assert (student_number, password) == ("new", "fake-password")
        assert (user.student_number, user.encrypted_password) == ("old", old)

    credentials.client.verify_credentials.side_effect = verify
    await credentials.service.save_credentials(975001, "new", "fake-password")
    assert user.student_number == "new" and crypto.decrypt(user.encrypted_password) == "fake-password"
    assert len(base64.b64decode(user.encrypted_password)) == 12 + len("fake-password") + 16
    assert await credentials.service.has_credentials(975001)
    await credentials.service.clear_credentials(975001)
    assert (user.student_number, user.encrypted_password) == (None, None)
    assert not await credentials.service.has_credentials(975001)


@pytest.mark.parametrize("operation", ["save", "has", "clear"])
async def test_unknown_user_never_attempts_login(credentials, operation):
    with pytest.raises(UserNotFoundError) as error:
        if operation == "save":
            await credentials.service.save_credentials(975001, "fake-student", "fake-password")
        elif operation == "has":
            await credentials.service.has_credentials(975001)
        else:
            await credentials.service.clear_credentials(975001)
    assert error.value.user_id == 975001
    credentials.client.verify_credentials.assert_not_awaited()


async def test_failed_login_does_not_replace_existing_credentials(session, credentials):
    user = DbUser(id=975001, full_name="Student", student_number="old", encrypted_password="old-ciphertext")
    session.add(user)
    await session.flush()
    credentials.client.verify_credentials.side_effect = ObisLoginError("denied")
    with pytest.raises(ObisLoginError):
        await credentials.service.save_credentials(975001, "new", "fake-password")
    assert (user.student_number, user.encrypted_password) == ("old", "old-ciphertext")


async def test_encryption_failure_preserves_existing_assignment_order(session, credentials, crypto, monkeypatch):
    user = DbUser(id=975001, full_name="Student", student_number="old", encrypted_password="old-ciphertext")
    session.add(user)
    await session.flush()

    def fail(_):
        raise RuntimeError("Encryption unavailable")

    monkeypatch.setattr(crypto, "encrypt", fail)
    with pytest.raises(RuntimeError, match="Encryption unavailable"):
        await credentials.service.save_credentials(975001, "new", "fake-password")
    # Existing order: student number mutates before encrypting. Fix separately from relocation.
    assert (user.student_number, user.encrypted_password) == ("new", "old-ciphertext")


@pytest.mark.parametrize("ciphertext", [None, "not-ciphertext"])
async def test_missing_or_corrupt_credentials_never_fetch_data(session, credentials, ciphertext):
    session.add(DbUser(id=975001, full_name="Student", student_number="fake-student", encrypted_password=ciphertext))
    await session.flush()
    with pytest.raises(UserHasNoCredentialsError) as error:
        await credentials.service.get_exam_grades(975001)
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
async def test_first_grade_preserves_existing_nonempty_notification_behavior(session, score):
    session.add(DbUser(id=975001, full_name="Student"))
    await session.flush()
    source = AsyncMock(spec=ObisService)
    source.get_exam_grades.return_value = [LessonExamsModel("Math", "MATH", [ExamModel("Midterm", score)])]
    service = ObisNotificationService(source, UserExamGradeRepository(session), UserLessonAttendanceRepository(session))
    first = await service.check_exam_grade_changes(975001)
    assert [change.score for change in first] == ([] if score is None else ["80"])
    await session.flush()
    assert await service.check_exam_grade_changes(975001) == []
    source.get_exam_grades.return_value = [LessonExamsModel("Math", "MATH", [ExamModel("Midterm", None)])]
    assert await service.check_exam_grade_changes(975001) == []
    source.get_exam_grades.return_value = [LessonExamsModel("Math", "MATH", [ExamModel("Midterm", "85")])]
    assert [change.score for change in await service.check_exam_grade_changes(975001)] == ["85"]


async def test_attendance_baseline_is_silent_and_only_known_increases_notify(session):
    session.add(DbUser(id=975001, full_name="Student"))
    await session.flush()
    source = AsyncMock(spec=ObisService)
    source.get_attendance.return_value = [LessonAttendanceModel("Math", "MATH", 12.5, None, 2, None)]
    service = ObisNotificationService(source, UserExamGradeRepository(session), UserLessonAttendanceRepository(session))
    assert await service.check_lesson_skip_changes(975001) == []
    await session.flush()
    source.get_attendance.return_value = [LessonAttendanceModel("Math", "MATH", 18.75, 6.25, 1, 2)]
    changes = await service.check_lesson_skip_changes(975001)
    assert [(change.skip_type, change.skips_percentage) for change in changes] == [(SkipType.THEORY, 18.75)]
    source.get_attendance.return_value = [LessonAttendanceModel("Math", "MATH", 0, None, 4, None)]
    assert await service.check_lesson_skip_changes(975001) == []


def test_obis_callbacks_fsm_private_and_password_mask_contract():
    assert ObisCallback(action=ObisAction.ACCEPT_TERMS).pack() == "obis:accept_terms"
    assert ObisResultsPageCallback(page=2).pack() == "obis_results_page:2"
    assert router.ObisCredentialsForm.student_number.state == "ObisCredentialsForm:student_number"
    assert router.ObisCredentialsForm.password.state == "ObisCredentialsForm:password"
    handlers = router.router.message.handlers + router.router.callback_query.handlers
    assert all(handler.flags["private_chat_only"] for handler in handlers)
    password = next(handler for handler in handlers if handler.callback.__name__ == "on_password_entered")
    assert password.flags["mask_logged_message"]


@pytest.mark.parametrize("failure", [None, "login", "missing"])
async def test_credentials_form_deletes_password_and_preserves_fsm_transitions(monkeypatch, failure):
    bot = Bot(token="123456:development-placeholder")
    user = User(id=975001, is_bot=False, first_name="Student")
    message = Message(message_id=1, date=0, chat=Chat(id=user.id, type="private"), from_user=user).as_(bot)
    callback = CallbackQuery(id="obis", from_user=user, message=message, chat_instance="chat").as_(bot)
    request = AsyncMock(return_value=message)
    monkeypatch.setattr(bot.session, "make_request", request)
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=bot.id, chat_id=user.id, user_id=user.id))
    service = AsyncMock()
    if failure:
        service.save_credentials.side_effect = (
            ObisLoginError("denied") if failure == "login" else UserNotFoundError(user.id)
        )
    with i18n.context(), i18n.use_locale("en"):
        await router.on_accept_terms(callback, state)
        await router.on_student_number_entered(message.model_copy(update={"text": " fake-student "}), state)
        assert await state.get_state() == "ObisCredentialsForm:password"
        request.reset_mock()
        await router.on_password_entered(message.model_copy(update={"text": " fake-password "}), state, service)
    service.save_credentials.assert_awaited_once_with(user.id, "fake-student", "fake-password")
    methods = [call.args[1] for call in request.await_args_list]
    assert methods[0].__api_method__ == "deleteMessage"
    assert await state.get_state() == ("ObisCredentialsForm:student_number" if failure == "login" else None)
    assert all("fake-password" not in (getattr(method, "text", None) or "") for method in methods)


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
    assert await EdersService(credentials.account, client, tracking).get_snapshot(user.id) is snapshot
    client.fetch_snapshot.assert_awaited_once_with("fake-student", "fake-password")
    tracking.observe.assert_awaited_once_with(user.id, account.credential_marker, snapshot)
    credentials.client.verify_credentials.assert_not_awaited()


@pytest.mark.parametrize("mode", ["unknown", "missing", "corrupt"])
async def test_eders_credential_failures_never_fetch_and_preserve_suppressed_decryption_context(
    session, credentials, mode
):
    if mode != "unknown":
        session.add(
            DbUser(
                id=975001,
                full_name="Student",
                student_number="fake-student",
                encrypted_password=None if mode == "missing" else "bad-ciphertext",
            )
        )
        await session.flush()
    client, tracking = AsyncMock(), AsyncMock()
    expected = UserNotFoundError if mode == "unknown" else UserHasNoCredentialsError
    with pytest.raises(expected) as error:
        await EdersService(credentials.account, client, tracking).get_snapshot(975001)
    assert error.value.__cause__ is None
    if mode == "corrupt":
        assert error.value.__suppress_context__
    tracking.get_settings.assert_awaited_once_with(975001)
    client.fetch_snapshot.assert_not_awaited()
    tracking.observe.assert_not_awaited()


async def test_eders_checks_tracking_before_reading_credentials():
    account, client, tracking = AsyncMock(), AsyncMock(), AsyncMock()
    tracking.get_settings.side_effect = RuntimeError("Tracking failed")
    with pytest.raises(RuntimeError, match="Tracking failed"):
        await EdersService(account, client, tracking).get_snapshot(975001)
    account.get_credentials.assert_not_awaited()
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
    notifications = AsyncMock(spec=ObisNotificationService)
    notifications.check_exam_grade_changes.return_value = ["grade"]
    notifications.check_lesson_skip_changes.return_value = ["skip"]
    notifications.check_exam_grade_changes.side_effect = error
    sender = AsyncMock()
    polling = PollObisUser(notifications)
    if isinstance(error, (httpx.HTTPError, RuntimeError)):
        with pytest.raises(type(error)):
            await polling.execute(975001, True, True, sender)
        notifications.check_lesson_skip_changes.assert_not_awaited()
        sender.lesson_skips_changed.assert_not_awaited()
    else:
        await polling.execute(975001, True, True, sender)
        notifications.check_lesson_skip_changes.assert_awaited_once_with(975001)
        sender.lesson_skips_changed.assert_awaited_once_with("skip")
    assert sender.exam_grade_changed.await_count == int(error is None)


@pytest.mark.parametrize("failure", ["telegram", "transport"])
async def test_telegram_sender_keeps_recipient_locale_and_delivery_failure_boundary(failure):
    notifications = AsyncMock(spec=ObisNotificationService)
    notifications.check_exam_grade_changes.return_value = [
        ExamGradeChange("Math", "Midterm", "80"),
        ExamGradeChange("Math", "Final", "90"),
    ]
    notifications.check_lesson_skip_changes.return_value = [LessonSkipChange("Math", SkipType.THEORY, 25, 0)]
    bot = AsyncMock()
    error = (
        TelegramBadRequest(method=SendMessage(chat_id=975001, text="fixture"), message="gone")
        if failure == "telegram"
        else RuntimeError("Transport failed")
    )
    bot.send_message.side_effect = [error, None, None]
    sender = TelegramObisNotificationSender(bot, 975001, Locale.ZH)
    with i18n.context(), i18n.use_locale("ru"):
        if failure == "telegram":
            await PollObisUser(notifications).execute(975001, True, True, sender)
            assert bot.send_message.await_count == 3
            assert all("Math" in call.args[1] for call in bot.send_message.await_args_list)
            with i18n.use_locale("zh"):
                expected = format_exam_grade_change(notifications.check_exam_grade_changes.return_value[0])
            assert bot.send_message.await_args_list[0].args[1] == expected
        else:
            with pytest.raises(RuntimeError, match="Transport failed"):
                await PollObisUser(notifications).execute(975001, True, True, sender)
            assert bot.send_message.await_count == 1
            notifications.check_lesson_skip_changes.assert_not_awaited()
        assert i18n.current_locale == "ru"


async def test_obis_provider_preserves_app_request_scopes_and_model_registry():
    from manashelper.modules.obis.infrastructure.user_exam_grade import UserExamGrade
    from manashelper.modules.obis.infrastructure.user_lesson_attendance import UserLessonAttendance

    assert Base.metadata.tables["user_exam_grades"] is UserExamGrade.__table__
    assert Base.metadata.tables["user_lesson_attendance"] is UserLessonAttendance.__table__
    dependencies = (
        ObisCredentialsRepository,
        ObisCredentialsService,
        ObisService,
        ObisNotificationService,
        UserExamGradeRepository,
        UserLessonAttendanceRepository,
        PollObisUser,
    )
    async with make_async_container(CoreProvider(), ObisProvider()) as container:
        client, crypto = await container.get(ObisClient), await container.get(CryptoService)
        async with container() as request:
            first = [await request.get(dependency) for dependency in dependencies]
            for dependency, instance in zip(dependencies, first, strict=True):
                assert instance is await request.get(dependency)
            assert client is await request.get(ObisClient) and crypto is await request.get(CryptoService)
        async with container() as request:
            for dependency, instance in zip(dependencies, first, strict=True):
                assert instance is not await request.get(dependency)
            assert client is await request.get(ObisClient) and crypto is await request.get(CryptoService)


def test_obis_polling_keeps_hourly_scheduler_contract():
    scheduler = create_scheduler("container", "bot")
    matching = [job for job in scheduler.get_jobs() if job.func is jobs.poll_obis_notifications_job]
    assert len(matching) == 1 and matching[0].trigger.interval.total_seconds() == 3600
    assert matching[0].args == ("container", "bot")
