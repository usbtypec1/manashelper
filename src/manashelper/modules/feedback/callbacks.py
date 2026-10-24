from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class FeedbackAction(StrEnum):
    CANCEL = "cancel"


class FeedbackCallback(CallbackData, prefix="feedback"):
    action: FeedbackAction
