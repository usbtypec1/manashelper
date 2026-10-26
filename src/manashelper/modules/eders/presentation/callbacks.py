from aiogram.filters.callback_data import CallbackData

from manashelper.modules.eders.application.models import DeadlineFilter
from manashelper.modules.eders.application.tracking import EdersSetting


class EdersPageCallback(CallbackData, prefix="eders"):
    selected: DeadlineFilter
    page: int = 0


class EdersSettingCallback(CallbackData, prefix="eders_setting"):
    setting: EdersSetting
