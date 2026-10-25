from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from manashelper.services.eders_models import DeadlineFilter
from manashelper.services.eders_tracking import EdersSetting


class ObisAction(StrEnum):
    START_CREDENTIALS = "start_credentials"
    ACCEPT_TERMS = "accept_terms"
    CANCEL_CREDENTIALS = "cancel_credentials"
    CLEAR_CREDENTIALS = "clear_credentials"
    CONFIRM_CLEAR_CREDENTIALS = "confirm_clear_credentials"


class ObisCallback(CallbackData, prefix="obis"):
    action: ObisAction


class ObisResultsPageCallback(CallbackData, prefix="obis_results_page"):
    page: int


class EdersPageCallback(CallbackData, prefix="eders"):
    selected: DeadlineFilter
    page: int = 0


class EdersSettingCallback(CallbackData, prefix="eders_setting"):
    setting: EdersSetting


class SettingsAction(StrEnum):
    OPEN_NOTIFICATIONS = "open_notifications"
    OPEN_EDERS_NOTIFICATIONS = "open_eders_notifications"
    OPEN_FOOD_MENU_NOTIFICATIONS = "open_food_menu_notifications"
    BACK_TO_NOTIFICATIONS = "back_to_notifications"
    OPEN_COURSE_TRACKING = "open_course_tracking"
    OPEN_OBIS = "open_obis"
    OPEN_LANGUAGE = "open_language"
    OPEN_PHONE_NUMBERS = "open_phone_numbers"
    OPEN_FEEDBACK = "open_feedback"
    OPEN_DONATIONS = "open_donations"
    BACK_TO_SETTINGS = "back_to_settings"


class SettingsCallback(CallbackData, prefix="settings"):
    action: SettingsAction
