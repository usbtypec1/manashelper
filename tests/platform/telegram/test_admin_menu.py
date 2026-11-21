from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SetChatMenuButton
from aiogram.types import MenuButtonDefault, MenuButtonWebApp

from manashelper.core.config import get_settings
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.admin_menu import setup_mini_app_menu_buttons
from manashelper.platform.telegram.keyboards.settings import build_settings_keyboard
from manashelper.platform.telegram.navigation import build_main_keyboard


@pytest.mark.parametrize("public_url", ["https://example.com", None])
async def test_admin_menu_button_is_scoped_to_personal_ids(public_url):
    bot = AsyncMock()
    settings = get_settings().model_copy(
        update={"public_url": public_url, "admin_chat_id": -100123, "admin_user_ids": frozenset({101, 102})}
    )
    bot.set_chat_menu_button.side_effect = [
        True,
        TelegramBadRequest(method=SetChatMenuButton(chat_id=101), message="chat not found"),
        True,
    ]
    await setup_mini_app_menu_buttons(bot, settings)

    calls = [call.kwargs for call in bot.set_chat_menu_button.await_args_list]
    assert [call.get("chat_id") for call in calls] == [None, 101, 102]
    for call, destination, label in zip(
        calls, ("settings", "admin", "admin"), ("⚙️ Настройки", "Админка", "Админка"), strict=True
    ):
        button = call["menu_button"]
        if public_url:
            assert isinstance(button, MenuButtonWebApp)
            assert button.web_app.url == f"{public_url}/app/{destination}"
            assert button.text == label
        else:
            assert isinstance(button, MenuButtonDefault)


@pytest.mark.parametrize("public_url", ["https://example.com", None])
def test_reply_keyboard_has_no_settings_and_old_menu_opens_the_available_settings(monkeypatch, public_url):
    monkeypatch.setattr(get_settings(), "public_url", public_url)
    with i18n.context(), i18n.use_locale("ru"):
        main = build_main_keyboard(achievements_enabled=True)
        settings = build_settings_keyboard()
        assert all(button.text != i18n.gettext("menu.settings") for row in main.keyboard for button in row)
    buttons = [button for row in settings.inline_keyboard for button in row]
    assert any(button.callback_data == "settings:open_notifications" for button in buttons) == (public_url is None)
    assert [button.web_app.url for button in buttons if button.web_app] == (
        [f"{public_url}/app/settings"] if public_url else []
    )


@pytest.mark.parametrize(
    ("chat_id", "configured_ids", "expected"),
    [(101, None, {101}), (-100123, None, set()), (101, frozenset(), set()), (101, frozenset({102}), {102})],
)
def test_admin_panel_access_configuration(chat_id, configured_ids, expected):
    settings = get_settings().model_copy(update={"admin_chat_id": chat_id, "admin_user_ids": configured_ids})
    assert settings.admin_panel_user_ids == expected
