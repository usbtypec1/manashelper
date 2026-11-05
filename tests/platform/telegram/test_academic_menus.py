from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.methods import SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from pydantic import SecretStr

from manashelper.core.config import get_settings
from manashelper.localization.locale import Locale
from manashelper.modules.eders.application.models import DeadlineFilter, EdersSnapshot
from manashelper.modules.eders.application.tracking import EdersSetting, EdersSettings
from manashelper.modules.eders.presentation import router as eders
from manashelper.modules.eders.presentation.callbacks import (
    EdersAction,
    EdersMenuCallback,
    EdersPageCallback,
    EdersSettingCallback,
)
from manashelper.modules.eders.presentation.keyboards import build_eders_menu_keyboard
from manashelper.modules.notifications.keyboards import build_notifications_keyboard
from manashelper.modules.notifications.settings import NotificationSetting, NotificationSettingsSummary
from manashelper.modules.obis.presentation import router as obis
from manashelper.modules.obis.presentation.callbacks import ObisAction, ObisCallback, ObisNotificationSettingCallback
from manashelper.modules.obis.presentation.keyboards import build_obis_menu_keyboard
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.middlewares.private_chat_only import PrivateChatOnlyMiddleware
from manashelper.platform.telegram.navigation import build_study_keyboard
from manashelper.platform.telegram.routers import navigation


def register_handlers(dispatcher, router):
    for event in ("message", "callback_query"):
        for handler in getattr(router, event).handlers:
            # Startup tests may already have injected the shared router. These
            # dispatch tests supply their own dependencies to the original handler.
            callback = getattr(handler.callback, "__dishka_orig_func__", handler.callback)
            getattr(dispatcher, event).register(
                callback, *(item.callback for item in handler.filters), flags=handler.flags.copy()
            )


