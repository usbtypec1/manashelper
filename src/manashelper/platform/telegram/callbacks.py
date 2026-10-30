from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


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
    BACK_TO_SETTINGS = "back_to_settings"


class SettingsCallback(CallbackData, prefix="settings"):
    action: SettingsAction
