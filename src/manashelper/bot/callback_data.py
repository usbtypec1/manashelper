import uuid
from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from manashelper.localization.locale import Locale
from manashelper.services.food_menu_cleanup_settings import FoodMenuCleanupOption
from manashelper.services.food_menu_notification_settings import FoodMenuMeal
from manashelper.services.notification_settings import NotificationSetting


class FacultyCallback(CallbackData, prefix="faculty"):
    id: uuid.UUID


class DepartmentCallback(CallbackData, prefix="department"):
    id: uuid.UUID


class CourseCallback(CallbackData, prefix="course"):
    id: int


class ScheduleDayCallback(CallbackData, prefix="schedule_day"):
    weekday: int


class TimetableMenuAction(StrEnum):
    OPEN_MY_SCHEDULE = "open_my_schedule"
    OPEN_LESSON_SEARCH = "open_lesson_search"


class TimetableMenuCallback(CallbackData, prefix="timetable_menu"):
    action: TimetableMenuAction


class LessonSearchPageCallback(CallbackData, prefix="lesson_search_page"):
    page: int


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


class FoodMenuNotificationWeekdayCallback(CallbackData, prefix="food_menu_notification_weekday"):
    weekday: int


class FoodMenuNotificationMealCallback(CallbackData, prefix="food_menu_notification_meal"):
    meal: FoodMenuMeal


class FoodMenuNotificationNoopCallback(CallbackData, prefix="food_menu_notification_noop"):
    pass


class FoodMenuCleanupOpenCallback(CallbackData, prefix="food_menu_cleanup_open"):
    pass


class FoodMenuCleanupSetCallback(CallbackData, prefix="food_menu_cleanup_set"):
    option: FoodMenuCleanupOption


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
    OPEN_LANGUAGE = "open_language"
    OPEN_PHONE_NUMBERS = "open_phone_numbers"
    BACK_TO_SETTINGS = "back_to_settings"


class SettingsCallback(CallbackData, prefix="settings"):
    action: SettingsAction


class NotificationSettingCallback(CallbackData, prefix="notification_setting"):
    setting: NotificationSetting


class LocaleCallback(CallbackData, prefix="locale"):
    locale: Locale


class VersionsPageCallback(CallbackData, prefix="versions_page"):
    page: int


class VersionCallback(CallbackData, prefix="version"):
    version: str
    page: int


class AdvertisementFormAction(StrEnum):
    SKIP_PRICE = "skip_price"
    DONE_MEDIA = "done_media"
    CONFIRM_SUBMIT = "confirm_submit"
    CANCEL = "cancel"


class AdvertisementFormCallback(CallbackData, prefix="ad_form"):
    action: AdvertisementFormAction


class AdvertisementExpiryOption(StrEnum):
    MIN_45 = "min_45"
    HOURS_6 = "hours_6"
    HOURS_24 = "hours_24"
    DAYS_7 = "days_7"
    NONE = "none"


class AdvertisementExpiryCallback(CallbackData, prefix="ad_expiry"):
    option: AdvertisementExpiryOption


class AdvertisementsPageCallback(CallbackData, prefix="ads_page"):
    page: int


class AdvertisementCallback(CallbackData, prefix="ad"):
    id: uuid.UUID
    page: int


class AdvertisementDeleteAction(StrEnum):
    REQUEST = "request"
    CONFIRM = "confirm"
    CANCEL = "cancel"


class AdvertisementDeleteCallback(CallbackData, prefix="ad_delete"):
    id: uuid.UUID
    action: AdvertisementDeleteAction
    page: int


class AdvertisementModerationAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    ADD_COMMENT = "add_comment"
    SKIP_COMMENT = "skip_comment"


class AdvertisementModerationCallback(CallbackData, prefix="ad_moderation"):
    id: uuid.UUID
    action: AdvertisementModerationAction


class PhoneNumberAction(StrEnum):
    ADD = "add"


class PhoneNumberActionCallback(CallbackData, prefix="phone_number_action"):
    action: PhoneNumberAction


class PhoneNumberDeleteCallback(CallbackData, prefix="phone_number_delete"):
    id: uuid.UUID
