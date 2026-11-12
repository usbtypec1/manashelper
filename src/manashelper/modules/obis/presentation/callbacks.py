from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from manashelper.modules.notifications.settings import NotificationSetting


class ObisAction(StrEnum):
    MENU = "menu"
    ATTENDANCE = "attendance"
    GRADES = "grades"
    NOTIFICATIONS = "notifications"
    START_CREDENTIALS = "start_credentials"
    TERMS = "terms"
    ACCEPT_TERMS = "accept_terms"
    CANCEL_CREDENTIALS = "cancel_credentials"
    CLEAR_CREDENTIALS = "clear_credentials"
    CONFIRM_CLEAR_CREDENTIALS = "confirm_clear_credentials"


class ObisCallback(CallbackData, prefix="obis"):
    action: ObisAction


class ObisResultsPageCallback(CallbackData, prefix="obis_results_page"):
    page: int


class ObisNotificationSettingCallback(CallbackData, prefix="obis_notification_setting"):
    setting: NotificationSetting
