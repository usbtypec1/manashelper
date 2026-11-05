from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.platform.telegram.navigation import send_welcome

router = Router(name="start")


@router.message(Command("hide_keyboard"))
async def hide_keyboard(message: Message) -> None:
    await message.reply(text=_("menu.keyboard_hidden"), reply_markup=ReplyKeyboardRemove())


@router.message(CommandStart())
async def on_start(message: Message, gamification: FromDishka[GamificationQuery]) -> None:
    await send_welcome(
        message,
        achievements_enabled=await gamification.is_enabled(
            message.from_user.id if message.from_user else message.chat.id
        ),
    )
