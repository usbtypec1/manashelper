from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandObject
from aiogram.types import Chat, Message, User

from manashelper.core.config import get_settings
from manashelper.localization.locale import Locale
from manashelper.modules.gamification.presentation import router
from manashelper.platform.i18n.catalog import i18n


@pytest.mark.parametrize("locale", list(Locale))
@pytest.mark.parametrize("args", [None, "invalid", "0", str(2**63)])
async def test_command_usage_is_plain_text_under_default_html_mode(monkeypatch, locale, args):
    settings = get_settings()
    use_case = AsyncMock()
    async with Bot("123456:development-placeholder", default=DefaultBotProperties(parse_mode=ParseMode.HTML)) as bot:
        message = Message(
            message_id=1,
            date=0,
            chat=Chat(id=settings.admin_chat_id, type="supergroup"),
            from_user=User(id=42, is_bot=False, first_name="Admin"),
        ).as_(bot)
        request = AsyncMock(return_value=message)
        monkeypatch.setattr(bot.session, "make_request", request)
        with i18n.context(), i18n.use_locale(locale.value):
            await router.set_gamification(message, CommandObject(command="gamification", args=args), use_case, settings)
            [method] = [call.args[1] for call in request.await_args_list]
            assert method.parse_mode is None
            usage_key = "gamification.access_usage"
            assert method.text == i18n.gettext(usage_key)
            assert "<" in method.text and ">" in method.text
        use_case.execute.assert_not_awaited()
