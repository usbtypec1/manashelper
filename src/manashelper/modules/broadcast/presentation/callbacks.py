from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class BroadcastAction(StrEnum):
    CONFIRM = "confirm"
    CANCEL = "cancel"
    BUTTONS = "buttons"
    WITHOUT_BUTTONS = "without_buttons"


class BroadcastCallback(CallbackData, prefix="broadcast"):
    action: BroadcastAction