@pytest.mark.parametrize("locale", list(Locale))
@pytest.mark.parametrize("feature", ["eders", "obis"])
async def test_study_feature_menu_views_notifications_and_back(monkeypatch, locale, feature):
    monkeypatch.setattr(get_settings(), "eders_password", SecretStr("fake-password"))
    dispatcher = Dispatcher()
    for router in (navigation.router, obis.menu_router, eders.menu_router, obis.router, eders.router):
        register_handlers(dispatcher, router)
    for event in (dispatcher.message, dispatcher.callback_query):
        event.middleware(PrivateChatOnlyMiddleware())
    eders_service = AsyncMock(get_snapshot=AsyncMock(return_value=EdersSnapshot((), datetime.now(UTC))))
    tracking = AsyncMock(
        get_settings=AsyncMock(return_value=EdersSettings(True, True, True, True, True)),
        toggle=AsyncMock(return_value=EdersSettings(False, True, True, True, True)),
    )
    obis_service = AsyncMock(get_attendance=AsyncMock(return_value=[]), get_exam_grades=AsyncMock(return_value=[]))
    settings_service = AsyncMock(
        get_settings=AsyncMock(return_value=NotificationSettingsSummary(True, True, True)),
        toggle_setting=AsyncMock(return_value=NotificationSettingsSummary(True, False, True)),
    )

    async def settings_execute(user_id, setting=None):
        if setting is None:
            return await settings_service.get_settings(user_id)
        return await settings_service.toggle_setting(user_id, setting)

    tracking.execute = tracking.toggle
    dependencies = dict(
        eders_query=eders_service,
        tracking=tracking,
        toggle_eders_setting=tracking,
        results=obis_service,
        activity=AsyncMock(),
        get_notification_settings=SimpleNamespace(execute=settings_execute),
        set_broadcast_mute=SimpleNamespace(execute=settings_execute),
        toggle_notification_setting=SimpleNamespace(execute=settings_execute),
    )
    chat = Chat(id=42, type="private")
    user = User(id=42, is_bot=False, first_name="Student")
    async with Bot(token="123456:development-placeholder") as bot:
        bot_message = Message(
            message_id=100, date=0, chat=chat, from_user=User(id=bot.id, is_bot=True, first_name="Bot")
        )
        request = AsyncMock(return_value=bot_message.as_(bot))
        monkeypatch.setattr(bot.session, "make_request", request)
        state = FSMContext(dispatcher.storage, StorageKey(bot_id=bot.id, chat_id=42, user_id=42))
        with i18n.context(), i18n.use_locale(locale.value):
            for index, key in enumerate(("menu.study", f"menu.{feature}")):
                await state.set_state(obis.ObisCredentialsForm.password)
                await state.update_data(student_number="unfinished")
                await dispatcher.feed_update(
                    bot,
                    Update(
                        update_id=index,
                        message=Message(
                            message_id=index + 1, date=0, chat=chat, from_user=user, text=i18n.gettext(key)
                        ),
                    ),
                    **dependencies,
                )
                assert await state.get_state() is None and await state.get_data() == {}
            sent = [call.args[1] for call in request.await_args_list if isinstance(call.args[1], SendMessage)]
            assert sent[0].reply_markup == build_study_keyboard()
            assert i18n.gettext(f"menu.{feature}") in [
                button.text for row in sent[0].reply_markup.keyboard for button in row
            ]
            menu = build_eders_menu_keyboard() if feature == "eders" else build_obis_menu_keyboard()
            assert sent[-1].reply_markup == menu
            assert sum(map(len, menu.inline_keyboard)) == 3
            payloads = [button.callback_data for row in menu.inline_keyboard for button in row]

            async def click(payload):
                request.reset_mock()
                await dispatcher.feed_update(
                    bot,
                    Update(
                        update_id=10,
                        callback_query=CallbackQuery(
                            id="test", from_user=user, chat_instance="chat", message=bot_message, data=payload
                        ),
                    ),
                    **dependencies,
                )
                return [call.args[1] for call in request.await_args_list]

            for payload in payloads[:2]:
                methods = await click(payload)
                assert methods
                if feature == "eders":
                    eders_service.get_snapshot.assert_awaited_with(user.id)
                    selected = next(
                        button
                        for row in methods[-1].reply_markup.inline_keyboard
                        for button in row
                        if button.text.startswith("✓ ")
                    )
                    expected = (
                        DeadlineFilter.MATERIALS
                        if EdersMenuCallback.unpack(payload).action == EdersAction.MATERIALS
                        else DeadlineFilter.ALL
                    )
                    assert EdersPageCallback.unpack(selected.callback_data).selected == expected
                else:
                    fetch = (
                        obis_service.get_attendance
                        if ObisCallback.unpack(payload).action == ObisAction.ATTENDANCE
                        else obis_service.get_exam_grades
                    )
                    fetch.assert_awaited_once_with(user.id)

            methods = await click(payloads[2])
            keyboard = next(method.reply_markup for method in methods if hasattr(method, "reply_markup"))
            if feature == "eders":
                assert len(keyboard.inline_keyboard) == len(EdersSetting) + 1
                toggle = EdersSettingCallback(setting=EdersSetting.DAY_BEFORE).pack()
                back = EdersMenuCallback(action=EdersAction.MENU).pack()
            else:
                assert len(keyboard.inline_keyboard) == 3
                toggle = ObisNotificationSettingCallback(setting=NotificationSetting.EXAM_GRADES).pack()
                back = ObisCallback(action=ObisAction.MENU).pack()
            assert keyboard.inline_keyboard[-1][0].callback_data == back
            methods = await click(toggle)
            keyboard = next(method.reply_markup for method in methods if hasattr(method, "reply_markup"))
            assert keyboard.inline_keyboard[-1][0].callback_data == back
            if feature == "eders":
                tracking.toggle.assert_awaited_once_with(user.id, EdersSetting.DAY_BEFORE)
            else:
                settings_service.toggle_setting.assert_awaited_once_with(user.id, NotificationSetting.EXAM_GRADES)
            methods = await click(back)
            assert next(method.reply_markup for method in methods if hasattr(method, "reply_markup")) == menu
            general = build_notifications_keyboard(NotificationSettingsSummary(True, True, True))
            assert {button.callback_data for row in general.inline_keyboard for button in row} == {
                "notification_setting:schedule_changes",
                "settings:open_food_menu_notifications",
                "settings:back_to_settings",
            }
    await dispatcher.storage.close()
