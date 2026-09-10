from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import (
    CourseCallback,
    DepartmentCallback,
    FacultyCallback,
    ScheduleDayCallback,
    SettingsAction,
    SettingsCallback,
)
from manashelper.services.course_service import CourseSummary
from manashelper.services.department_service import DepartmentSummary
from manashelper.services.faculty_service import FacultyModel
from manashelper.services.timetable_formatter import WEEKDAY_LABELS


def build_faculty_keyboard(faculties: list[FacultyModel]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for faculty in faculties:
        builder.button(text=faculty.name, callback_data=FacultyCallback(id=faculty.id))
    builder.adjust(1)
    return builder.as_markup()


def build_department_keyboard(departments: list[DepartmentSummary]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for department in departments:
        builder.button(text=department.name, callback_data=DepartmentCallback(id=department.id))
    builder.adjust(1)
    return builder.as_markup()


def build_no_tracked_courses_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Выбрать курсы", callback_data=SettingsCallback(action=SettingsAction.OPEN_COURSE_TRACKING))
    return builder.as_markup()


def build_schedule_days_keyboard(current_weekday: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for weekday in sorted(WEEKDAY_LABELS):
        if weekday == current_weekday:
            continue
        builder.button(text=WEEKDAY_LABELS[weekday], callback_data=ScheduleDayCallback(weekday=weekday))
    builder.adjust(4)
    return builder.as_markup()


def build_course_keyboard(courses: list[CourseSummary]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for course in courses:
        check_mark = "✅ " if course.is_tracked else ""
        builder.button(text=f"{check_mark}{course.number} курс", callback_data=CourseCallback(id=course.id))
    builder.adjust(1)
    return builder.as_markup()
