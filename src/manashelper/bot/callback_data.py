import uuid
from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class FacultyCallback(CallbackData, prefix="faculty"):
    id: uuid.UUID


class DepartmentCallback(CallbackData, prefix="department"):
    id: uuid.UUID


class CourseCallback(CallbackData, prefix="course"):
    id: int


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


class ObisAction(StrEnum):
    ATTENDANCE = "attendance"
    EXAMS = "exams"
    START_CREDENTIALS = "start_credentials"
    ACCEPT_TERMS = "accept_terms"
    CANCEL_CREDENTIALS = "cancel_credentials"


class ObisCallback(CallbackData, prefix="obis"):
    action: ObisAction
