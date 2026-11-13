import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from functools import partial

import httpx
from aiogram import F, Router, flags
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InputMediaPhoto, Message
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
from manashelper.modules.obis.application.models import ObisCaptcha, ObisLoginAttempt, PendingObisLogin
from manashelper.modules.obis.application.queries import ObisResultsQuery
from manashelper.modules.obis.application.use_cases.clear_obis_credentials import ClearObisCredentialsUseCase
from manashelper.modules.obis.application.use_cases.complete_obis_login import CompleteObisLoginUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_captcha import RefreshObisCaptchaUseCase
from manashelper.modules.obis.application.use_cases.start_obis_login import StartObisLoginUseCase
from manashelper.modules.obis.errors import (
    ObisCaptchaError,
    ObisLoginError,
    ObisParseError,
    ObisSessionExpiredError,
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
    build_captcha_keyboard,
    build_confirm_clear_credentials_keyboard,
    build_login_keyboard,
    build_no_credentials_keyboard,
    build_obis_menu_keyboard,
    build_obis_notifications_keyboard,
    build_obis_results_keyboard,
    build_obis_settings_keyboard,
    build_terms_keyboard,
)
from manashelper.modules.schedule.application.subject_timetable import SubjectTimetableQuery
from manashelper.platform.legal import TERMS_SOURCES, TERMS_UPDATED, terms_sections, terms_ui_strings
from manashelper.platform.telegram.filters.translated_text import TranslatedText
from manashelper.platform.telegram.html import escape_html

router = Router(name="obis")
menu_router = Router(name="obis_menu")
logger = logging.getLogger(__name__)
RESULTS_KEY = "obis_result_pages"
MAX_SAVED_RESULTS = 5
PENDING_LOGIN_KEY = "obis_pending_login"


class ObisCredentialsForm(StatesGroup):
    student_number = State()
    password = State()
    captcha = State()


def pending_login_data(pending: PendingObisLogin) -> dict[str, object]:
    # Plain values keep FSM data storage-agnostic; the password remains encrypted.
    return {
        "student_number": pending.student_number,
        "encrypted_password": pending.encrypted_password,
        "cookies": dict(pending.attempt.cookies),
        "csrf_token": pending.attempt.csrf_token,
    }


def load_pending_login(data: dict[str, object]) -> PendingObisLogin | None:
    match data.get(PENDING_LOGIN_KEY):
        case {
            "student_number": str(student_number),
            "encrypted_password": str(encrypted_password),
            "cookies": dict(cookies),
            "csrf_token": str(csrf_token),
        }:
            attempt = ObisLoginAttempt({str(key): str(value) for key, value in cookies.items()}, csrf_token)
            return PendingObisLogin(student_number, encrypted_password, attempt)
    return None


async def _ask_captcha(message: Message, state: FSMContext, captcha: ObisCaptcha, caption: str) -> None:
    await state.set_state(ObisCredentialsForm.captcha)
    await state.update_data({PENDING_LOGIN_KEY: pending_login_data(captcha.pending)})
    await message.answer_photo(
        BufferedInputFile(captcha.image, "captcha.png"), caption=caption, reply_markup=build_captcha_keyboard()
    )


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
    results: ObisResultsQuery,
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
        await sent.edit_text(_("data.preparing"), reply_markup=build_obis_results_keyboard(0, 1))
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
    except ObisSessionExpiredError:
        await sent.edit_text(_("obis.session_required"), reply_markup=build_login_keyboard())
        return False
    except (ObisParseError, httpx.HTTPError):
        logger.warning("Failed to load requested OBIS data", exc_info=True)
        await sent.edit_text(_("obis.fetch_failed"), reply_markup=build_obis_results_keyboard(0, 1))
        return False
    except Exception:
        await sent.edit_text(_("obis.fetch_failed"), reply_markup=build_obis_results_keyboard(0, 1))
        raise
    pages = format_results(lessons)
    if len(pages) > 1:
        data = await state.get_data()
        snapshots: dict[str, list[str]] = dict(data.get(RESULTS_KEY, {}))
        snapshots[str(sent.message_id)] = pages
        while len(snapshots) > MAX_SAVED_RESULTS:
            snapshots.pop(next(iter(snapshots)))
        await state.update_data({RESULTS_KEY: snapshots})
    # Cached data stays visible after the session ends, with a way to resume synchronization.
    login = not await results.has_session(recipient_id)
    await sent.edit_text(
        pages[0], parse_mode=None, reply_markup=build_obis_results_keyboard(0, len(pages), login=login)
    )
    return True


