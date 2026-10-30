from aiogram import Router, flags
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from manashelper.platform.telegram.filters.translated_text import TranslatedText
from manashelper.platform.telegram.navigation import build_main_keyboard, build_study_keyboard

router = Router(name="navigation")


@router.message(TranslatedText("menu.study"))
@flags.private_chat_only
async def on_study_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_("menu.study"), reply_markup=build_study_keyboard())


@router.message(TranslatedText("common.back_to_menu"))
@flags.private_chat_only
async def on_back_to_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_("menu.main"), reply_markup=build_main_keyboard())
