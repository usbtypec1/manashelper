from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback
from manashelper.platform.telegram.navigation import build_mini_app_button, build_navigation_keyboard


def build_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("settings.notifications"), callback_data=SettingsCallback(action=SettingsAction.OPEN_NOTIFICATIONS)
    )
    mini_app = build_mini_app_button()
    if mini_app is not None:
        builder.row(mini_app)
    builder.button(text=_("settings.obis_credentials"), callback_data=SettingsCallback(action=SettingsAction.OPEN_OBIS))
    builder.button(text=_("settings.language"), callback_data=SettingsCallback(action=SettingsAction.OPEN_LANGUAGE))
    builder.button(text=_("settings.theme"), callback_data=SettingsCallback(action=SettingsAction.OPEN_THEME))
    builder.button(text=_("settings.feedback"), callback_data=SettingsCallback(action=SettingsAction.OPEN_FEEDBACK))
    builder.adjust(1)
    builder.attach(build_navigation_keyboard())
    return builder.as_markup()
