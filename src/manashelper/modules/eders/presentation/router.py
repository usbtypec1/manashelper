import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from aiogram import F, Router, flags
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.modules.eders.application.eders import EdersQuery, filter_activities
from manashelper.modules.eders.application.models import DeadlineFilter, EdersSnapshot
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.application.use_cases.set_activity_completion import SetActivityCompletionUseCase
from manashelper.modules.eders.application.use_cases.toggle_eders_setting import ToggleEdersSettingUseCase
from manashelper.modules.eders.errors import (
    EdersCompletionUnavailableError,
    EdersFetchError,
    EdersParseError,
    EdersSnapshotNotReadyError,
    EdersUnsafeUrlError,
)
from manashelper.modules.eders.presentation.callbacks import (
    EdersAction,
    EdersCompletionCallback,
    EdersMenuCallback,
    EdersPageCallback,
    EdersSettingCallback,
)
from manashelper.modules.eders.presentation.formatter import format_activity_page, format_completion_message
from manashelper.modules.eders.presentation.keyboards import (
    build_eders_completion_keyboard,
    build_eders_keyboard,
    build_eders_menu_keyboard,
    build_eders_settings_keyboard,
)
from manashelper.modules.obis.errors import ObisLoginError, ObisParseError, UserHasNoCredentialsError, UserNotFoundError
from manashelper.modules.obis.presentation.keyboards import build_no_credentials_keyboard
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback
from manashelper.platform.telegram.filters.translated_text import TranslatedText
from manashelper.platform.telegram.navigation import build_navigation_keyboard

router = Router(name="eders")
menu_router = Router(name="eders_menu")
SNAPSHOT_KEY = "eders_snapshot"
SNAPSHOT_OPENED_AT_KEY = "eders_snapshot_opened_at"
SNAPSHOT_TTL = timedelta(minutes=15)


@router.callback_query(EdersCompletionCallback.filter())
@flags.private_chat_only
async def on_eders_completion(
    callback: CallbackQuery,
    callback_data: EdersCompletionCallback,
    set_completion: FromDishka[SetActivityCompletionUseCase],
) -> None:
    message = callback.message
    if not isinstance(message, Message) or message.chat.id != callback.from_user.id or not message.text:
        await callback.answer(_("eders.completion_unavailable"), show_alert=True)
        return
    try:
        await set_completion.execute(callback.from_user.id, callback_data.activity_id, callback_data.completed)
    except (EdersCompletionUnavailableError, EdersSnapshotNotReadyError):
        await callback.answer(_("eders.completion_unavailable"), show_alert=True)
        return
    except UserNotFoundError:
        await callback.answer(_("common.start_required"), show_alert=True)
        return
    except (UserHasNoCredentialsError, ObisLoginError):
        await callback.answer(_("obis.credentials_missing"), show_alert=True)
        return
    except (EdersFetchError, EdersParseError, EdersUnsafeUrlError, ObisParseError):
        await callback.answer(_("eders.completion_failed"), show_alert=True)
        return

    text = format_completion_message(message.html_text, callback_data.completed)
    keyboard = build_eders_completion_keyboard(callback_data.activity_id, callback_data.completed)
    # The upstream write succeeded. Telegram errors must not roll back its local mirror.
    try:
        await callback.answer(
            _("eders.completion_done") if callback_data.completed else _("eders.completion_undone"), show_alert=True
        )
    except TelegramAPIError:
        logging.getLogger(__name__).warning("Could not answer Eders completion callback")
    if message.html_text != text or message.reply_markup != keyboard:
        try:
            await message.edit_text(
                text, reply_markup=keyboard, link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        except TelegramAPIError:
            logging.getLogger(__name__).warning("Could not edit Eders completion message")


@menu_router.message(TranslatedText("menu.eders"))
@flags.private_chat_only
async def on_eders_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_("menu.eders"), reply_markup=build_eders_menu_keyboard())


