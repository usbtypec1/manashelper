from contextlib import suppress

from aiogram import F, Router, flags
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import ObisAction, ObisCallback
from manashelper.bot.filters.translated_text import TranslatedText
from manashelper.bot.keyboards.obis import (
    build_cancel_keyboard,
    build_confirm_clear_credentials_keyboard,
    build_no_credentials_keyboard,
    build_obis_settings_keyboard,
    build_terms_keyboard,
)
from manashelper.scraping.obis_client import ObisLoginError
from manashelper.scraping.obis_parser import ObisParseError
from manashelper.services.obis import ObisService, UserHasNoCredentialsError, UserNotFoundError
from manashelper.services.obis_formatter import format_attendance, format_exam_grades

router = Router(name="obis")


class ObisCredentialsForm(StatesGroup):
    student_number = State()
    password = State()


@router.message(TranslatedText("📋 Attendance"))
@flags.private_chat_only
async def on_attendance_button(message: Message, obis_service: FromDishka[ObisService]) -> None:
    if message.from_user is None:
        return

    try:
        attendance = await obis_service.get_attendance(message.from_user.id)
    except UserNotFoundError:
        await message.answer(_("Please start with the /start command"))
        return
    except UserHasNoCredentialsError:
        await message.answer(
            _("You haven't saved your OBIS credentials. Enter them using the button below."),
            reply_markup=build_no_credentials_keyboard(),
        )
        return
    except ObisLoginError:
        await message.answer(
            _("Your OBIS credentials are invalid. Enter them again using the button below."),
            reply_markup=build_no_credentials_keyboard(),
        )
        return
    except ObisParseError:
        await message.answer(_("Couldn't fetch data from OBIS. Please try again later."))
        return

    await message.answer(format_attendance(attendance))


@router.message(TranslatedText("💯 Grades"))
@flags.private_chat_only
async def on_exams_button(message: Message, obis_service: FromDishka[ObisService]) -> None:
    if message.from_user is None:
        return

    try:
        lesson_exams = await obis_service.get_exam_grades(message.from_user.id)
    except UserNotFoundError:
        await message.answer(_("Please start with the /start command"))
        return
    except UserHasNoCredentialsError:
        await message.answer(
            _("You haven't saved your OBIS credentials. Enter them using the button below."),
            reply_markup=build_no_credentials_keyboard(),
        )
        return
    except ObisLoginError:
        await message.answer(
            _("Your OBIS credentials are invalid. Enter them again using the button below."),
            reply_markup=build_no_credentials_keyboard(),
        )
        return
    except ObisParseError:
        await message.answer(_("Couldn't fetch data from OBIS. Please try again later."))
        return

    await message.answer(format_exam_grades(lesson_exams))


@router.callback_query(ObisCallback.filter(F.action == ObisAction.START_CREDENTIALS))
@flags.private_chat_only
async def on_start_credentials(callback_query: CallbackQuery) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.answer(
            _("Please accept the bot's terms of use to continue."), reply_markup=build_terms_keyboard()
        )
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.ACCEPT_TERMS))
@flags.private_chat_only
async def on_accept_terms(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ObisCredentialsForm.student_number)
    if isinstance(callback_query.message, Message):
        await callback_query.message.answer(_("Enter your student number:"), reply_markup=build_cancel_keyboard())
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.CANCEL_CREDENTIALS))
@flags.private_chat_only
async def on_cancel_credentials(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback_query.message, Message):
        await callback_query.message.answer(_("Cancelled"))
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.CLEAR_CREDENTIALS))
@flags.private_chat_only
async def on_clear_credentials_requested(callback_query: CallbackQuery) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("Are you sure you want to clear your saved OBIS credentials?"),
            reply_markup=build_confirm_clear_credentials_keyboard(),
        )
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.CONFIRM_CLEAR_CREDENTIALS))
@flags.private_chat_only
async def on_confirm_clear_credentials(
    callback_query: CallbackQuery,
    obis_service: FromDishka[ObisService],
) -> None:
    try:
        await obis_service.clear_credentials(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("OBIS credentials removed ✅"), reply_markup=build_obis_settings_keyboard(has_credentials=False)
        )
    await callback_query.answer()


@router.message(StateFilter(ObisCredentialsForm.student_number))
@flags.private_chat_only
async def on_student_number_entered(message: Message, state: FSMContext) -> None:
    student_number = message.text.strip() if message.text else ""
    if not student_number:
        await message.answer(
            _("The student number can't be empty. Please try again:"), reply_markup=build_cancel_keyboard()
        )
        return

    await state.update_data(student_number=student_number)
    await state.set_state(ObisCredentialsForm.password)
    await message.answer(_("Enter your OBIS password:"), reply_markup=build_cancel_keyboard())


@router.message(StateFilter(ObisCredentialsForm.password))
@flags.private_chat_only
async def on_password_entered(
    message: Message,
    state: FSMContext,
    obis_service: FromDishka[ObisService],
) -> None:
    password = message.text.strip() if message.text else ""
    data = await state.get_data()
    student_number = data.get("student_number")

    with suppress(TelegramBadRequest):
        await message.delete()

    if not password or not student_number or message.from_user is None:
        await state.clear()
        await message.answer(_("Something went wrong. Please try again."))
        return

    try:
        await obis_service.save_credentials(message.from_user.id, student_number, password)
    except ObisLoginError:
        await state.set_state(ObisCredentialsForm.student_number)
        await message.answer(
            _("Invalid OBIS credentials. Enter your student number again:"), reply_markup=build_cancel_keyboard()
        )
        return
    except UserNotFoundError:
        await state.clear()
        await message.answer(_("Please start with the /start command"))
        return

    await state.clear()
    await message.answer(
        _("Credentials saved successfully ✅"), reply_markup=build_obis_settings_keyboard(has_credentials=True)
    )
