import subprocess
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, ReplyKeyboardRemove, User
from dishka import make_async_container
from dishka.integrations.aiogram import CONTAINER_NAME

from manashelper.core.database import Base
from manashelper.core.provider import CoreProvider
from manashelper.localization.locale import DEFAULT_LOCALE, Locale
from manashelper.modules.eders.provider import EdersProvider
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.obis import jobs
from manashelper.modules.obis.application.notification import ObisNotificationService
from manashelper.modules.obis.application.polling import PollObisUser
from manashelper.modules.obis.presentation import sender as obis_sender
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.schedule.infrastructure.models.course import Course
from manashelper.modules.schedule.infrastructure.models.department import Department
from manashelper.modules.schedule.infrastructure.models.faculty import Faculty
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.study_week.provider import StudyWeekProvider
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.user_contact import (
    InvalidPhoneNumberError,
    PhoneNumberForbiddenError,
    PhoneNumberNotFoundError,
    PhoneNumberSummary,
    UserContactService,
    UserNotFoundError,
)
from manashelper.modules.users.infrastructure.user import User as DbUser
from manashelper.modules.users.infrastructure.user_phone_number import UserPhoneNumber
from manashelper.modules.users.infrastructure.user_phone_number_repository import UserPhoneNumberRepository
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.presentation.callbacks import (
    LocaleCallback,
    PhoneNumberAction,
    PhoneNumberActionCallback,
    PhoneNumberDeleteCallback,
)
from manashelper.modules.users.presentation.routers import locale, phone_numbers
from manashelper.modules.users.provider import UsersProvider
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.middlewares.i18n import LocaleMiddleware
from manashelper.platform.telegram.provider import TelegramPlatformProvider


@pytest.fixture
def context(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    user = User(id=973001, is_bot=False, first_name="Student")
    message = Message(message_id=1, date=0, chat=Chat(id=user.id, type="private"), from_user=user).as_(bot)
    callback = CallbackQuery(id="users", from_user=user, message=message, chat_instance="chat").as_(bot)
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=bot.id, chat_id=user.id, user_id=user.id))
    request = AsyncMock(return_value=message)
    monkeypatch.setattr(bot.session, "make_request", request)
    with i18n.context(), i18n.use_locale("ru"):
        yield SimpleNamespace(message=message, callback=callback, state=state, request=request)


async def test_profile_refresh_preserves_locale_credentials_and_course_relationship(session):
    repository = UserRepository(session)
    locales = LocaleService(repository)
    faculty = Faculty(id=uuid.uuid4(), name="Users migration")
    department = Department(id=uuid.uuid4(), name="Users migration", faculty=faculty)
    course = Course(id=973100, number=1, department=department)
    user = DbUser(
        id=973001,
        full_name="First name",
        username="old",
        tracked_courses=[course],
        student_number="student",
        encrypted_password="opaque-encrypted-value",
    )
    session.add(user)
    await session.flush()
    assert await locales.resolve(973001, "First name", "old", "zh-CN") == Locale.ZH
    assert await locales.resolve(973001, "New name", None, "en") == Locale.ZH
    assert (user.full_name, user.username) == ("New name", None)
    assert (user.student_number, user.encrypted_password) == ("student", "opaque-encrypted-value")
    assert user.tracked_courses == [course]
    await locales.set_locale(973001, Locale.TR)
    await session.flush()
    session.expire_all()
    assert await locales.get_locale(973001) == Locale.TR


async def test_locale_read_and_set_do_not_register_missing_users(session):
    repository = UserRepository(session)
    locales = LocaleService(repository)
    assert await locales.get_locale(973001) == DEFAULT_LOCALE
    await locales.set_locale(973001, Locale.EN)
    assert await repository.get_by_id(973001) is None
    assert await locales.resolve(973001, "Student", None, "unsupported") == DEFAULT_LOCALE
    await session.flush()
    assert (await repository.get_by_id(973001)).locale == DEFAULT_LOCALE.value


async def test_invalid_saved_locale_still_propagates_value_error(session):
    session.add(DbUser(id=973001, full_name="Student", locale="xx"))
    await session.flush()
    locales = LocaleService(UserRepository(session))
    with pytest.raises(ValueError):
        await locales.get_locale(973001)
    with pytest.raises(ValueError):
        await locales.resolve(973001, "Student", None, "en")


async def test_phone_read_order_and_stored_format_remain_unchanged(session):
    session.add(DbUser(id=973001, full_name="Student"))
    await session.flush()
    now = datetime(2026, 1, 1)
    older = UserPhoneNumber(id=uuid.uuid4(), user_id=973001, phone_number="+996 (700) 11-22-33", created_at=now)
    newer = UserPhoneNumber(
        id=uuid.uuid4(), user_id=973001, phone_number="0700000001", created_at=now + timedelta(seconds=1)
    )
    session.add_all([newer, older])
    await session.flush()
    service = UserContactService(UserRepository(session), UserPhoneNumberRepository(session))
    assert await service.get_phone_numbers(973001) == [
        PhoneNumberSummary(older.id, older.phone_number),
        PhoneNumberSummary(newer.id, newer.phone_number),
    ]
    assert await service.get_phone_numbers(973002) == []


