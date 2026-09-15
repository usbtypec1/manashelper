from datetime import datetime

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import (
    CourseCallback,
    DepartmentCallback,
    FacultyCallback,
    ScheduleDayCallback,
    TimetableMenuAction,
    TimetableMenuCallback,
)
from manashelper.bot.filters.translated_text import TranslatedText
from manashelper.bot.keyboards.timetable import (
    build_course_keyboard,
    build_department_keyboard,
    build_no_tracked_courses_keyboard,
    build_schedule_days_keyboard,
    build_timetable_menu_keyboard,
)
from manashelper.services.course import CourseNotFoundError, CourseService, UserNotFoundError
from manashelper.services.daily_menu import BISHKEK_TZ
from manashelper.services.department import DepartmentService
from manashelper.services.schedule import NoTrackedCoursesError, ScheduleService
from manashelper.services.timetable_formatter import format_day_schedule

router = Router(name="timetable")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


_WORKDAYS = (1, 2, 3, 4, 5)


def _current_weekday(now: datetime) -> int:
    weekday = now.isoweekday()
    return weekday if weekday in _WORKDAYS else _WORKDAYS[0]


@router.message(TranslatedText("📅 Schedule"))
async def on_timetable_menu_button(message: Message) -> None:
    await message.answer(_("📅 Schedule"), reply_markup=build_timetable_menu_keyboard())


@router.callback_query(TimetableMenuCallback.filter(F.action == TimetableMenuAction.OPEN_MY_SCHEDULE))
async def on_my_schedule_selected(
    callback_query: CallbackQuery,
    schedule_service: FromDishka[ScheduleService],
) -> None:
    try:
        lessons = await schedule_service.get_user_schedule(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return
    except NoTrackedCoursesError:
        if isinstance(callback_query.message, Message):
            await callback_query.message.edit_text(
                _("You have no tracked courses yet. Pick your courses with the button below to see your schedule."),
                reply_markup=build_no_tracked_courses_keyboard(),
            )
        await callback_query.answer()
        return

    if not lessons:
        await callback_query.answer(
            _(
                "The schedule for your courses hasn't been loaded yet. It updates once an hour "
                "— please check back a bit later."
            ),
            show_alert=True,
        )
        return

    weekday = _current_weekday(datetime.now(BISHKEK_TZ))
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            format_day_schedule(weekday, lessons, datetime.now(BISHKEK_TZ)),
            reply_markup=build_schedule_days_keyboard(weekday),
        )
    await callback_query.answer()


@router.callback_query(ScheduleDayCallback.filter())
async def on_schedule_day_selected(
    callback_query: CallbackQuery,
    callback_data: ScheduleDayCallback,
    schedule_service: FromDishka[ScheduleService],
) -> None:
    try:
        lessons = await schedule_service.get_user_schedule(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return
    except NoTrackedCoursesError:
        await callback_query.answer(_("You no longer have any tracked courses"), show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            format_day_schedule(callback_data.weekday, lessons, datetime.now(BISHKEK_TZ)),
            reply_markup=build_schedule_days_keyboard(callback_data.weekday),
        )
    await callback_query.answer()


@router.callback_query(FacultyCallback.filter())
async def list_departments(
    callback_query: CallbackQuery,
    callback_data: FacultyCallback,
    department_service: FromDishka[DepartmentService],
) -> None:
    departments = await department_service.get_departments_by_faculty(callback_data.id)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("List of departments"), reply_markup=build_department_keyboard(departments)
        )
    await callback_query.answer()


@router.callback_query(DepartmentCallback.filter())
async def list_courses(
    callback_query: CallbackQuery,
    callback_data: DepartmentCallback,
    course_service: FromDishka[CourseService],
) -> None:
    courses = await course_service.get_courses_by_department(callback_data.id, callback_query.from_user.id)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("List of courses"), reply_markup=build_course_keyboard(courses))
    await callback_query.answer()


@router.callback_query(CourseCallback.filter())
async def toggle_course_tracking(
    callback_query: CallbackQuery,
    callback_data: CourseCallback,
    course_service: FromDishka[CourseService],
) -> None:
    try:
        courses = await course_service.toggle_tracked_course(callback_data.id, callback_query.from_user.id)
    except CourseNotFoundError:
        await callback_query.answer(_("Course not found"), show_alert=True)
        return
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("List of courses"), reply_markup=build_course_keyboard(courses))
    await callback_query.answer()
