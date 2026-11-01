from aiogram import Router, flags
from aiogram.filters import Command
from aiogram.types import Message
from dishka import FromDishka

from manashelper.modules.study_week.application import GetStudyWeek
from manashelper.modules.study_week.entrypoints import show_study_week
from manashelper.platform.telegram.filters.translated_text import TranslatedText

router = Router(name="study_week")


@router.message(TranslatedText("menu.study_week"))
@router.message(Command("week"))
@flags.private_chat_only
async def on_week_command(message: Message, get_study_week: FromDishka[GetStudyWeek]) -> None:
    if message.from_user is not None:
        await show_study_week(message, message.from_user.id, get_study_week)
