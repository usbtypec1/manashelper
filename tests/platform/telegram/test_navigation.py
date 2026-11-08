from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.methods import SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.schedule.application.schedule import NoTrackedCoursesError, ScheduleLessonModel
from manashelper.modules.schedule.presentation.routers import lesson_search, timetable
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.callbacks import NavigationAction, NavigationCallback
from manashelper.platform.telegram.middlewares.private_chat_only import PrivateChatOnlyMiddleware
from manashelper.platform.telegram.navigation import build_main_keyboard, build_study_keyboard
from manashelper.platform.telegram.routers import navigation


def register_handlers(dispatcher, router):
    for event in ("message", "callback_query"):
        for handler in getattr(router, event).handlers:
            getattr(dispatcher, event).register(
                getattr(handler.callback, "__dishka_orig_func__", handler.callback),
                *(item.callback for item in handler.filters),
                flags=handler.flags.copy(),
            )


@pytest.mark.parametrize("action", ["study", "back"])
@pytest.mark.parametrize("chat_type", ["private", "group", "supergroup"])
async def test_navigation_clears_private_forms_and_rejects_group_updates(monkeypatch, action, chat_type):
    dispatcher = Dispatcher(gamification=AsyncMock(is_enabled=AsyncMock(return_value=False)))
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


async def test_settings_button_exits_subject_search_without_treating_it_as_a_query(monkeypatch):
    from manashelper.platform.telegram.keyboards.settings import build_settings_keyboard
    from manashelper.platform.telegram.routers import settings

    search = AsyncMock()
    dispatcher = Dispatcher(lesson_search_query=search)
    for router in (settings.router, lesson_search.router):
        register_handlers(dispatcher, router)
    async with Bot(token="123456:development-placeholder") as bot:
        chat = Chat(id=42, type="private")
        user = User(id=42, is_bot=False, first_name="Student")
        state = FSMContext(dispatcher.storage, StorageKey(bot_id=bot.id, chat_id=42, user_id=42))
        await state.set_state(lesson_search.LessonSearchForm.query)
        await state.update_data(old="draft")
        request = AsyncMock(return_value=Message(message_id=2, date=0, chat=chat))
        monkeypatch.setattr(bot.session, "make_request", request)
        with i18n.context(), i18n.use_locale("ru"):
            await dispatcher.feed_update(
                bot,
                Update(
                    update_id=1,
                    message=Message(
                        message_id=1, date=0, chat=chat, from_user=user, text=i18n.gettext("menu.settings")
                    ),
                ),
            )
            assert await state.get_state() is None and await state.get_data() == {}
            search.search.assert_not_awaited()
            assert request.await_args_list[0].args[1].reply_markup == build_settings_keyboard()
    await dispatcher.storage.close()


@pytest.mark.parametrize("locale", list(Locale))
def test_mini_app_settings_and_course_launchers_use_inline_buttons_without_my_lessons(monkeypatch, locale):
    from manashelper.core.config import get_settings
    from manashelper.modules.schedule.presentation.keyboards.timetable import build_faculty_keyboard
    from manashelper.platform.telegram.keyboards.settings import build_settings_keyboard

    monkeypatch.setattr(get_settings(), "public_url", "https://example.com")
    with i18n.context(), i18n.use_locale(locale.value):
        settings_buttons = [button for row in build_settings_keyboard().inline_keyboard for button in row]
        assert all(button.callback_data != "settings:open_course_tracking" for button in settings_buttons)
        assert [button.web_app.url for button in settings_buttons if button.web_app] == [
            "https://example.com/app/?view=settings"
        ]
        course_buttons = [button for row in build_faculty_keyboard([]).inline_keyboard for button in row]
        assert [button.web_app.url for button in course_buttons if button.web_app] == [
            "https://example.com/app/?view=courses"
        ]
        assert all(button.web_app is None for row in build_study_keyboard().keyboard for button in row)