@router.message(TranslatedText("menu.attendance"))
@flags.private_chat_only
async def on_attendance_button(
    message: Message,
    state: FSMContext,
    results: FromDishka[ObisResultsQuery],
    subject_timetable: FromDishka[SubjectTimetableQuery],
) -> None:
    if message.from_user is None:
        return
    weeks = await subject_timetable.weekly_by_subject(message.from_user.id)
    await _show_obis_results(
        message,
        state,
        results,
        results.get_attendance,
        partial(format_attendance_pages, weeks=weeks),
        _("obis.loading_attendance"),
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
        message, state, results, results.get_exam_grades, format_exam_grades_pages, _("obis.loading_grades")
    )
    if shown and message.from_user is not None:
        await activity.execute(message.from_user.id, "grades")


@router.callback_query(ObisResultsPageCallback.filter())
@flags.private_chat_only
async def on_obis_results_page(
    callback_query: CallbackQuery,
    callback_data: ObisResultsPageCallback,
    state: FSMContext,
    results: FromDishka[ObisResultsQuery],
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
            reply_markup=build_obis_results_keyboard(
                callback_data.page, len(pages), login=not await results.has_session(callback_query.from_user.id)
            ),
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
    subject_timetable: FromDishka[SubjectTimetableQuery],
) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    if callback_data.action == ObisAction.ATTENDANCE:
        weeks = await subject_timetable.weekly_by_subject(callback.from_user.id)
        await _show_obis_results(
            callback.message,
            state,
            results,
            results.get_attendance,
            partial(format_attendance_pages, weeks=weeks),
            _("obis.loading_attendance"),
            user_id=callback.from_user.id,
        )
    else:
        shown = await _show_obis_results(
            callback.message,
            state,
            results,
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


@router.callback_query(ObisCallback.filter(F.action == ObisAction.TERMS))
@flags.private_chat_only
async def on_terms(callback_query: CallbackQuery) -> None:
    await callback_query.answer()
    if not isinstance(callback_query.message, Message):
        return
    title = terms_ui_strings()["title"]
    await callback_query.message.answer(f"{title} · {TERMS_UPDATED}", parse_mode=None)
    for key, title, body in terms_sections():
        sources = TERMS_SOURCES.get(key, ())
        text = "\n\n".join((title, body, *sources))
        await callback_query.message.answer(escape_html(text))


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
    start_obis_login: FromDishka[StartObisLoginUseCase],
) -> None:
    password = message.text.strip() if message.text else ""
    data = await state.get_data()
    student_number = data.get("student_number")

    with suppress(TelegramBadRequest):
        await message.delete()

    if not password or not isinstance(student_number, str) or not student_number or message.from_user is None:
        await state.clear()
        await message.answer(_("common.error_retry"))
        return

    try:
        captcha = await start_obis_login.execute(message.from_user.id, student_number, password)
    except UserNotFoundError:
        await state.clear()
        await message.answer(_("common.start_required"))
        return
    except (ObisParseError, httpx.HTTPError):
        logger.warning("Failed to open OBIS login form", exc_info=True)
        await state.clear()
        await message.answer(_("obis.fetch_failed"))
        return
    await _ask_captcha(message, state, captcha, _("obis.captcha_prompt"))