def test_users_callback_payload_fsm_and_private_flags():
    key = uuid.UUID("00000000-0000-0000-0000-000000000001")
    assert LocaleCallback(locale=Locale.ZH).pack() == "locale:zh"
    assert PhoneNumberActionCallback(action=PhoneNumberAction.ADD).pack() == "phone_number_action:add"
    assert PhoneNumberDeleteCallback(id=key).pack() == f"phone_number_delete:{key.hex}"
    assert phone_numbers.PhoneNumberForm.phone_number.state == "PhoneNumberForm:phone_number"
    for router in (locale.router, phone_numbers.router):
        handlers = router.message.handlers + router.callback_query.handlers
        assert handlers and all(handler.flags["private_chat_only"] for handler in handlers)


@pytest.mark.parametrize("selected", list(Locale))
async def test_selected_language_controls_confirmation_and_welcome(context, selected):
    locales = AsyncMock(spec=LocaleService)
    await locale.on_locale_selected(context.callback, LocaleCallback(locale=selected), locales)
    locales.set_locale.assert_awaited_once_with(973001, selected)
    requests = [call.args[1] for call in context.request.await_args_list]
    expected = i18n.gettext("language.selected", locale=selected.value).format(
        language=i18n.gettext("language.native_name", locale=selected.value)
    )
    assert requests[0].text == expected
    assert requests[1].text == i18n.gettext("common.welcome", locale=selected.value)
    assert requests[1].reply_markup.keyboard[0][0].text == i18n.gettext("menu.food", locale=selected.value)
    assert requests[-1].__api_method__ == "answerCallbackQuery"


@pytest.mark.parametrize("failure", [None, "invalid", "missing"])
async def test_phone_form_retains_state_only_for_invalid_input(context, failure):
    contacts = AsyncMock(spec=UserContactService)
    contacts.get_phone_numbers.return_value = []
    if failure == "invalid":
        contacts.add_phone_number.side_effect = InvalidPhoneNumberError("bad")
    elif failure == "missing":
        contacts.add_phone_number.side_effect = UserNotFoundError(973001)
    await phone_numbers.on_add_phone_number_requested(context.callback, context.state)
    assert await context.state.get_state() == "PhoneNumberForm:phone_number"
    context.request.reset_mock()
    message = context.message.model_copy(update={"text": "  +996700000001  "})
    await phone_numbers.on_phone_number_entered(message, context.state, contacts)
    contacts.add_phone_number.assert_awaited_once_with(973001, "+996700000001")
    assert await context.state.get_state() == ("PhoneNumberForm:phone_number" if failure == "invalid" else None)
    requests = [call.args[1] for call in context.request.await_args_list]
    key = "phone.invalid" if failure == "invalid" else "common.start_required" if failure else "phone.saved"
    assert requests[0].text == i18n.gettext(key)
    if failure == "invalid":
        assert requests[0].reply_markup.keyboard[0][0].request_contact is True
    else:
        assert isinstance(requests[0].reply_markup, ReplyKeyboardRemove)
    assert len(requests) == (2 if failure is None else 1)
    assert contacts.get_phone_numbers.await_count == (1 if failure is None else 0)


@pytest.mark.parametrize("failure", [None, "forbidden", "missing"])
async def test_phone_deletion_keeps_ownership_alert_and_refresh_behavior(context, failure):
    contacts = AsyncMock(spec=UserContactService)
    contacts.get_phone_numbers.return_value = []
    key = uuid.uuid4()
    if failure:
        contacts.delete_phone_number.side_effect = (
            PhoneNumberForbiddenError(key, 973001) if failure == "forbidden" else PhoneNumberNotFoundError(key)
        )
    await phone_numbers.on_delete_phone_number(context.callback, PhoneNumberDeleteCallback(id=key), contacts)
    contacts.delete_phone_number.assert_awaited_once_with(973001, key)
    requests = [call.args[1] for call in context.request.await_args_list]
    if failure:
        assert len(requests) == 1 and requests[0].show_alert is True
        assert requests[0].text == i18n.gettext("phone.not_found")
        contacts.get_phone_numbers.assert_not_awaited()
    else:
        assert requests[0].text == i18n.gettext("phone.list")
        contacts.get_phone_numbers.assert_awaited_once_with(973001)


