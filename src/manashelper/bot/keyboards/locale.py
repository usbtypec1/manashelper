from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import LocaleCallback
from manashelper.localization.locale import Locale

# Language names are shown in their own language regardless of the bot's current locale, so a
# user recognizes their language before it's been determined at all.
NATIVE_NAMES: dict[Locale, str] = {
    Locale.KY: "Кыргызча",
    Locale.RU: "Русский",
    Locale.EN: "English",
    Locale.TR: "Türkçe",
}

_BUTTON_LABELS: dict[Locale, str] = {
    Locale.KY: "🇰🇬 Кыргызча",
    Locale.RU: "🇷🇺 Русский",
    Locale.EN: "🇬🇧 English",
    Locale.TR: "🇹🇷 Türkçe",
}

# Shown before a locale is known at all, so it's spelled out in every supported language at once.
LOCALE_PROMPT_TEXT = "🌐 Тилди тандаңыз / Выберите язык / Please choose your language / Lütfen dilinizi seçin"


def build_locale_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for locale, label in _BUTTON_LABELS.items():
        builder.button(text=label, callback_data=LocaleCallback(locale=locale))
    builder.adjust(1)
    return builder.as_markup()
