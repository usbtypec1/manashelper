from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import FeedbackAction, FeedbackCallback


def build_feedback_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("❌ Cancel"), callback_data=FeedbackCallback(action=FeedbackAction.CANCEL))
    return builder.as_markup()
