import uuid
from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from manashelper.modules.food_menu.application.food_menu_cleanup_settings import FoodMenuCleanupOption
from manashelper.modules.food_menu.application.food_menu_notification_settings import FoodMenuMeal


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


class FoodMenuOpenCallback(CallbackData, prefix="food_menu_open"):
    pass


class FoodMenuDateCallback(CallbackData, prefix="food_menu_date"):
    menu_date: str


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
