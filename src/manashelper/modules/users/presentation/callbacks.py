from aiogram.filters.callback_data import CallbackData

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme


class LocaleCallback(CallbackData, prefix="locale"):
    locale: Locale


class ThemeCallback(CallbackData, prefix="theme"):
    theme: Theme
