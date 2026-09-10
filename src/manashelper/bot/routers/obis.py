from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from manashelper.bot.callback_data import ObisAction, ObisCallback
from manashelper.bot.keyboards.obis import (
    build_cancel_keyboard,
    build_confirm_clear_credentials_keyboard,
    build_no_credentials_keyboard,
    build_obis_settings_keyboard,
    build_terms_keyboard,
)
from manashelper.scraping.obis_client import ObisLoginError
from manashelper.scraping.obis_parser import ObisParseError
from manashelper.services.obis_formatter import format_attendance, format_exam_grades
from manashelper.services.obis_service import ObisService, UserHasNoCredentialsError, UserNotFoundError

router = Router(name="obis")

TERMS_TEXT = "Пожалуйста, примите условия использования бота, чтобы продолжить."
NO_CREDENTIALS_TEXT = "У вас не сохранены данные от OBIS. Введите их кнопкой ниже."
INVALID_CREDENTIALS_TEXT = "Неверные данные от OBIS. Введите их заново кнопкой ниже."
FETCH_FAILED_TEXT = "Не удалось получить данные с OBIS. Попробуйте позже."
CONFIRM_CLEAR_CREDENTIALS_TEXT = "Вы уверены, что хотите очистить сохранённые данные от OBIS?"


class ObisCredentialsForm(StatesGroup):
    student_number = State()
    password = State()


@router.message(F.text == "📋 Йоклама")
async def on_attendance_button(message: Message, obis_service: FromDishka[ObisService]) -> None:
    if message.from_user is None:
        return

    try:
        attendance = await obis_service.get_attendance(message.from_user.id)
    except UserNotFoundError:
        await message.answer("Пожалуйста, начните с команды /start")
        return
    except UserHasNoCredentialsError:
        await message.answer(NO_CREDENTIALS_TEXT, reply_markup=build_no_credentials_keyboard())
        return
    except ObisLoginError:
        await message.answer(INVALID_CREDENTIALS_TEXT, reply_markup=build_no_credentials_keyboard())
        return
    except ObisParseError:
        await message.answer(FETCH_FAILED_TEXT)
        return

    await message.answer(format_attendance(attendance))


@router.message(F.text == "💯 Оценки")
async def on_exams_button(message: Message, obis_service: FromDishka[ObisService]) -> None:
    if message.from_user is None:
        return

    try:
        lesson_exams = await obis_service.get_exam_grades(message.from_user.id)
    except UserNotFoundError:
        await message.answer("Пожалуйста, начните с команды /start")
        return
    except UserHasNoCredentialsError:
        await message.answer(NO_CREDENTIALS_TEXT, reply_markup=build_no_credentials_keyboard())
        return
    except ObisLoginError:
        await message.answer(INVALID_CREDENTIALS_TEXT, reply_markup=build_no_credentials_keyboard())
        return
    except ObisParseError:
        await message.answer(FETCH_FAILED_TEXT)
        return

    await message.answer(format_exam_grades(lesson_exams))


@router.callback_query(ObisCallback.filter(F.action == ObisAction.START_CREDENTIALS))
async def on_start_credentials(callback_query: CallbackQuery) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.answer(TERMS_TEXT, reply_markup=build_terms_keyboard())
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.ACCEPT_TERMS))
async def on_accept_terms(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ObisCredentialsForm.student_number)
    if isinstance(callback_query.message, Message):
        await callback_query.message.answer("Введите ваш студенческий номер:", reply_markup=build_cancel_keyboard())
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.CANCEL_CREDENTIALS))
async def on_cancel_credentials(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback_query.message, Message):
        await callback_query.message.answer("Отменено")
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.CLEAR_CREDENTIALS))
async def on_clear_credentials_requested(callback_query: CallbackQuery) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            CONFIRM_CLEAR_CREDENTIALS_TEXT, reply_markup=build_confirm_clear_credentials_keyboard()
        )
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.CONFIRM_CLEAR_CREDENTIALS))
async def on_confirm_clear_credentials(
    callback_query: CallbackQuery,
    obis_service: FromDishka[ObisService],
) -> None:
    try:
        await obis_service.clear_credentials(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer("Пожалуйста, начните с команды /start", show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            "Данные от OBIS удалены ✅", reply_markup=build_obis_settings_keyboard(has_credentials=False)
        )
    await callback_query.answer()


@router.message(StateFilter(ObisCredentialsForm.student_number))
async def on_student_number_entered(message: Message, state: FSMContext) -> None:
    student_number = message.text.strip() if message.text else ""
    if not student_number:
        await message.answer(
            "Студенческий номер не может быть пустым. Попробуйте снова:", reply_markup=build_cancel_keyboard()
        )
        return

    await state.update_data(student_number=student_number)
    await state.set_state(ObisCredentialsForm.password)
    await message.answer("Введите ваш пароль от OBIS:", reply_markup=build_cancel_keyboard())


@router.message(StateFilter(ObisCredentialsForm.password))
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
        await message.answer("Что-то пошло не так. Попробуйте снова.")
        return

    try:
        await obis_service.save_credentials(message.from_user.id, student_number, password)
    except ObisLoginError:
        await state.set_state(ObisCredentialsForm.student_number)
        await message.answer(
            "Неверные данные от OBIS. Введите студенческий номер заново:", reply_markup=build_cancel_keyboard()
        )
        return
    except UserNotFoundError:
        await state.clear()
        await message.answer("Пожалуйста, начните с команды /start")
        return

    await state.clear()
    await message.answer("Данные успешно сохранены ✅", reply_markup=build_obis_settings_keyboard(has_credentials=True))
