from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.methods import SendMessage
from aiogram.types import Chat, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, Update, User

from manashelper.core.config import get_settings
from manashelper.localization.locale import Locale
from manashelper.modules.gamification.presentation import router
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.navigation import build_main_keyboard, build_study_keyboard


@pytest.mark.parametrize("locale", list(Locale))
@pytest.mark.parametrize(
    "enabled,public_url", [(True, "https://example.com"), (False, "https://example.com"), (True, None)]
)
async def test_reply_achievement_button_sends_separate_inline_launch_only_for_enabled_users(
    monkeypatch, locale, enabled, public_url
):
    settings = get_settings()
    monkeypatch.setattr(settings, "public_url", public_url)
    query = AsyncMock(is_enabled=AsyncMock(return_value=enabled))
    dispatcher = Dispatcher(query=query, settings=settings)
    # Reuse the real translated filter and handler without attaching the singleton router.
    handler = router.router.message.handlers[0]
    dispatcher.message.register(
        getattr(handler.callback, "__dishka_orig_func__", handler.callback),
        *(item.callback for item in handler.filters),
        flags=handler.flags.copy(),
    )
    async with Bot("123456:development-placeholder") as bot:
        user = User(id=42, is_bot=False, first_name="Student")
        chat = Chat(id=user.id, type="private")
        request = AsyncMock(return_value=Message(message_id=2, date=0, chat=chat))
        monkeypatch.setattr(bot.session, "make_request", request)
        state = FSMContext(dispatcher.storage, StorageKey(bot_id=bot.id, chat_id=user.id, user_id=user.id))
        await state.set_state("Form:input")
        await state.update_data(draft="unfinished")
        with i18n.context(), i18n.use_locale(locale.value):
            keyboard = build_main_keyboard(achievements_enabled=enabled)
            assert isinstance(keyboard, ReplyKeyboardMarkup)
            assert isinstance(build_study_keyboard(), ReplyKeyboardMarkup)
            buttons = [button for row in keyboard.keyboard for button in row]
            achievement_buttons = [button for button in buttons if button.text == i18n.gettext("menu.achievements")]
            assert len(achievement_buttons) == int(enabled and bool(public_url))
            # The bottom button sends text; Telegram authorization starts only at the inline button.
            assert all(button.web_app is None for button in buttons)
            await dispatcher.feed_update(
                bot,
                Update(
                    update_id=1,
                    message=Message(
                        message_id=1,
                        date=0,
                        chat=chat,
                        from_user=user,
                        text=i18n.gettext("menu.achievements"),
                    ),
                ),
            )
            [response] = [call.args[1] for call in request.await_args_list]
            assert isinstance(response, SendMessage)
            if enabled and public_url:
                assert response.text == i18n.gettext("gamification.open_prompt")
                assert isinstance(response.reply_markup, InlineKeyboardMarkup)
                [button] = [button for row in response.reply_markup.inline_keyboard for button in row]
                assert button.web_app.url == "https://example.com/app/"
                query.is_enabled.assert_awaited_once_with(user.id)
            else:
                assert response.text == i18n.gettext("gamification.unavailable")
                assert response.reply_markup is None
        assert await state.get_state() is None
        assert await state.get_data() == {}
    await dispatcher.storage.close()
