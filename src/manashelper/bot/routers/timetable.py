from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from manashelper.bot.callback_data import CourseCallback, DepartmentCallback, FacultyCallback, ScheduleDayCallback
from manashelper.bot.keyboards.timetable import (
    build_course_keyboard,
    build_department_keyboard,
    build_no_tracked_courses_keyboard,
    build_schedule_days_keyboard,
)
from manashelper.services.course import CourseNotFoundError, CourseService, UserNotFoundError
from manashelper.services.daily_menu import BISHKEK_TZ
from manashelper.services.department import DepartmentService
from manashelper.services.schedule import NoTrackedCoursesError, ScheduleLessonModel, ScheduleService
from manashelper.services.timetable_formatter import format_day_schedule

router = Router(name="timetable")

NO_TRACKED_COURSES_TEXT = "У вас нет отслеживаемых курсов. Выберите курсы кнопкой ниже, чтобы видеть расписание."
SCHEDULE_NOT_SYNCED_TEXT = (
    "Расписание для ваших курсов ещё не загружено. Оно обновляется раз в час — попробуйте зайти чуть позже."
)

_WORKDAYS = (1, 2, 3, 4, 5)


def _current_weekday(now: datetime) -> int:
    weekday = now.isoweekday()
    return weekday if weekday in _WORKDAYS else _WORKDAYS[0]


async def _show_day_schedule(message: Message, weekday: int, lessons: list[ScheduleLessonModel]) -> None:
    now = datetime.now(BISHKEK_TZ)
    await message.answer(
        format_day_schedule(weekday, lessons, now),
        reply_markup=build_schedule_days_keyboard(weekday),
    )


@router.message(F.text == "📅 Расписание")
async def show_schedule(message: Message, schedule_service: FromDishka[ScheduleService]) -> None:
    if message.from_user is None:
        return

    try:
        lessons = await schedule_service.get_user_schedule(message.from_user.id)
    except UserNotFoundError:
        await message.answer("Пожалуйста, начните с команды /start")
        return
    except NoTrackedCoursesError:
        await message.answer(NO_TRACKED_COURSES_TEXT, reply_markup=build_no_tracked_courses_keyboard())
        return

    if not lessons:
        await message.answer(SCHEDULE_NOT_SYNCED_TEXT)
        return

    await _show_day_schedule(message, _current_weekday(datetime.now(BISHKEK_TZ)), lessons)


@router.callback_query(ScheduleDayCallback.filter())
async def on_schedule_day_selected(
    callback_query: CallbackQuery,
    callback_data: ScheduleDayCallback,
    schedule_service: FromDishka[ScheduleService],
) -> None:
    try:
        lessons = await schedule_service.get_user_schedule(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer("Пожалуйста, начните с команды /start", show_alert=True)
        return
    except NoTrackedCoursesError:
        await callback_query.answer("У вас больше нет отслеживаемых курсов", show_alert=True)
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
            "Список направлений", reply_markup=build_department_keyboard(departments)
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
        await callback_query.message.edit_text("Список курсов", reply_markup=build_course_keyboard(courses))
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
        await callback_query.answer("Курс не найден", show_alert=True)
        return
    except UserNotFoundError:
        await callback_query.answer("Пожалуйста, начните с команды /start", show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text("Список курсов", reply_markup=build_course_keyboard(courses))
    await callback_query.answer()
