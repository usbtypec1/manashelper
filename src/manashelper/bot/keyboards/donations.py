from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import DonationBankCallback, SettingsAction, SettingsCallback
from manashelper.services.donations import DonationBank


def build_donations_keyboard(banks: list[DonationBank]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for bank in banks:
        builder.button(text=bank.name, callback_data=DonationBankCallback(bank_id=bank.id))
    builder.button(text=_("◀️ Back to settings"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_SETTINGS))
    builder.adjust(1)
    return builder.as_markup()
