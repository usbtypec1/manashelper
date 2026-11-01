from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from manashelper.modules.schedule.presentation.keyboards.timetable import build_timetable_menu_keyboard


async def show_timetable_menu(message: Message) -> None:
    await message.answer(_("menu.schedule"), reply_markup=build_timetable_menu_keyboard())
