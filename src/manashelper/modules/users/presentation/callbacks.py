import uuid
from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme


class LocaleCallback(CallbackData, prefix="locale"):
    locale: Locale


class ThemeCallback(CallbackData, prefix="theme"):
    theme: Theme


class PhoneNumberAction(StrEnum):
    ADD = "add"


class PhoneNumberActionCallback(CallbackData, prefix="phone_number_action"):
    action: PhoneNumberAction


class PhoneNumberDeleteCallback(CallbackData, prefix="phone_number_delete"):
    id: uuid.UUID
