import uuid
from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from manashelper.services.food_menu_notification_settings_service import FoodMenuMeal
from manashelper.services.notification_settings_service import NotificationSetting


class FacultyCallback(CallbackData, prefix="faculty"):
    id: uuid.UUID


class DepartmentCallback(CallbackData, prefix="department"):
    id: uuid.UUID


class CourseCallback(CallbackData, prefix="course"):
    id: int


class ScheduleDayCallback(CallbackData, prefix="schedule_day"):
    weekday: int


class FoodMenuDay(StrEnum):
    TODAY = "today"
    TOMORROW = "tomorrow"
    AFTER_TOMORROW = "after_tomorrow"


FOOD_MENU_DAY_TO_SKIP_DAYS = {
    FoodMenuDay.TODAY: 0,
    FoodMenuDay.TOMORROW: 1,
    FoodMenuDay.AFTER_TOMORROW: 2,
}


class FoodMenuCallback(CallbackData, prefix="food_menu"):
    day: FoodMenuDay


class FoodMenuRatingCallback(CallbackData, prefix="food_menu_rating"):
    daily_menu_id: uuid.UUID
    rating: int


class FoodMenuNotificationDayCallback(CallbackData, prefix="food_menu_notification_day"):
    weekday: int
    meal: FoodMenuMeal


class FoodMenuNotificationBulkCallback(CallbackData, prefix="food_menu_notification_bulk"):
    enable: bool


class FoodMenuNotificationNoopCallback(CallbackData, prefix="food_menu_notification_noop"):
    pass


class ObisAction(StrEnum):
    START_CREDENTIALS = "start_credentials"
    ACCEPT_TERMS = "accept_terms"
    CANCEL_CREDENTIALS = "cancel_credentials"
    CLEAR_CREDENTIALS = "clear_credentials"
    CONFIRM_CLEAR_CREDENTIALS = "confirm_clear_credentials"


class ObisCallback(CallbackData, prefix="obis"):
    action: ObisAction


class SettingsAction(StrEnum):
    OPEN_NOTIFICATIONS = "open_notifications"
    OPEN_FOOD_MENU_NOTIFICATIONS = "open_food_menu_notifications"
    BACK_TO_NOTIFICATIONS = "back_to_notifications"
    OPEN_COURSE_TRACKING = "open_course_tracking"
    OPEN_OBIS = "open_obis"
    BACK_TO_SETTINGS = "back_to_settings"


class SettingsCallback(CallbackData, prefix="settings"):
    action: SettingsAction


class NotificationSettingCallback(CallbackData, prefix="notification_setting"):
    setting: NotificationSetting
