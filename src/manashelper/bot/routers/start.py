from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _

router = Router(name="start")


def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("🍉 Food")), KeyboardButton(text=_("📅 Schedule"))],
            [KeyboardButton(text=_("📋 Attendance")), KeyboardButton(text=_("💯 Grades"))],
            [KeyboardButton(text=_("🛒 Marketplace"))],
            [KeyboardButton(text=_("⚙️ Settings"))],
        ],
        resize_keyboard=True,
    )


async def send_welcome(message: Message) -> None:
    reply_markup = build_main_keyboard() if message.chat.type == ChatType.PRIVATE else ReplyKeyboardRemove()
    await message.answer(_("Welcome to Manashelper!"), reply_markup=reply_markup)


@router.message(Command("hide_keyboard"))
async def hide_keyboard(message: Message) -> None:
    await message.reply(text=_("Keyboard is hidden"), reply_markup=ReplyKeyboardRemove())


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await send_welcome(message)
