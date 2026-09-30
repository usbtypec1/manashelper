from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import BroadcastAction, BroadcastCallback


def build_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("common.send"), callback_data=BroadcastCallback(action=BroadcastAction.CONFIRM))
    builder.button(text=_("common.cancel"), callback_data=BroadcastCallback(action=BroadcastAction.CANCEL))
    builder.adjust(2)
    return builder.as_markup()