@pytest.mark.parametrize("action", list(NavigationAction))
@pytest.mark.parametrize("chat_type", ["private", "group", "supergroup"])
@pytest.mark.parametrize("locale", list(Locale))
@pytest.mark.parametrize("theme", list(Theme))
async def test_inline_navigation_clears_forms_only_in_private_chats(monkeypatch, action, chat_type, locale, theme):
    gamification = AsyncMock(is_enabled=AsyncMock(return_value=True))
    dispatcher = Dispatcher(gamification=gamification)
    register_handlers(dispatcher, navigation.router)
    dispatcher.callback_query.middleware(PrivateChatOnlyMiddleware())
    async with Bot(token="123456:development-placeholder") as bot:
        chat = Chat(id=42 if chat_type == "private" else -42, type=chat_type)
        user = User(id=42, is_bot=False, first_name="Student")
        state = FSMContext(dispatcher.storage, StorageKey(bot_id=bot.id, chat_id=chat.id, user_id=user.id))
        await state.set_state("Form:input")
        await state.update_data(draft="unfinished")
        message = Message(message_id=2, date=0, chat=chat, from_user=User(id=bot.id, is_bot=True, first_name="Bot"))
        request = AsyncMock(return_value=message)
        monkeypatch.setattr(bot.session, "make_request", request)
        with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
            await dispatcher.feed_update(
                bot,
                Update(
                    update_id=1,
                    callback_query=CallbackQuery(
                        id="navigation",
                        from_user=user,
                        chat_instance="chat",
                        message=message,
                        data=NavigationCallback(action=action).pack(),
                    ),
                ),
            )
            sent = [call.args[1] for call in request.await_args_list if isinstance(call.args[1], SendMessage)]
            if chat_type == "private":
                assert await state.get_state() is None and await state.get_data() == {}
                [response] = sent
                expected = (
                    build_main_keyboard(achievements_enabled=True)
                    if action == NavigationAction.MAIN
                    else build_study_keyboard()
                )
                assert response.reply_markup == expected
                assert response.text == i18n.gettext("menu.main" if action == NavigationAction.MAIN else "menu.study")
                if action == NavigationAction.MAIN:
                    gamification.is_enabled.assert_awaited_once_with(user.id)
            else:
                assert not sent
                assert await state.get_state() == "Form:input"
                assert await state.get_data() == {"draft": "unfinished"}
                gamification.is_enabled.assert_not_awaited()
    await dispatcher.storage.close()


async def test_search_back_button_cancels_query_and_restores_study_menu(monkeypatch):
    from manashelper.modules.schedule.presentation.callbacks import TimetableMenuAction, TimetableMenuCallback

    dispatcher = Dispatcher()
    for router in (navigation.router, timetable.router, lesson_search.router):
        register_handlers(dispatcher, router)
    async with Bot(token="123456:development-placeholder") as bot:
        chat = Chat(id=42, type="private")
        user = User(id=42, is_bot=False, first_name="Student")
        message = Message(message_id=2, date=0, chat=chat)
        request = AsyncMock(return_value=message)
        monkeypatch.setattr(bot.session, "make_request", request)
        state = FSMContext(dispatcher.storage, StorageKey(bot_id=bot.id, chat_id=chat.id, user_id=user.id))
        with i18n.context(), i18n.use_locale("ru"):
            payloads = [
                TimetableMenuCallback(action=TimetableMenuAction.OPEN_LESSON_SEARCH).pack(),
                NavigationCallback(action=NavigationAction.STUDY).pack(),
            ]
            for index, payload in enumerate(payloads):
                await dispatcher.feed_update(
                    bot,
                    Update(
                        update_id=index,
                        callback_query=CallbackQuery(
                            id=str(index),
                            from_user=user,
                            chat_instance="chat",
                            message=message,
                            data=payload,
                        ),
                    ),
                )
                if index == 0:
                    assert await state.get_state() == lesson_search.LessonSearchForm.query.state
                    prompt = request.await_args_list[-2].args[1]
                    assert (
                        prompt.reply_markup.inline_keyboard[0][0].callback_data
                        == NavigationCallback(action=NavigationAction.STUDY).pack()
                    )
            assert await state.get_state() is None and await state.get_data() == {}
            response = request.await_args_list[-2].args[1]
            assert response.reply_markup == build_study_keyboard()
    await dispatcher.storage.close()


@pytest.mark.parametrize("no_courses", [False, True])
async def test_study_submenu_opens_schedule_immediately_and_keeps_course_selection_first(monkeypatch, no_courses):
    schedule = AsyncMock(get_user_schedule=AsyncMock(return_value=[ScheduleLessonModel(1, "9:00-10:00", "Math")]))
    if no_courses:
        schedule.get_user_schedule.side_effect = NoTrackedCoursesError(42)
    dispatcher = Dispatcher(gamification=AsyncMock(is_enabled=AsyncMock(return_value=False)), schedule_query=schedule)
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
            assert methods[1].reply_markup.inline_keyboard[0][0].callback_data == "settings:open_course_tracking"
            assert len(methods[1].reply_markup.inline_keyboard[0]) == 1
            assert methods[1].text != i18n.gettext("menu.schedule")
            if no_courses:
                assert methods[1].text == i18n.gettext("schedule.no_tracked_courses")
            else:
                assert methods[1].reply_markup.inline_keyboard[0][0].text == i18n.gettext("schedule.change_courses")
            assert all(
                button.callback_data != "timetable_menu:open_lesson_search"
                for row in methods[1].reply_markup.inline_keyboard
                for button in row
            )
    await dispatcher.storage.close()
