from aiogram import Bot, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.core.config import Settings
from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.platform.telegram.admin_menu import set_admin_menu_button
from manashelper.platform.telegram.navigation import send_welcome

router = Router(name="start")


@router.message(Command("hide_keyboard"))
async def hide_keyboard(message: Message) -> None:
    await message.reply(text=_("menu.keyboard_hidden"), reply_markup=ReplyKeyboardRemove())


@router.message(CommandStart())
async def on_start(
    message: Message, bot: Bot, gamification: FromDishka[GamificationQuery], settings: FromDishka[Settings]
) -> None:
    await send_welcome(
        message,
        achievements_enabled=await gamification.is_enabled(
            message.from_user.id if message.from_user else message.chat.id
        ),
    )
    if message.chat.type == ChatType.PRIVATE and settings.public_url:
        await set_admin_menu_button(bot, settings, message.chat.id)
