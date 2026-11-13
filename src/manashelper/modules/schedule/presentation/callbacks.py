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
    MENU = "menu"
    OPEN_MY_SCHEDULE = "open_my_schedule"
    OPEN_LESSON_SEARCH = "open_lesson_search"
    OPEN_NOW = "open_now"
    OPEN_FREE_ROOMS = "open_free_rooms"


class TimetableMenuCallback(CallbackData, prefix="timetable_menu"):
    action: TimetableMenuAction


class LessonSearchPageCallback(CallbackData, prefix="lesson_search_page"):
    page: int


class FreeRoomsCallback(CallbackData, prefix="free_rooms"):
    """weekday=0 means "now"; building="" shows the building overview."""

    weekday: int
    period: int
    building: str = ""


class CampusKind(StrEnum):
    ROOM = "room"
    TEACHER = "teacher"


class CampusSearchCallback(CallbackData, prefix="campus_search"):
    kind: CampusKind


class CampusResultCallback(CallbackData, prefix="campus"):
    """Index into the FSM-stored search matches; weekday=0 opens today's (or the next workday's) view."""

    kind: CampusKind
    index: int
    weekday: int = 0
