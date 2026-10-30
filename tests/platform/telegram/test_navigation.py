from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Chat, Message, Update, User

from manashelper.modules.schedule.presentation.keyboards.timetable import build_timetable_menu_keyboard
from manashelper.modules.schedule.presentation.routers import timetable
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.middlewares.private_chat_only import PrivateChatOnlyMiddleware
from manashelper.platform.telegram.navigation import build_main_keyboard, build_study_keyboard
from manashelper.platform.telegram.routers import navigation


def register_handlers(dispatcher, router):
    for handler in router.message.handlers:
        dispatcher.message.register(
            handler.callback, *(item.callback for item in handler.filters), flags=handler.flags.copy()
        )


@pytest.mark.parametrize("action", ["study", "back"])
@pytest.mark.parametrize("chat_type", ["private", "group", "supergroup"])
async def test_navigation_clears_private_forms_and_rejects_group_updates(monkeypatch, action, chat_type):
    dispatcher = Dispatcher()
    register_handlers(dispatcher, navigation.router)
    dispatcher.message.middleware(PrivateChatOnlyMiddleware())
    form_handler = AsyncMock()

    @dispatcher.message()
    async def form(message):
        await form_handler(message)

    async with Bot(token="123456:development-placeholder") as bot:
        chat = Chat(id=42 if chat_type == "private" else -42, type=chat_type)
        user = User(id=42, is_bot=False, first_name="Student")
        state = FSMContext(dispatcher.storage, StorageKey(bot_id=bot.id, chat_id=chat.id, user_id=user.id))
        await state.set_state("Form:input")
        await state.update_data(draft="unfinished")
        request = AsyncMock(return_value=Message(message_id=2, date=0, chat=chat))
        monkeypatch.setattr(bot.session, "make_request", request)
        with i18n.context(), i18n.use_locale("ru"):
            label = i18n.gettext("menu.study" if action == "study" else "common.back_to_menu")
            message = Message(message_id=1, date=datetime.now(UTC), chat=chat, from_user=user, text=label)
            await dispatcher.feed_update(bot, Update(update_id=1, message=message))
            form_handler.assert_not_awaited()
            [method] = [call.args[1] for call in request.await_args_list]
            if chat_type == "private":
                assert await state.get_state() is None and await state.get_data() == {}
                expected = build_study_keyboard() if action == "study" else build_main_keyboard()
                assert method.reply_markup == expected
                assert method.text == i18n.gettext("menu.study" if action == "study" else "menu.main")
            else:
                assert await state.get_state() == "Form:input"
                assert await state.get_data() == {"draft": "unfinished"}
                assert method.text == i18n.gettext("common.private_chat_only")
    await dispatcher.storage.close()


async def test_study_submenu_opens_existing_schedule_handler(monkeypatch):
    dispatcher = Dispatcher()
    register_handlers(dispatcher, navigation.router)
    register_handlers(dispatcher, timetable.router)
    async with Bot(token="123456:development-placeholder") as bot:
        chat = Chat(id=42, type="private")
        user = User(id=42, is_bot=False, first_name="Student")
        request = AsyncMock(return_value=Message(message_id=2, date=0, chat=chat))
        monkeypatch.setattr(bot.session, "make_request", request)
        with i18n.context(), i18n.use_locale("ru"):
            for update_id, key in enumerate(["menu.study", "menu.schedule"]):
                await dispatcher.feed_update(
                    bot,
                    Update(
                        update_id=update_id,
                        message=Message(
                            message_id=update_id + 1,
                            date=datetime.now(UTC),
                            chat=chat,
                            from_user=user,
                            text=i18n.gettext(key),
                        ),
                    ),
                )
            methods = [call.args[1] for call in request.await_args_list]
            assert methods[0].reply_markup == build_study_keyboard()
            assert methods[1].reply_markup == build_timetable_menu_keyboard()
    await dispatcher.storage.close()
