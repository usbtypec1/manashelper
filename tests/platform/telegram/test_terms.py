from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, User

from manashelper.core.config import get_settings
from manashelper.modules.obis.presentation.keyboards import build_terms_keyboard
from manashelper.modules.obis.presentation.router import on_terms
from manashelper.platform.i18n.catalog import i18n


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
async def test_terms_are_readable_without_public_url_and_preserve_acceptance(monkeypatch, locale):
    monkeypatch.setattr(get_settings(), "public_url", None)
    async with Bot("123456:development-placeholder") as bot:
        user = User(id=975001, is_bot=False, first_name="Student")
        message = Message(message_id=1, date=0, chat=Chat(id=user.id, type="private"), from_user=user).as_(bot)
        callback = CallbackQuery(id="terms", from_user=user, message=message, chat_instance="chat").as_(bot)
        request = AsyncMock(return_value=message)
        monkeypatch.setattr(bot.session, "make_request", request)
        with i18n.context(), i18n.use_locale(locale):
            keyboard = build_terms_keyboard()
            assert keyboard.inline_keyboard[0][0].callback_data == "obis:terms"
            assert keyboard.inline_keyboard[1][0].callback_data == "obis:accept_terms"
            await on_terms(callback)
        texts = [call.args[1].text for call in request.await_args_list if call.args[1].__api_method__ == "sendMessage"]
        assert len(texts) == 9
        assert all(len(text) <= 4096 and "terms." not in text for text in texts)
        assert "transkript-detailed" in " ".join(texts)
        assert "core_completion_update_activity_completion_status_manually" in " ".join(texts)


def test_terms_web_app_link_uses_public_url_and_current_locale(monkeypatch):
    monkeypatch.setattr(get_settings(), "public_url", "https://example.com/")
    with i18n.context(), i18n.use_locale("ky"):
        keyboard = build_terms_keyboard()
    button = keyboard.inline_keyboard[0][0]
    assert button.web_app is not None
    assert button.web_app.url == "https://example.com/app/?view=terms&lang=ky"
    assert keyboard.inline_keyboard[1][0].callback_data == "obis:accept_terms"
