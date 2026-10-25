from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery, Message
from aiogram.types import User as TelegramUser
from dishka import make_async_container
from sqlalchemy import select

from manashelper.core.database import Base
from manashelper.core.provider import CoreProvider
from manashelper.db.models import NotificationSettings, User
from manashelper.di import AppProvider, RequestProvider
from manashelper.jobs import obis_notification
from manashelper.modules.notifications import router
from manashelper.modules.notifications.callbacks import NotificationSettingCallback
from manashelper.modules.notifications.keyboards import build_notifications_keyboard
from manashelper.modules.notifications.orm import NotificationSettings as OwnedNotificationSettings
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.notifications.repository import NotificationSettingsRepository
from manashelper.modules.notifications.settings import (
    NotificationSetting,
    NotificationSettingsService,
    NotificationSettingsSummary,
    UserNotFoundError,
)
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.provider import UsersProvider
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback
from manashelper.platform.telegram.provider import TelegramPlatformProvider


def service(session):
    return NotificationSettingsService(NotificationSettingsRepository(session), UsersQuery(UserRepository(session)))


@pytest.mark.parametrize("action", ["get", *NotificationSetting])
async def test_settings_require_existing_user_without_creating_a_row(session, action):
    with pytest.raises(UserNotFoundError) as error:
        if action == "get":
            await service(session).get_settings(972001)
        else:
            await service(session).toggle_setting(972001, action)
    assert error.value.user_id == 972001
    assert await session.get(NotificationSettings, 972001) is None


@pytest.mark.parametrize("setting", list(NotificationSetting))
async def test_toggle_preserves_other_settings_and_persists(session, setting):
    session.add(User(id=972001, full_name="Notifications"))
    await session.flush()
    session.add(NotificationSettings(user_id=972001))
    await session.flush()
    settings_service = service(session)
    assert await settings_service.get_settings(972001) == NotificationSettingsSummary(True, True, True)
    result = await settings_service.toggle_setting(972001, setting)
    expected = {f"{option.value}_enabled": option != setting for option in NotificationSetting}
    assert result == NotificationSettingsSummary(**expected)
    await session.flush()
    session.expire_all()
    assert await settings_service.get_settings(972001) == result
    assert await settings_service.toggle_setting(972001, setting) == NotificationSettingsSummary(True, True, True)


@pytest.mark.parametrize("setting", list(NotificationSetting))
async def test_first_toggle_keeps_existing_orm_default_timing(session, setting):
    session.add(User(id=972001, full_name="Notifications"))
    await session.flush()
    result = await service(session).toggle_setting(972001, setting)
    # Defaults only run on INSERT. Preserve this existing defect during relocation.
    assert getattr(result, f"{setting.value}_enabled") is True
    assert all(getattr(result, f"{other.value}_enabled") is None for other in NotificationSetting if other != setting)
    await session.flush()
    assert await service(session).get_settings(972001) == NotificationSettingsSummary(True, True, True)


async def test_read_creates_settings_with_existing_deferred_defaults(session):
    session.add(User(id=972001, full_name="Notifications"))
    await session.flush()
    summary = await service(session).get_settings(972001)
    assert summary.schedule_changes_enabled is None
    assert summary.exam_grades_enabled is None
    assert summary.lesson_skips_enabled is None
    await session.flush()
    assert await service(session).get_settings(972001) == NotificationSettingsSummary(True, True, True)
    rows = await session.scalars(select(NotificationSettings).where(NotificationSettings.user_id == 972001))
    assert len(rows.all()) == 1


async def test_recipients_include_missing_settings_and_filter_flags_independently(session):
    ids = {972001, 972002, 972003, 972004}
    session.add_all(User(id=user_id, full_name="Recipient") for user_id in ids)
    await session.flush()
    session.add_all(
        [
            NotificationSettings(user_id=972002, exam_grades_enabled=False),
            NotificationSettings(user_id=972003, lesson_skips_enabled=False),
            NotificationSettings(user_id=972004, exam_grades_enabled=False, lesson_skips_enabled=False),
        ]
    )
    await session.flush()
    recipients = NotificationRecipientsQuery(NotificationSettingsRepository(session))
    assert set(await recipients.for_exam_grades()) & ids == {972001, 972003}
    assert set(await recipients.for_lesson_skips()) & ids == {972001, 972002}


def test_notification_payload_keyboard_order_and_private_flags():
    with i18n.context(), i18n.use_locale("ru"):
        keyboard = build_notifications_keyboard(NotificationSettingsSummary(True, False, True))
    buttons = [row[0] for row in keyboard.inline_keyboard]
    assert [button.callback_data for button in buttons] == [
        "notification_setting:schedule_changes",
        "settings:open_food_menu_notifications",
        "notification_setting:exam_grades",
        "notification_setting:lesson_skips",
        "settings:open_eders_notifications",
        "settings:back_to_settings",
    ]
    assert buttons[0].text.startswith("✅") and buttons[2].text.startswith("❌")
    names = {"on_open_notifications", "on_back_to_notifications", "on_toggle_notification_setting"}
    handlers = [handler for handler in router.router.callback_query.handlers if handler.callback.__name__ in names]
    assert len(handlers) == 3
    assert all(handler.flags["private_chat_only"] for handler in handlers)
    assert SettingsCallback(action=SettingsAction.BACK_TO_NOTIFICATIONS).pack() == "settings:back_to_notifications"


