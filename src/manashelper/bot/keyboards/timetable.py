from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import (
    CourseCallback,
    DepartmentCallback,
    FacultyCallback,
    ScheduleDayCallback,
    SettingsAction,
    SettingsCallback,
    TimetableMenuAction,
    TimetableMenuCallback,
)
from manashelper.services.course import CourseSummary
from manashelper.services.department import DepartmentSummary
from manashelper.services.faculty import FacultyModel
from manashelper.services.timetable_formatter import weekday_abbr


def build_timetable_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("📅 My schedule"), callback_data=TimetableMenuCallback(action=TimetableMenuAction.OPEN_MY_SCHEDULE)
    )
    builder.button(
        text=_("🔎 Search for a subject"),
        callback_data=TimetableMenuCallback(action=TimetableMenuAction.OPEN_LESSON_SEARCH),
    )
    builder.adjust(1)
    return builder.as_markup()


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
    builder.button(
        text=_("📚 Choose courses"), callback_data=SettingsCallback(action=SettingsAction.OPEN_COURSE_TRACKING)
    )
    return builder.as_markup()


def build_schedule_days_keyboard(current_weekday: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for weekday in range(1, 6):
        if weekday == current_weekday:
            continue
        emoji = "⬅️" if weekday < current_weekday else "➡️️"
        text = f"{emoji} {weekday_abbr(weekday)}"
        builder.button(text=text, callback_data=ScheduleDayCallback(weekday=weekday))
    builder.adjust(4)
    return builder.as_markup()


def build_course_keyboard(courses: list[CourseSummary]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for course in courses:
        check_mark = "✅ " if course.is_tracked else ""
        course_year = _("Year {number}").format(number=course.number)
        builder.button(text=f"{check_mark}{course_year}", callback_data=CourseCallback(id=course.id))
    builder.adjust(1)
    return builder.as_markup()
