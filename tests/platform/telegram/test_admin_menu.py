from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SetChatMenuButton
from aiogram.types import MenuButtonDefault, MenuButtonWebApp

from manashelper.core.config import get_settings
from manashelper.platform.telegram.admin_menu import setup_admin_menu_buttons


@pytest.mark.parametrize("public_url", ["https://example.com", None])
async def test_admin_menu_button_is_scoped_to_personal_ids(public_url):
    bot = AsyncMock()
    settings = get_settings().model_copy(
        update={"public_url": public_url, "admin_chat_id": -100123, "admin_user_ids": frozenset({101, 102})}
    )
    bot.set_chat_menu_button.side_effect = [
        TelegramBadRequest(method=SetChatMenuButton(chat_id=101), message="chat not found"),
        True,
    ]
    await setup_admin_menu_buttons(bot, settings)

    calls = [call.kwargs for call in bot.set_chat_menu_button.await_args_list]
    assert [call["chat_id"] for call in calls] == [101, 102]
    for call in calls:
        button = call["menu_button"]
        if public_url:
            assert isinstance(button, MenuButtonWebApp)
            assert button.web_app.url == f"{public_url}/app/admin"
            assert button.text == "Админка"
        else:
            assert isinstance(button, MenuButtonDefault)


@pytest.mark.parametrize(
    ("chat_id", "configured_ids", "expected"),
    [(101, None, {101}), (-100123, None, set()), (101, frozenset(), set()), (101, frozenset({102}), {102})],
)
def test_admin_panel_access_configuration(chat_id, configured_ids, expected):
    settings = get_settings().model_copy(update={"admin_chat_id": chat_id, "admin_user_ids": configured_ids})
    assert settings.admin_panel_user_ids == expected
