from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback


def build_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("settings.notifications"), callback_data=SettingsCallback(action=SettingsAction.OPEN_NOTIFICATIONS)
    )
    builder.button(
        text=_("settings.my_lessons"), callback_data=SettingsCallback(action=SettingsAction.OPEN_COURSE_TRACKING)
    )
    builder.button(text=_("settings.obis_credentials"), callback_data=SettingsCallback(action=SettingsAction.OPEN_OBIS))
    builder.button(
        text=_("settings.phone_numbers"), callback_data=SettingsCallback(action=SettingsAction.OPEN_PHONE_NUMBERS)
    )
    builder.button(text=_("settings.language"), callback_data=SettingsCallback(action=SettingsAction.OPEN_LANGUAGE))
    builder.button(text=_("settings.feedback"), callback_data=SettingsCallback(action=SettingsAction.OPEN_FEEDBACK))
    builder.adjust(1)
    return builder.as_markup()
