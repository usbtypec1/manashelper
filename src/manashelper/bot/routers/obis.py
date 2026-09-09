from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from manashelper.bot.callback_data import ObisAction, ObisCallback
from manashelper.bot.keyboards.obis import build_cancel_keyboard, build_obis_menu_keyboard, build_terms_keyboard
from manashelper.scraping.obis_client import ObisLoginError
from manashelper.scraping.obis_parser import ObisParseError
from manashelper.services.obis_formatter import format_attendance, format_exam_grades
from manashelper.services.obis_service import ObisService, UserHasNoCredentialsError, UserNotFoundError

router = Router(name="obis")

TERMS_TEXT = "Пожалуйста, примите условия использования бота, чтобы продолжить."
NO_CREDENTIALS_TEXT = "Введите ваши данные от OBIS"
INVALID_CREDENTIALS_TEXT = "Неверные данные от OBIS. Пожалуйста, введите их заново."
FETCH_FAILED_TEXT = "Не удалось получить данные с OBIS. Попробуйте позже."


class ObisCredentialsForm(StatesGroup):
    student_number = State()
    password = State()


@router.message(F.text == "🔐 OBIS")
async def on_obis_button(message: Message) -> None:
    await message.answer("Меню OBIS", reply_markup=build_obis_menu_keyboard())


@router.callback_query(ObisCallback.filter(F.action == ObisAction.ATTENDANCE))
async def on_attendance(callback_query: CallbackQuery, obis_service: FromDishka[ObisService]) -> None:
    await callback_query.answer()
    if not isinstance(callback_query.message, Message):
        return

    try:
        attendance = await obis_service.get_attendance(callback_query.from_user.id)
    except (UserNotFoundError, UserHasNoCredentialsError):
        await callback_query.message.answer(NO_CREDENTIALS_TEXT, reply_markup=build_obis_menu_keyboard())
        return
    except ObisLoginError:
        await callback_query.message.answer(INVALID_CREDENTIALS_TEXT, reply_markup=build_obis_menu_keyboard())
        return
    except ObisParseError:
        await callback_query.message.answer(FETCH_FAILED_TEXT)
        return

    await callback_query.message.answer(format_attendance(attendance))


@router.callback_query(ObisCallback.filter(F.action == ObisAction.EXAMS))
async def on_exams(callback_query: CallbackQuery, obis_service: FromDishka[ObisService]) -> None:
    await callback_query.answer()
    if not isinstance(callback_query.message, Message):
        return

    try:
        lesson_exams = await obis_service.get_exam_grades(callback_query.from_user.id)
    except (UserNotFoundError, UserHasNoCredentialsError):
        await callback_query.message.answer(NO_CREDENTIALS_TEXT, reply_markup=build_obis_menu_keyboard())
        return
    except ObisLoginError:
        await callback_query.message.answer(INVALID_CREDENTIALS_TEXT, reply_markup=build_obis_menu_keyboard())
        return
    except ObisParseError:
        await callback_query.message.answer(FETCH_FAILED_TEXT)
        return

    await callback_query.message.answer(format_exam_grades(lesson_exams))


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
    await message.answer("Данные успешно сохранены ✅", reply_markup=build_obis_menu_keyboard())
