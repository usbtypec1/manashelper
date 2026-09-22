from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import (
    PhoneNumberAction,
    PhoneNumberActionCallback,
    PhoneNumberDeleteCallback,
    SettingsAction,
    SettingsCallback,
)
from manashelper.services.user_contact import PhoneNumberSummary


def build_contact_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_("📱 Share phone number"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def build_phone_numbers_keyboard(phone_numbers: list[PhoneNumberSummary]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for phone_number in phone_numbers:
        builder.button(
            text=f"🗑 {phone_number.phone_number}",
            callback_data=PhoneNumberDeleteCallback(id=phone_number.id),
        )
    builder.adjust(1)

    action_builder = InlineKeyboardBuilder()
    action_builder.button(
        text=_("➕ Add a phone number"), callback_data=PhoneNumberActionCallback(action=PhoneNumberAction.ADD)
    )
    action_builder.button(text=_("◀️ Back"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_SETTINGS))
    action_builder.adjust(1)
    builder.attach(action_builder)
    return builder.as_markup()
