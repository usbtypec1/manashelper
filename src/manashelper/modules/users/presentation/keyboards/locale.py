from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.localization.locale import Locale
from manashelper.modules.users.presentation.callbacks import LocaleCallback
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback
from manashelper.platform.telegram.navigation import build_navigation_keyboard


def native_language_name(locale: Locale) -> str:
    return i18n.gettext("language.native_name", locale=locale.value)


def build_locale_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for locale in Locale:
        label = i18n.gettext("language.button", locale=locale.value)
        builder.button(text=label, callback_data=LocaleCallback(locale=locale))
    builder.adjust(1)
    builder.button(text=_("common.back"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_SETTINGS))
    builder.adjust(1)
    builder.attach(build_navigation_keyboard())
    return builder.as_markup()
