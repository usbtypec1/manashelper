from aiogram import F, Router, flags
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.platform.telegram.callbacks import NavigationAction, NavigationCallback
from manashelper.platform.telegram.filters.translated_text import TranslatedText
from manashelper.platform.telegram.navigation import build_main_keyboard, build_study_keyboard

router = Router(name="navigation")


@router.callback_query(NavigationCallback.filter(F.action == NavigationAction.STUDY))
@flags.private_chat_only
async def on_back_to_study(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.answer(_("menu.study"), reply_markup=build_study_keyboard())
    await callback.answer()


@router.callback_query(NavigationCallback.filter(F.action == NavigationAction.MAIN))
@flags.private_chat_only
async def on_main_menu_callback(
    callback: CallbackQuery, state: FSMContext, gamification: FromDishka[GamificationQuery]
) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            _("menu.main"),
            reply_markup=build_main_keyboard(achievements_enabled=await gamification.is_enabled(callback.from_user.id)),
        )
    await callback.answer()


@router.message(TranslatedText("menu.study"))
@flags.private_chat_only
async def on_study_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_("menu.study"), reply_markup=build_study_keyboard())


@router.message(TranslatedText("common.back_to_menu"))
@flags.private_chat_only
async def on_back_to_main_menu(
    message: Message, state: FSMContext, gamification: FromDishka[GamificationQuery]
) -> None:
    await state.clear()
    await message.answer(
        _("menu.main"),
        reply_markup=build_main_keyboard(achievements_enabled=await gamification.is_enabled(message.chat.id)),
    )
