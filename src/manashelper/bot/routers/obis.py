import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress

import httpx
from aiogram import F, Router, flags
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import ObisAction, ObisCallback, ObisResultsPageCallback
from manashelper.bot.filters.translated_text import TranslatedText
from manashelper.bot.keyboards.obis import (
    build_cancel_keyboard,
    build_confirm_clear_credentials_keyboard,
    build_no_credentials_keyboard,
    build_obis_results_keyboard,
    build_obis_settings_keyboard,
    build_terms_keyboard,
)
from manashelper.scraping.obis_client import ObisLoginError
from manashelper.scraping.obis_parser import ObisParseError
from manashelper.services.obis import ObisService, UserHasNoCredentialsError, UserNotFoundError
from manashelper.services.obis_formatter import format_attendance_pages, format_exam_grades_pages

router = Router(name="obis")
logger = logging.getLogger(__name__)
RESULTS_KEY = "obis_result_pages"
MAX_SAVED_RESULTS = 5


class ObisCredentialsForm(StatesGroup):
    student_number = State()
    password = State()


async def _show_obis_results[T](
    message: Message,
    state: FSMContext,
    fetch: Callable[[int], Awaitable[list[T]]],
    format_results: Callable[[list[T]], list[str]],
    loading_text: str,
) -> None:
    if message.from_user is None:
        return
    sent = await message.answer(loading_text, parse_mode=None)
    try:
        lessons = await fetch(message.from_user.id)
    except UserNotFoundError:
        await sent.edit_text(_("common.start_required"))
        return
    except UserHasNoCredentialsError:
        await sent.edit_text(
            _("obis.credentials_missing"),
            reply_markup=build_no_credentials_keyboard(),
        )
        return
    except ObisLoginError:
        await sent.edit_text(
            _("obis.credentials_invalid"),
            reply_markup=build_no_credentials_keyboard(),
        )
        return
    except (ObisParseError, httpx.HTTPError):
        logger.warning("Failed to load requested OBIS data", exc_info=True)
        await sent.edit_text(_("obis.fetch_failed"))
        return
    except Exception:
        await sent.edit_text(_("obis.fetch_failed"))
        raise
    pages = format_results(lessons)
    if len(pages) > 1:
        data = await state.get_data()
        snapshots: dict[str, list[str]] = dict(data.get(RESULTS_KEY, {}))
        snapshots[str(sent.message_id)] = pages
        while len(snapshots) > MAX_SAVED_RESULTS:
            snapshots.pop(next(iter(snapshots)))
        await state.update_data({RESULTS_KEY: snapshots})
    await sent.edit_text(pages[0], parse_mode=None, reply_markup=build_obis_results_keyboard(0, len(pages)))


@router.message(TranslatedText("menu.attendance"))
@flags.private_chat_only
async def on_attendance_button(message: Message, state: FSMContext, obis_service: FromDishka[ObisService]) -> None:
    await _show_obis_results(
        message, state, obis_service.get_attendance, format_attendance_pages, _("obis.loading_attendance")
    )


@router.message(TranslatedText("menu.grades"))
@flags.private_chat_only
async def on_exams_button(message: Message, state: FSMContext, obis_service: FromDishka[ObisService]) -> None:
    await _show_obis_results(
        message, state, obis_service.get_exam_grades, format_exam_grades_pages, _("obis.loading_grades")
    )


@router.callback_query(ObisResultsPageCallback.filter())
@flags.private_chat_only
async def on_obis_results_page(
    callback_query: CallbackQuery, callback_data: ObisResultsPageCallback, state: FSMContext
) -> None:
    message = callback_query.message
    if not isinstance(message, Message):
        await callback_query.answer()
        return
    data = await state.get_data()
    snapshots: dict[str, list[str]] = data.get(RESULTS_KEY, {})
    pages = snapshots.get(str(message.message_id))
    if not pages or not 0 <= callback_data.page < len(pages):
        await callback_query.answer(_("obis.result_expired"), show_alert=True)
        return
    try:
        await message.edit_text(
            pages[callback_data.page],
            parse_mode=None,
            reply_markup=build_obis_results_keyboard(callback_data.page, len(pages)),
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in error.message:
            logger.warning("Failed to change requested OBIS page", exc_info=True)
            await callback_query.answer(_("common.error_retry"), show_alert=True)
            return
    except TelegramAPIError:
        logger.warning("Failed to change requested OBIS page", exc_info=True)
        await callback_query.answer(_("common.error_retry"), show_alert=True)
        return
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.START_CREDENTIALS))
@flags.private_chat_only
async def on_start_credentials(callback_query: CallbackQuery) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.answer(_("obis.accept_terms_prompt"), reply_markup=build_terms_keyboard())
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.ACCEPT_TERMS))
@flags.private_chat_only
async def on_accept_terms(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ObisCredentialsForm.student_number)
    if isinstance(callback_query.message, Message):
        await callback_query.message.answer(_("obis.student_number_prompt"), reply_markup=build_cancel_keyboard())
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.CANCEL_CREDENTIALS))
@flags.private_chat_only
async def on_cancel_credentials(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback_query.message, Message):
        await callback_query.message.answer(_("obis.cancelled"))
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.CLEAR_CREDENTIALS))
@flags.private_chat_only
async def on_clear_credentials_requested(callback_query: CallbackQuery) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("obis.clear_confirmation"),
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
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("obis.credentials_removed"), reply_markup=build_obis_settings_keyboard(has_credentials=False)
        )
    await callback_query.answer()


@router.message(StateFilter(ObisCredentialsForm.student_number))
@flags.private_chat_only
async def on_student_number_entered(message: Message, state: FSMContext) -> None:
    student_number = message.text.strip() if message.text else ""
    if not student_number:
        await message.answer(_("obis.empty_student_number"), reply_markup=build_cancel_keyboard())
        return

    await state.update_data(student_number=student_number)
    await state.set_state(ObisCredentialsForm.password)
    await message.answer(_("obis.password_prompt"), reply_markup=build_cancel_keyboard())


@router.message(StateFilter(ObisCredentialsForm.password))
@flags.private_chat_only
@flags.mask_logged_message
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
        await message.answer(_("common.error_retry"))
        return

    try:
        await obis_service.save_credentials(message.from_user.id, student_number, password)
    except ObisLoginError:
        await state.set_state(ObisCredentialsForm.student_number)
        await message.answer(_("obis.login_failed"), reply_markup=build_cancel_keyboard())
        return
    except UserNotFoundError:
        await state.clear()
        await message.answer(_("common.start_required"))
        return

    await state.clear()
    await message.answer(_("obis.credentials_saved"), reply_markup=build_obis_settings_keyboard(has_credentials=True))
