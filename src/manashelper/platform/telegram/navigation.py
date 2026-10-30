from aiogram.enums import ChatType
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _

from manashelper.core.config import get_settings


def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("menu.food")), KeyboardButton(text=_("menu.study"))],
            [KeyboardButton(text=_("menu.marketplace"))],
            [KeyboardButton(text=_("menu.settings"))],
        ],
        resize_keyboard=True,
    )


def build_study_keyboard() -> ReplyKeyboardMarkup:
    schedule_row = [KeyboardButton(text=_("menu.schedule"))]
    eders_rows = []
    if get_settings().eders_enabled:
        schedule_row.append(KeyboardButton(text=_("menu.study_week")))
        eders_rows = [
            [KeyboardButton(text=_("menu.eders")), KeyboardButton(text=_("menu.eders_materials"))],
        ]
    return ReplyKeyboardMarkup(
        keyboard=[
            schedule_row,
            [KeyboardButton(text=_("menu.attendance")), KeyboardButton(text=_("menu.grades"))],
            *eders_rows,
            [KeyboardButton(text=_("common.back_to_menu"))],
        ],
        resize_keyboard=True,
    )


async def send_welcome(message: Message) -> None:
    reply_markup = build_main_keyboard() if message.chat.type == ChatType.PRIVATE else ReplyKeyboardRemove()
    await message.answer(_("common.welcome"), reply_markup=reply_markup)
