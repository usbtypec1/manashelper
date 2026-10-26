from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class BroadcastAction(StrEnum):
    CONFIRM = "confirm"
    CANCEL = "cancel"


class BroadcastCallback(CallbackData, prefix="broadcast"):
    action: BroadcastAction
