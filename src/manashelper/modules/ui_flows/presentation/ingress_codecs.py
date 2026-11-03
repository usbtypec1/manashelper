"""Registered legacy callback codecs; no handler discovery or executable DB parser."""

from aiogram.filters.callback_data import CallbackData

from manashelper.modules.advertisements.presentation.callbacks import (
    AdvertisementCallback,
    AdvertisementDeleteCallback,
    AdvertisementExpiryCallback,
    AdvertisementFormCallback,
    AdvertisementModerationCallback,
    AdvertisementsPageCallback,
)
from manashelper.modules.broadcast.callbacks import (
    BroadcastCallback,
)
from manashelper.modules.eders.presentation.callbacks import (
    EdersPageCallback,
    EdersSettingCallback,
)
from manashelper.modules.feedback.callbacks import (
    FeedbackCallback,
)
from manashelper.modules.food_menu.presentation.callbacks import (
    FoodMenuCallback,
    FoodMenuCleanupOpenCallback,
    FoodMenuCleanupSetCallback,
    FoodMenuDateCallback,
    FoodMenuNotificationBulkCallback,
    FoodMenuNotificationDayCallback,
    FoodMenuNotificationMealCallback,
    FoodMenuNotificationNoopCallback,
    FoodMenuNotificationWeekdayCallback,
    FoodMenuOpenCallback,
    FoodMenuRatingCallback,
)
from manashelper.modules.notifications.callbacks import (
    NotificationSettingCallback,
)
from manashelper.modules.obis.presentation.callbacks import (
    ObisCallback,
    ObisResultsPageCallback,
)
from manashelper.modules.schedule.presentation.callbacks import (
    CourseCallback,
    DepartmentCallback,
    FacultyCallback,
    LessonSearchPageCallback,
    ScheduleDayCallback,
    TimetableMenuCallback,
)
from manashelper.modules.student_questions.callbacks import (
    StudentQuestionsAnswerCallback,
    StudentQuestionsControlCallback,
)
from manashelper.modules.ui_flows.presentation.callbacks import (
    UiFlowCallback,
)
from manashelper.modules.users.presentation.callbacks import (
    LocaleCallback,
    PhoneNumberActionCallback,
    PhoneNumberDeleteCallback,
    ThemeCallback,
)
from manashelper.platform.telegram.callbacks import (
    SettingsCallback,
)

CODECS: dict[str, type[CallbackData]] = {
    "ad": AdvertisementCallback,
    "ad_delete": AdvertisementDeleteCallback,
    "ad_expiry": AdvertisementExpiryCallback,
    "ad_form": AdvertisementFormCallback,
    "ad_moderation": AdvertisementModerationCallback,
    "ads_page": AdvertisementsPageCallback,
    "broadcast": BroadcastCallback,
    "eders": EdersPageCallback,
    "eders_setting": EdersSettingCallback,
    "feedback": FeedbackCallback,
    "food_menu": FoodMenuCallback,
    "food_menu_cleanup_open": FoodMenuCleanupOpenCallback,
    "food_menu_cleanup_set": FoodMenuCleanupSetCallback,
    "food_menu_date": FoodMenuDateCallback,
    "food_menu_notification_bulk": FoodMenuNotificationBulkCallback,
    "food_menu_notification_day": FoodMenuNotificationDayCallback,
    "food_menu_notification_meal": FoodMenuNotificationMealCallback,
    "food_menu_notification_noop": FoodMenuNotificationNoopCallback,
    "food_menu_notification_weekday": FoodMenuNotificationWeekdayCallback,
    "food_menu_open": FoodMenuOpenCallback,
    "food_menu_rating": FoodMenuRatingCallback,
    "notification_setting": NotificationSettingCallback,
    "obis": ObisCallback,
    "obis_results_page": ObisResultsPageCallback,
    "course": CourseCallback,
    "department": DepartmentCallback,
    "faculty": FacultyCallback,
    "lesson_search_page": LessonSearchPageCallback,
    "schedule_day": ScheduleDayCallback,
    "timetable_menu": TimetableMenuCallback,
    "sqa": StudentQuestionsAnswerCallback,
    "sqc": StudentQuestionsControlCallback,
    "uf": UiFlowCallback,
    "locale": LocaleCallback,
    "phone_number_action": PhoneNumberActionCallback,
    "phone_number_delete": PhoneNumberDeleteCallback,
    "theme": ThemeCallback,
    "settings": SettingsCallback,
}
