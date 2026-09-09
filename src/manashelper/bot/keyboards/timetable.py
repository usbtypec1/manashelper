from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import CourseCallback, DepartmentCallback, FacultyCallback
from manashelper.services.course_service import CourseSummary
from manashelper.services.department_service import DepartmentSummary
from manashelper.services.faculty_service import FacultyModel


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


def build_course_keyboard(courses: list[CourseSummary]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for course in courses:
        check_mark = "✅ " if course.is_tracked else ""
        builder.button(text=f"{check_mark}{course.number} курс", callback_data=CourseCallback(id=course.id))
    builder.adjust(1)
    return builder.as_markup()
