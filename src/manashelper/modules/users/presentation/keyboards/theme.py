from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.localization.theme import Theme
from manashelper.modules.users.presentation.callbacks import ThemeCallback
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback


def theme_name(theme: Theme) -> str:
    if theme == Theme.HALLOWEEN:
        return _("theme.halloween")
    return _("theme.basic")


def build_theme_keyboard(selected: Theme) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for theme in Theme:
        label = theme_name(theme)
        builder.button(text=f"✅ {label}" if theme == selected else label, callback_data=ThemeCallback(theme=theme))
    builder.button(text=_("common.back"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_SETTINGS))
    builder.adjust(1)
    return builder.as_markup()
