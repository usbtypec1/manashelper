from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.localization.weekdays import weekday_abbr
from manashelper.modules.schedule.application.course import CourseSummary
from manashelper.modules.schedule.application.department import DepartmentSummary
from manashelper.modules.schedule.application.faculty import FacultyModel
from manashelper.modules.schedule.presentation.callbacks import (
    CourseCallback,
    DepartmentCallback,
    FacultyCallback,
    ScheduleDayCallback,
    TimetableMenuAction,
    TimetableMenuCallback,
)
from manashelper.platform.telegram.callbacks import (
    NavigationAction,
    NavigationCallback,
    SettingsAction,
    SettingsCallback,
)
from manashelper.platform.telegram.navigation import build_mini_app_button, build_navigation_keyboard


def build_timetable_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("schedule.my_schedule"), callback_data=TimetableMenuCallback(action=TimetableMenuAction.OPEN_MY_SCHEDULE)
    )
    builder.button(
        text=_("schedule.search_subject"),
        callback_data=TimetableMenuCallback(action=TimetableMenuAction.OPEN_LESSON_SEARCH),
    )
    builder.adjust(1)
    builder.attach(build_navigation_keyboard(NavigationCallback(action=NavigationAction.STUDY)))
    return builder.as_markup()


def build_faculty_keyboard(faculties: list[FacultyModel]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    mini_app = build_mini_app_button(courses=True)
    if mini_app is not None:
        builder.row(mini_app)
    for faculty in faculties:
        builder.button(text=faculty.name, callback_data=FacultyCallback(id=faculty.id))
    builder.adjust(1)
    builder.attach(build_navigation_keyboard(TimetableMenuCallback(action=TimetableMenuAction.MENU)))
    return builder.as_markup()


def build_department_keyboard(departments: list[DepartmentSummary]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for department in departments:
        builder.button(text=department.name, callback_data=DepartmentCallback(id=department.id))
    builder.adjust(1)
    builder.attach(build_navigation_keyboard(SettingsCallback(action=SettingsAction.OPEN_COURSE_TRACKING)))
    return builder.as_markup()


def build_no_tracked_courses_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("schedule.choose_courses"), callback_data=SettingsCallback(action=SettingsAction.OPEN_COURSE_TRACKING)
    )
    builder.attach(build_navigation_keyboard(NavigationCallback(action=NavigationAction.STUDY)))
    return builder.as_markup()


def build_schedule_days_keyboard(current_weekday: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("schedule.change_courses"), callback_data=SettingsCallback(action=SettingsAction.OPEN_COURSE_TRACKING)
    )
    builder.adjust(1)
    days = InlineKeyboardBuilder()
    for weekday in range(1, 6):
        if weekday == current_weekday:
            continue
        emoji = "⬅️" if weekday < current_weekday else "➡️️"
        text = f"{emoji} {weekday_abbr(weekday)}"
        days.button(text=text, callback_data=ScheduleDayCallback(weekday=weekday))
    days.adjust(4)
    builder.attach(days)
    builder.attach(build_navigation_keyboard(NavigationCallback(action=NavigationAction.STUDY)))
    return builder.as_markup()


def build_course_keyboard(courses: list[CourseSummary]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for course in courses:
        check_mark = "✅ " if course.is_tracked else ""
        course_year = _("schedule.course_year").format(number=course.number)
        builder.button(text=f"{check_mark}{course_year}", callback_data=CourseCallback(id=course.id))
    builder.adjust(1)
    builder.button(
        text=_("schedule.faculties"), callback_data=SettingsCallback(action=SettingsAction.OPEN_COURSE_TRACKING)
    )
    builder.adjust(1)
    builder.attach(build_navigation_keyboard(TimetableMenuCallback(action=TimetableMenuAction.MENU)))
    return builder.as_markup()
