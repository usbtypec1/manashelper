from aiogram.enums import ChatType
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _


def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("menu.food")), KeyboardButton(text=_("menu.schedule"))],
            [KeyboardButton(text=_("menu.attendance")), KeyboardButton(text=_("menu.grades"))],
            [KeyboardButton(text=_("menu.marketplace"))],
            [KeyboardButton(text=_("menu.settings"))],
        ],
        resize_keyboard=True,
    )


async def send_welcome(message: Message) -> None:
    reply_markup = build_main_keyboard() if message.chat.type == ChatType.PRIVATE else ReplyKeyboardRemove()
    await message.answer(_("common.welcome"), reply_markup=reply_markup)