@pytest.mark.parametrize("action", ["open", "back", "toggle"])
@pytest.mark.parametrize("known_user", [True, False])
async def test_notification_handlers_keep_rendering_and_unknown_user_alerts(action, known_user):
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = SimpleNamespace(id=972001)
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    settings_service = AsyncMock()
    summary = NotificationSettingsSummary(True, False, True)
    method = settings_service.toggle_setting if action == "toggle" else settings_service.get_settings
    method.return_value = summary
    if not known_user:
        method.side_effect = UserNotFoundError(972001)
    with i18n.context(), i18n.use_locale("ru"):
        if action == "toggle":
            await router.on_toggle_notification_setting(
                callback, NotificationSettingCallback(setting=NotificationSetting.EXAM_GRADES), settings_service
            )
            method.assert_awaited_once_with(972001, NotificationSetting.EXAM_GRADES)
        else:
            handler = router.on_open_notifications if action == "open" else router.on_back_to_notifications
            await handler(callback, settings_service)
            method.assert_awaited_once_with(972001)
        if known_user:
            callback.message.edit_text.assert_awaited_once_with(
                i18n.gettext("notifications.title"), reply_markup=build_notifications_keyboard(summary)
            )
            callback.answer.assert_awaited_once_with()
        else:
            callback.message.edit_text.assert_not_awaited()
            callback.answer.assert_awaited_once_with(i18n.gettext("common.start_required"), show_alert=True)


@pytest.mark.parametrize("load_fails", [False, True])
async def test_obis_poll_keeps_recipient_union_flags_and_load_failure_boundary(monkeypatch, caplog, load_fails):
    recipients = AsyncMock(spec=NotificationRecipientsQuery)
    recipients.for_exam_grades.return_value = [11, 12]
    recipients.for_lesson_skips.return_value = [12, 13]
    if load_fails:
        recipients.for_lesson_skips.side_effect = RuntimeError("Recipients unavailable")
    opened = []

    @asynccontextmanager
    async def container():
        opened.append(object())
        yield SimpleNamespace(get=AsyncMock(side_effect={NotificationRecipientsQuery: recipients}.__getitem__))

    poll = AsyncMock()
    monkeypatch.setattr(obis_notification, "_poll_user_obis_notifications", poll)
    bot = object()
    await obis_notification.poll_obis_notifications_job(container, bot)
    assert len(opened) == 1
    recipients.for_exam_grades.assert_awaited_once_with()
    recipients.for_lesson_skips.assert_awaited_once_with()
    if load_fails:
        poll.assert_not_awaited()
        assert "Failed to load users for OBIS notification polling" in caplog.text
    else:
        assert poll.await_count == 3
        assert {call.args[2:] for call in poll.await_args_list} == {
            (11, True, False),
            (12, True, True),
            (13, False, True),
        }
        assert all(call.args[:2] == (container, bot) for call in poll.await_args_list)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("settings:open_notifications", "on_open_notifications"),
        ("settings:back_to_notifications", "on_back_to_notifications"),
        ("notification_setting:lesson_skips", "on_toggle_notification_setting"),
        ("settings:open_obis", None),
        ("settings:open_food_menu_notifications", None),
        ("settings:open_eders_notifications", None),
    ],
)
async def test_notification_router_matches_only_its_callbacks(payload, expected):
    callback = CallbackQuery(
        id="notifications",
        chat_instance="chat",
        data=payload,
        from_user=TelegramUser(id=972001, is_bot=False, first_name="Student"),
    )
    matching = []
    for handler in router.router.callback_query.handlers:
        matches, _ = await handler.check(callback)
        if matches:
            matching.append(handler.callback.__name__)
    assert matching == ([expected] if expected else [])


async def test_notification_provider_preserves_request_scope_and_model_registry():
    assert NotificationSettings is OwnedNotificationSettings
    assert Base.metadata.tables["notification_settings"] is NotificationSettings.__table__
    async with make_async_container(
        CoreProvider(),
        TelegramPlatformProvider(),
        AppProvider(),
        RequestProvider(),
        ScheduleProvider(),
        NotificationsProvider(),
        UsersProvider(),
    ) as container:
        async with container() as request:
            settings = await request.get(NotificationSettingsService)
            recipients = await request.get(NotificationRecipientsQuery)
            repository = await request.get(NotificationSettingsRepository)
            assert settings is await request.get(NotificationSettingsService)
            assert recipients is await request.get(NotificationRecipientsQuery)
            assert repository is await request.get(NotificationSettingsRepository)
        async with container() as request:
            assert settings is not await request.get(NotificationSettingsService)
            assert recipients is not await request.get(NotificationRecipientsQuery)
            assert repository is not await request.get(NotificationSettingsRepository)
