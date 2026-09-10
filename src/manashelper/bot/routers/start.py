from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from dishka import FromDishka

from manashelper.repositories.user_repository import UserRepository

router = Router(name="start")


def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍉 Йемек"), KeyboardButton(text="📅 Расписание")],
            [KeyboardButton(text="📋 Йоклама"), KeyboardButton(text="💯 Оценки")],
            [KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
    )


@router.message(CommandStart())
async def on_start(message: Message, user_repository: FromDishka[UserRepository]) -> None:
    if message.from_user is None:
        return

    await user_repository.upsert(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
    )
    await message.answer("Добро пожаловать в Manashelper!", reply_markup=build_main_keyboard())
