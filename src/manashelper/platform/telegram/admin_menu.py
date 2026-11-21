import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import MenuButtonDefault, MenuButtonWebApp, WebAppInfo
from aiogram.utils.i18n import gettext as _

from manashelper.core.config import Settings
from manashelper.localization.locale import DEFAULT_LOCALE
from manashelper.platform.i18n.catalog import i18n

logger = logging.getLogger(__name__)


async def set_admin_menu_button(bot: Bot, settings: Settings, user_id: int) -> None:
    if user_id not in settings.admin_panel_user_ids:
        return
    button: MenuButtonWebApp | MenuButtonDefault
    if settings.public_url:
        button = MenuButtonWebApp(
            text=_("miniapp.admin.title"),
            web_app=WebAppInfo(url=f"{settings.public_url}/app/admin"),
        )
    else:
        button = MenuButtonDefault()
    try:
        await bot.set_chat_menu_button(chat_id=user_id, menu_button=button)
    except TelegramAPIError:
        logger.warning("Could not set the admin menu button for Telegram user %d", user_id, exc_info=True)


async def setup_mini_app_menu_buttons(bot: Bot, settings: Settings) -> None:
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        button = (
            MenuButtonWebApp(text=_("menu.settings"), web_app=WebAppInfo(url=f"{settings.public_url}/app/settings"))
            if settings.public_url
            else MenuButtonDefault()
        )
        try:
            await bot.set_chat_menu_button(menu_button=button)
        except TelegramAPIError:
            logger.warning("Could not set the default Mini App menu button", exc_info=True)
        for user_id in sorted(settings.admin_panel_user_ids):
            await set_admin_menu_button(bot, settings, user_id)