@router.callback_query(ObisCallback.filter(F.action == ObisAction.LOGIN))
@flags.private_chat_only
async def on_login(
    callback_query: CallbackQuery, state: FSMContext, start_obis_login: FromDishka[StartObisLoginUseCase]
) -> None:
    await callback_query.answer()
    message = callback_query.message
    if not isinstance(message, Message):
        return
    try:
        captcha = await start_obis_login.execute(callback_query.from_user.id)
    except UserNotFoundError:
        await message.answer(_("common.start_required"))
        return
    except UserHasNoCredentialsError:
        await message.answer(_("obis.credentials_missing"), reply_markup=build_no_credentials_keyboard())
        return
    except (ObisParseError, httpx.HTTPError):
        logger.warning("Failed to open OBIS login form", exc_info=True)
        await message.answer(_("obis.fetch_failed"))
        return
    await _ask_captcha(message, state, captcha, _("obis.captcha_prompt"))


@router.callback_query(
    StateFilter(ObisCredentialsForm.captcha), ObisCallback.filter(F.action == ObisAction.REFRESH_CAPTCHA)
)
@flags.private_chat_only
async def on_refresh_captcha(
    callback_query: CallbackQuery, state: FSMContext, refresh_obis_captcha: FromDishka[RefreshObisCaptchaUseCase]
) -> None:
    pending = load_pending_login(await state.get_data())
    message = callback_query.message
    if pending is None or not isinstance(message, Message):
        await callback_query.answer(_("common.error_retry"), show_alert=True)
        return
    try:
        captcha = await refresh_obis_captcha.execute(pending)
    except (ObisParseError, httpx.HTTPError):
        logger.warning("Failed to refresh OBIS captcha", exc_info=True)
        await callback_query.answer(_("obis.fetch_failed"), show_alert=True)
        return
    await state.update_data({PENDING_LOGIN_KEY: pending_login_data(captcha.pending)})
    media = InputMediaPhoto(media=BufferedInputFile(captcha.image, "captcha.png"), caption=_("obis.captcha_prompt"))
    await message.edit_media(media, reply_markup=build_captcha_keyboard())
    await callback_query.answer()


@router.callback_query(ObisCallback.filter(F.action == ObisAction.REFRESH_CAPTCHA))
@flags.private_chat_only
async def on_expired_captcha(callback_query: CallbackQuery) -> None:
    # The form was cancelled or replaced, so an old captcha button has nothing to refresh.
    await callback_query.answer(_("common.error_retry"), show_alert=True)


@router.message(StateFilter(ObisCredentialsForm.captcha))
@flags.private_chat_only
async def on_captcha_entered(
    message: Message,
    state: FSMContext,
    complete_obis_login: FromDishka[CompleteObisLoginUseCase],
    refresh_obis_captcha: FromDishka[RefreshObisCaptchaUseCase],
) -> None:
    code = message.text.strip() if message.text else ""
    pending = load_pending_login(await state.get_data())
    if pending is None or message.from_user is None:
        await state.clear()
        await message.answer(_("common.error_retry"))
        return
    if not code:
        await message.answer(_("obis.captcha_prompt"), reply_markup=build_captcha_keyboard())
        return

    try:
        await complete_obis_login.execute(message.from_user.id, pending, code)
    except ObisCaptchaError:
        try:
            captcha = await refresh_obis_captcha.execute(pending)
        except (ObisParseError, httpx.HTTPError):
            logger.warning("Failed to refresh OBIS captcha", exc_info=True)
            await state.clear()
            await message.answer(_("obis.fetch_failed"))
            return
        await _ask_captcha(message, state, captcha, _("obis.captcha_invalid"))
        return
    except ObisLoginError:
        await state.set_state(ObisCredentialsForm.student_number)
        await message.answer(_("obis.login_failed"), reply_markup=build_cancel_keyboard())
        return
    except UserNotFoundError:
        await state.clear()
        await message.answer(_("common.start_required"))
        return
    except (ObisParseError, httpx.HTTPError):
        logger.warning("Failed to complete OBIS login", exc_info=True)
        await state.clear()
        await message.answer(_("obis.fetch_failed"))
        return

    await state.clear()
    await message.answer(_("obis.logged_in"), reply_markup=build_obis_settings_keyboard(has_credentials=True))
