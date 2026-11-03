from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from manashelper.modules.schedule.application.faculty import FacultyService
from manashelper.modules.schedule.presentation.keyboards.timetable import (
    build_faculty_keyboard,
    build_timetable_menu_keyboard,
)


async def show_timetable_menu(message: Message) -> None:
    await message.answer(_("menu.schedule"), reply_markup=build_timetable_menu_keyboard())


async def show_course_tracking(message: Message, faculties: FacultyService) -> None:
    await message.answer(
        _("schedule.faculties"), reply_markup=build_faculty_keyboard(await faculties.get_all_faculties())
    )
