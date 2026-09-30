from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import LocaleCallback
from manashelper.localization.i18n import i18n
from manashelper.localization.locale import Locale


def native_language_name(locale: Locale) -> str:
    return i18n.gettext("language.native_name", locale=locale.value)


def build_locale_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for locale in Locale:
        label = i18n.gettext("language.button", locale=locale.value)
        builder.button(text=label, callback_data=LocaleCallback(locale=locale))
    builder.adjust(1)
    return builder.as_markup()
