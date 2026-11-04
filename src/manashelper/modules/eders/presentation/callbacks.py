from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from manashelper.modules.eders.application.models import DeadlineFilter
from manashelper.modules.eders.application.tracking import EdersSetting


class EdersAction(StrEnum):
    MENU = "menu"
    MATERIALS = "materials"
    DEADLINES = "deadlines"
    NOTIFICATIONS = "notifications"


class EdersMenuCallback(CallbackData, prefix="eders_menu"):
    action: EdersAction


class EdersPageCallback(CallbackData, prefix="eders"):
    selected: DeadlineFilter
    page: int = 0


class EdersSettingCallback(CallbackData, prefix="eders_setting"):
    setting: EdersSetting