@menu_router.callback_query(EdersMenuCallback.filter(F.action == EdersAction.MENU))
@flags.private_chat_only
async def on_back_to_eders_menu(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(_("menu.eders"), reply_markup=build_eders_menu_keyboard())
    await callback.answer()


@router.message(TranslatedText("menu.eders_materials"))
@router.message(Command("eders", "materials"))
@flags.private_chat_only
async def on_eders_command(
    message: Message,
    state: FSMContext,
    eders_query: FromDishka[EdersQuery],
    tracking: FromDishka[EdersTrackingService],
) -> None:
    if message.from_user is None:
        return
    command, _separator, query = (message.text or "").partition(" ")
    is_materials = command.split("@")[0] == "/materials" or message.text == _("menu.eders_materials")
    selected = DeadlineFilter.MATERIALS if is_materials else DeadlineFilter.ALL
    await _show_eders_view(
        message,
        message.from_user.id,
        state,
        eders_query,
        tracking,
        selected,
        query if command.startswith("/") else "",
    )


async def _show_eders_view(
    message: Message,
    user_id: int,
    state: FSMContext,
    eders_query: EdersQuery,
    tracking: EdersTrackingService,
    selected: DeadlineFilter,
    query: str = "",
) -> None:
    await state.update_data({SNAPSHOT_KEY: None})
    keyboard = build_navigation_keyboard(EdersMenuCallback(action=EdersAction.MENU)).as_markup()
    try:
        snapshot = await eders_query.get_snapshot(user_id)
    except UserNotFoundError:
        await message.answer(_("common.start_required"))
        return
    except EdersSnapshotNotReadyError:
        await message.answer(_("data.preparing"), reply_markup=keyboard)
        return
    except UserHasNoCredentialsError:
        await message.answer(_("obis.credentials_missing"), reply_markup=build_no_credentials_keyboard())
        return
    except ObisLoginError:
        await message.answer(_("obis.credentials_invalid"), reply_markup=build_no_credentials_keyboard())
        return
    except (EdersFetchError, EdersParseError, EdersUnsafeUrlError, ObisParseError):
        await message.answer(_("eders.fetch_failed"), reply_markup=keyboard)
        return
    if query.strip():
        search = query.strip().casefold()
        snapshot = replace(
            snapshot,
            activities=tuple(
                item
                for item in snapshot.activities
                if search in f"{item.course.name} {item.section} {item.name} {item.description}".casefold()
            ),
        )
    await state.update_data({SNAPSHOT_KEY: snapshot, SNAPSHOT_OPENED_AT_KEY: datetime.now(UTC)})
    settings = await tracking.get_settings(user_id)
    activities = filter_activities(snapshot.activities, selected, datetime.now(UTC), settings.hide_archived)
    await message.answer(
        format_activity_page(activities, 0),
        reply_markup=build_eders_keyboard(selected, 0, len(activities)),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@router.callback_query(EdersMenuCallback.filter(F.action.in_({EdersAction.MATERIALS, EdersAction.DEADLINES})))
@flags.private_chat_only
async def on_eders_view(
    callback: CallbackQuery,
    callback_data: EdersMenuCallback,
    state: FSMContext,
    eders_query: FromDishka[EdersQuery],
    tracking: FromDishka[EdersTrackingService],
) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        selected = DeadlineFilter.MATERIALS if callback_data.action == EdersAction.MATERIALS else DeadlineFilter.ALL
        await _show_eders_view(callback.message, callback.from_user.id, state, eders_query, tracking, selected)


@router.callback_query(EdersPageCallback.filter())
@flags.private_chat_only
async def on_eders_page(
    callback: CallbackQuery,
    callback_data: EdersPageCallback,
    state: FSMContext,
    tracking: FromDishka[EdersTrackingService],
) -> None:
    data = await state.get_data()
    snapshot = data.get(SNAPSHOT_KEY)
    now = datetime.now(UTC)
    opened_at = data.get(SNAPSHOT_OPENED_AT_KEY, snapshot.fetched_at if isinstance(snapshot, EdersSnapshot) else now)
    if not isinstance(snapshot, EdersSnapshot) or now - opened_at > SNAPSHOT_TTL:
        await callback.answer(_("eders.expired"), show_alert=True)
        return
    settings = await tracking.get_settings(callback.from_user.id)
    activities = filter_activities(snapshot.activities, callback_data.selected, now, settings.hide_archived)
    page = min(max(callback_data.page, 0), max(len(activities) - 1, 0))
    # A selected filter's button always points to its first page; acknowledge a
    # repeated tap without attempting an identical Telegram edit.
    text = format_activity_page(activities, page)
    keyboard = build_eders_keyboard(callback_data.selected, page, len(activities))
    if isinstance(callback.message, Message) and (
        callback.message.html_text != text or callback.message.reply_markup != keyboard
    ):
        await callback.message.edit_text(
            text, reply_markup=keyboard, link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    await callback.answer()


@router.message(Command("eders_settings"))
@flags.private_chat_only
async def on_eders_settings(message: Message, tracking: FromDishka[EdersTrackingService]) -> None:
    if message.from_user is None:
        return
    try:
        settings = await tracking.get_settings(message.from_user.id)
    except UserNotFoundError:
        await message.answer(_("common.start_required"))
        return
    await message.answer(_("eders.settings_header"), reply_markup=build_eders_settings_keyboard(settings))


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_EDERS_NOTIFICATIONS))
@router.callback_query(EdersMenuCallback.filter(F.action == EdersAction.NOTIFICATIONS))
@flags.private_chat_only
async def on_open_eders_settings(callback: CallbackQuery, tracking: FromDishka[EdersTrackingService]) -> None:
    try:
        settings = await tracking.get_settings(callback.from_user.id)
    except UserNotFoundError:
        await callback.answer(_("common.start_required"), show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _("eders.settings_header"), reply_markup=build_eders_settings_keyboard(settings)
        )
    await callback.answer()


@router.callback_query(EdersSettingCallback.filter())
@flags.private_chat_only
async def on_eders_setting(
    callback: CallbackQuery,
    callback_data: EdersSettingCallback,
    toggle_eders_setting: FromDishka[ToggleEdersSettingUseCase],
) -> None:
    try:
        settings = await toggle_eders_setting.execute(callback.from_user.id, callback_data.setting)
    except UserNotFoundError:
        await callback.answer(_("common.start_required"), show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _("eders.settings_header"), reply_markup=build_eders_settings_keyboard(settings)
        )
    await callback.answer()
