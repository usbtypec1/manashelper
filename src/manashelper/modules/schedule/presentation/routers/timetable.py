from datetime import datetime

from aiogram import F, Router, flags
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.schedule.application.course import CourseNotFoundError, CourseQuery, UserNotFoundError
from manashelper.modules.schedule.application.department import DepartmentQuery
from manashelper.modules.schedule.application.faculty import FacultyQuery
from manashelper.modules.schedule.application.schedule import NoTrackedCoursesError, ScheduleQuery
from manashelper.modules.schedule.application.use_cases.toggle_tracked_course import ToggleTrackedCourseUseCase
from manashelper.modules.schedule.presentation.callbacks import (
    CourseCallback,
    DepartmentCallback,
    FacultyCallback,
    ScheduleDayCallback,
    TimetableMenuAction,
    TimetableMenuCallback,
)
from manashelper.modules.schedule.presentation.editing import edit_view
from manashelper.modules.schedule.presentation.entries_formatter import format_now_next
from manashelper.modules.schedule.presentation.keyboards.campus import build_now_keyboard
from manashelper.modules.schedule.presentation.keyboards.timetable import (
    build_course_keyboard,
    build_department_keyboard,
    build_faculty_keyboard,
    build_no_tracked_courses_keyboard,
    build_schedule_days_keyboard,
)
from manashelper.modules.schedule.presentation.timetable_formatter import format_day_schedule
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback
from manashelper.platform.telegram.filters.translated_text import TranslatedText

router = Router(name="timetable")


_WORKDAYS = (1, 2, 3, 4, 5)


def _current_weekday(now: datetime) -> int:
    weekday = now.isoweekday()
    return weekday if weekday in _WORKDAYS else _WORKDAYS[0]


@router.message(TranslatedText("menu.schedule"))
@flags.private_chat_only
async def on_timetable_menu_button(
    message: Message, state: FSMContext, schedule_query: FromDishka[ScheduleQuery]
) -> None:
    await state.clear()
    if message.from_user is None:
        return
    try:
        text, keyboard = await _schedule_view(schedule_query, message.from_user.id)
    except UserNotFoundError:
        await message.answer(_("common.start_required"))
        return
    await message.answer(text, reply_markup=keyboard)


async def _schedule_view(schedule_query: ScheduleQuery, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    try:
        lessons = await schedule_query.get_user_schedule(user_id)
    except NoTrackedCoursesError:
        return _("schedule.no_tracked_courses"), build_no_tracked_courses_keyboard()
    if not lessons:
        return _("schedule.not_loaded"), build_no_tracked_courses_keyboard()
    now = datetime.now(BISHKEK_TZ)
    weekday = _current_weekday(now)
    return format_day_schedule(weekday, lessons, now), build_schedule_days_keyboard(weekday)


async def _now_view(schedule_query: ScheduleQuery, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    now = datetime.now(BISHKEK_TZ)
    try:
        now_next = await schedule_query.get_now_next(user_id, now)
    except NoTrackedCoursesError:
        return _("schedule.no_tracked_courses"), build_no_tracked_courses_keyboard()
    return format_now_next(now_next, now), build_now_keyboard()


@router.message(Command("now"))
@flags.private_chat_only
async def on_now_command(message: Message, state: FSMContext, schedule_query: FromDishka[ScheduleQuery]) -> None:
    await state.clear()
    if message.from_user is None:
        return
    try:
        text, keyboard = await _now_view(schedule_query, message.from_user.id)
    except UserNotFoundError:
        await message.answer(_("common.start_required"))
        return
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(TimetableMenuCallback.filter(F.action == TimetableMenuAction.OPEN_NOW))
@flags.private_chat_only
async def on_now_selected(callback_query: CallbackQuery, schedule_query: FromDishka[ScheduleQuery]) -> None:
    try:
        text, keyboard = await _now_view(schedule_query, callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return
    await edit_view(callback_query, text, keyboard)
    await callback_query.answer()


@router.callback_query(
    TimetableMenuCallback.filter(F.action.in_({TimetableMenuAction.MENU, TimetableMenuAction.OPEN_MY_SCHEDULE}))
)
@flags.private_chat_only
async def on_my_schedule_selected(
    callback_query: CallbackQuery,
    schedule_query: FromDishka[ScheduleQuery],
    state: FSMContext,
) -> None:
    await state.clear()
    try:
        text, keyboard = await _schedule_view(schedule_query, callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_COURSE_TRACKING))
@flags.private_chat_only
async def on_open_course_tracking(callback_query: CallbackQuery, faculty_query: FromDishka[FacultyQuery]) -> None:
    faculties = await faculty_query.get_all_faculties()
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("schedule.faculties"), reply_markup=build_faculty_keyboard(faculties))
    await callback_query.answer()


@router.callback_query(ScheduleDayCallback.filter())
@flags.private_chat_only
async def on_schedule_day_selected(
    callback_query: CallbackQuery,
    callback_data: ScheduleDayCallback,
    schedule_query: FromDishka[ScheduleQuery],
) -> None:
    try:
        lessons = await schedule_query.get_user_schedule(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return
    except NoTrackedCoursesError:
        if isinstance(callback_query.message, Message):
            await callback_query.message.edit_text(
                _("schedule.no_tracked_courses"), reply_markup=build_no_tracked_courses_keyboard()
            )
        await callback_query.answer()
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            format_day_schedule(callback_data.weekday, lessons, datetime.now(BISHKEK_TZ)),
            reply_markup=build_schedule_days_keyboard(callback_data.weekday),
        )
    await callback_query.answer()


@router.callback_query(FacultyCallback.filter())
@flags.private_chat_only
async def list_departments(
    callback_query: CallbackQuery,
    callback_data: FacultyCallback,
    department_query: FromDishka[DepartmentQuery],
) -> None:
    departments = await department_query.get_departments_by_faculty(callback_data.id)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("schedule.departments"), reply_markup=build_department_keyboard(departments)
        )
    await callback_query.answer()


@router.callback_query(DepartmentCallback.filter())
@flags.private_chat_only
async def list_courses(
    callback_query: CallbackQuery,
    callback_data: DepartmentCallback,
    course_query: FromDishka[CourseQuery],
) -> None:
    courses = await course_query.get_courses_by_department(callback_data.id, callback_query.from_user.id)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("schedule.courses"), reply_markup=build_course_keyboard(courses))
    await callback_query.answer()


@router.callback_query(CourseCallback.filter())
@flags.private_chat_only
async def toggle_course_tracking(
    callback_query: CallbackQuery,
    callback_data: CourseCallback,
    toggle_tracked_course: FromDishka[ToggleTrackedCourseUseCase],
) -> None:
    try:
        courses = await toggle_tracked_course.execute(callback_data.id, callback_query.from_user.id)
    except CourseNotFoundError:
        await callback_query.answer(_("schedule.course_not_found"), show_alert=True)
        return
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("schedule.courses"), reply_markup=build_course_keyboard(courses))
    await callback_query.answer()