@pytest.mark.parametrize("saved", [None, "zh", "xx", "read_failure"])
async def test_obis_user_poll_keeps_locale_fallback_and_failure_isolation(monkeypatch, caplog, saved):
    users = AsyncMock(spec=UserRepository)
    users.get_by_id.return_value = SimpleNamespace(locale=saved) if saved is not None else None
    if saved == "read_failure":
        users.get_by_id.side_effect = RuntimeError("Locale unavailable")
    service = AsyncMock(spec=ObisNotificationService)
    service.check_exam_grade_changes.return_value = [object()]
    service.check_lesson_skip_changes.return_value = [object()]
    dependencies = {LocaleService: LocaleService(users), PollObisUser: PollObisUser(service)}
    opened = []

    @asynccontextmanager
    async def container():
        opened.append(object())
        yield SimpleNamespace(get=AsyncMock(side_effect=dependencies.__getitem__))

    monkeypatch.setattr(obis_sender, "format_exam_grade_change", lambda _: i18n.gettext("menu.grades"))
    monkeypatch.setattr(obis_sender, "format_lesson_skip_change", lambda _: i18n.gettext("menu.attendance"))
    send = AsyncMock()
    monkeypatch.setattr(obis_sender, "send_notification", send)
    bot = object()
    await jobs._poll_user_obis_notifications(container, bot, 973001, True, True)
    assert len(opened) == 1
    users.get_by_id.assert_awaited_once_with(973001)
    if saved in ("xx", "read_failure"):
        service.check_exam_grade_changes.assert_not_awaited()
        service.check_lesson_skip_changes.assert_not_awaited()
        send.assert_not_awaited()
        assert "Failed to poll OBIS notifications for user 973001" in caplog.text
    else:
        service.check_exam_grade_changes.assert_awaited_once_with(973001)
        service.check_lesson_skip_changes.assert_awaited_once_with(973001)
        assert [call.args for call in send.await_args_list] == [
            (bot, 973001, i18n.gettext(key, locale=saved or DEFAULT_LOCALE.value))
            for key in ("menu.grades", "menu.attendance")
        ]


async def test_users_provider_scopes_and_orm_registry():
    assert Base.metadata.tables["users"] is DbUser.__table__
    assert Base.metadata.tables["user_phone_numbers"] is UserPhoneNumber.__table__
    dependencies = (UsersQuery, LocaleService, UserContactService, UserRepository, UserPhoneNumberRepository)
    async with make_async_container(
        CoreProvider(),
        TelegramPlatformProvider(),
        ObisProvider(),
        EdersProvider(),
        StudyWeekProvider(),
        UsersProvider(),
        ScheduleProvider(),
        NotificationsProvider(),
    ) as container:
        async with container() as request:
            first = [await request.get(dependency) for dependency in dependencies]
            for dependency, instance in zip(dependencies, first, strict=True):
                assert instance is await request.get(dependency)
        async with container() as request:
            for dependency, instance in zip(dependencies, first, strict=True):
                assert instance is not await request.get(dependency)


@pytest.mark.parametrize("has_user", [False, True])
async def test_locale_middleware_keeps_request_context_and_profile_refresh(context, has_user):
    locales = AsyncMock(spec=LocaleService)
    locales.resolve.return_value = Locale.ZH
    request = SimpleNamespace(get=AsyncMock(return_value=locales))
    data = {CONTAINER_NAME: request}
    if has_user:
        data["event_from_user"] = context.message.from_user
    observed = []

    async def handler(event, payload):
        observed.append((event, payload.get("locale"), i18n.current_locale))
        return "handled"

    assert await LocaleMiddleware()(handler, context.message, data) == "handled"
    assert observed == [(context.message, Locale.ZH if has_user else None, "zh" if has_user else "ru")]
    assert i18n.current_locale == "ru"
    if has_user:
        request.get.assert_awaited_once_with(LocaleService)
        user = context.message.from_user
        locales.resolve.assert_awaited_once_with(
            user_id=user.id, full_name=user.full_name, username=user.username, language_code=user.language_code
        )
    else:
        request.get.assert_not_awaited()
        locales.resolve.assert_not_awaited()


@pytest.mark.parametrize(
    "module",
    [
        "manashelper.modules.users.application.locale",
        "manashelper.modules.users.infrastructure.user_phone_number_repository",
    ],
)
def test_users_standalone_import_uses_explicit_model_registration(module):
    script = (
        "import importlib; from sqlalchemy.orm import configure_mappers; "
        f"importlib.import_module({module!r}); "
        "from manashelper.core.database import Base; "
        "assert len(Base.metadata.tables) < 27; "
        "from manashelper.bootstrap import load_models; load_models(); configure_mappers(); "
        "assert len(Base.metadata.tables) == 27; "
        "assert Base.metadata.tables['user_courses'].c.user_id.references(Base.metadata.tables['users'].c.id)"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
