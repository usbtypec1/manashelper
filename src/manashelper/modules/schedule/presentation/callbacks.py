import uuid
from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


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
