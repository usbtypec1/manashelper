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

from manashelper.modules.gamification.application.use_cases.record_activity import RecordActivityUseCase
from manashelper.modules.notifications.application.use_cases.get_notification_settings import (
    GetNotificationSettingsUseCase,
)
from manashelper.modules.notifications.application.use_cases.toggle_notification_setting import (
    ToggleNotificationSettingUseCase,
)
from manashelper.modules.notifications.settings import NotificationSetting
from manashelper.modules.obis.application.queries import ObisResultsQuery
from manashelper.modules.obis.application.use_cases.clear_obis_credentials import ClearObisCredentialsUseCase
from manashelper.modules.obis.application.use_cases.save_obis_credentials import SaveObisCredentialsUseCase
from manashelper.modules.obis.errors import (
    ObisLoginError,
    ObisParseError,
    ObisSnapshotNotReadyError,
    UserHasNoCredentialsError,
    UserNotFoundError,
)
from manashelper.modules.obis.presentation.callbacks import (
    ObisAction,
    ObisCallback,
    ObisNotificationSettingCallback,
    ObisResultsPageCallback,
)
from manashelper.modules.obis.presentation.formatter import format_attendance_pages, format_exam_grades_pages
from manashelper.modules.obis.presentation.keyboards import (
    build_cancel_keyboard,
    build_confirm_clear_credentials_keyboard,
    build_no_credentials_keyboard,
    build_obis_menu_keyboard,
    build_obis_notifications_keyboard,
    build_obis_results_keyboard,
    build_obis_settings_keyboard,
    build_terms_keyboard,
)
from manashelper.platform.telegram.filters.translated_text import TranslatedText

router = Router(name="obis")
menu_router = Router(name="obis_menu")
logger = logging.getLogger(__name__)
RESULTS_KEY = "obis_result_pages"
MAX_SAVED_RESULTS = 5


class ObisCredentialsForm(StatesGroup):
    student_number = State()
    password = State()


@menu_router.message(TranslatedText("menu.obis"))
@flags.private_chat_only
async def on_obis_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_("menu.obis"), reply_markup=build_obis_menu_keyboard())


@menu_router.callback_query(ObisCallback.filter(F.action == ObisAction.MENU))
@flags.private_chat_only
async def on_back_to_obis_menu(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(_("menu.obis"), reply_markup=build_obis_menu_keyboard())
    await callback.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.NOTIFICATIONS))
@flags.private_chat_only
async def on_obis_notifications(
    callback: CallbackQuery, get_notification_settings: FromDishka[GetNotificationSettingsUseCase]
) -> None:
    try:
        settings = await get_notification_settings.execute(callback.from_user.id)
    except UserNotFoundError:
        await callback.answer(_("common.start_required"), show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _("obis.notifications_header"), reply_markup=build_obis_notifications_keyboard(settings)
        )
    await callback.answer()


@router.callback_query(
    ObisNotificationSettingCallback.filter(
        F.setting.in_({NotificationSetting.EXAM_GRADES, NotificationSetting.LESSON_SKIPS})
    )
)
@flags.private_chat_only
async def on_obis_notification_setting(
    callback: CallbackQuery,
    callback_data: ObisNotificationSettingCallback,
    toggle_notification_setting: FromDishka[ToggleNotificationSettingUseCase],
) -> None:
    try:
        settings = await toggle_notification_setting.execute(callback.from_user.id, callback_data.setting)
    except UserNotFoundError:
        await callback.answer(_("common.start_required"), show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _("obis.notifications_header"), reply_markup=build_obis_notifications_keyboard(settings)
        )
    await callback.answer()


async def _show_obis_results[T](
    message: Message,
    state: FSMContext,
    fetch: Callable[[int], Awaitable[list[T]]],
    format_results: Callable[[list[T]], list[str]],
    loading_text: str,
    *,
    user_id: int | None = None,
) -> bool:
    recipient_id = user_id if user_id is not None else message.from_user.id if message.from_user else None
    if recipient_id is None:
        return False
    sent = await message.answer(loading_text, parse_mode=None)
    try:
        lessons = await fetch(recipient_id)
    except UserNotFoundError:
        await sent.edit_text(_("common.start_required"))
        return False
    except ObisSnapshotNotReadyError:
        await sent.edit_text(_("data.preparing"))
        return False
    except UserHasNoCredentialsError:
        await sent.edit_text(
            _("obis.credentials_missing"),
            reply_markup=build_no_credentials_keyboard(),
        )
        return False
    except ObisLoginError:
        await sent.edit_text(
            _("obis.credentials_invalid"),
            reply_markup=build_no_credentials_keyboard(),
        )
        return False
    except (ObisParseError, httpx.HTTPError):
        logger.warning("Failed to load requested OBIS data", exc_info=True)
        await sent.edit_text(_("obis.fetch_failed"))
        return False
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
    return True


@router.message(TranslatedText("menu.attendance"))
@flags.private_chat_only
async def on_attendance_button(message: Message, state: FSMContext, results: FromDishka[ObisResultsQuery]) -> None:
    await _show_obis_results(
        message, state, results.get_attendance, format_attendance_pages, _("obis.loading_attendance")
    )


@router.message(TranslatedText("menu.grades"))
@flags.private_chat_only
async def on_exams_button(
    message: Message,
    state: FSMContext,
    results: FromDishka[ObisResultsQuery],
    activity: FromDishka[RecordActivityUseCase],
) -> None:
    shown = await _show_obis_results(
        message, state, results.get_exam_grades, format_exam_grades_pages, _("obis.loading_grades")
    )
    if shown and message.from_user is not None:
        await activity.execute(message.from_user.id, "grades")


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


@router.callback_query(ObisCallback.filter(F.action.in_({ObisAction.ATTENDANCE, ObisAction.GRADES})))
@flags.private_chat_only
async def on_obis_view(
    callback: CallbackQuery,
    callback_data: ObisCallback,
    state: FSMContext,
    results: FromDishka[ObisResultsQuery],
    activity: FromDishka[RecordActivityUseCase],
) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    if callback_data.action == ObisAction.ATTENDANCE:
        await _show_obis_results(
            callback.message,
            state,
            results.get_attendance,
            format_attendance_pages,
            _("obis.loading_attendance"),
            user_id=callback.from_user.id,
        )
    else:
        shown = await _show_obis_results(
            callback.message,
            state,
            results.get_exam_grades,
            format_exam_grades_pages,
            _("obis.loading_grades"),
            user_id=callback.from_user.id,
        )
        if shown:
            await activity.execute(callback.from_user.id, "grades")


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
    clear_obis_credentials: FromDishka[ClearObisCredentialsUseCase],
    state: FSMContext,
) -> None:
    try:
        await clear_obis_credentials.execute(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return

    await state.clear()
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
    save_obis_credentials: FromDishka[SaveObisCredentialsUseCase],
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
        await save_obis_credentials.execute(message.from_user.id, student_number, password)
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
