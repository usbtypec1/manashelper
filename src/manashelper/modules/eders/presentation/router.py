from datetime import UTC, datetime, timedelta

from aiogram import F, Router, flags
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.modules.eders.application.eders import EdersService, filter_activities
from manashelper.modules.eders.application.models import DeadlineFilter, EdersSnapshot
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.presentation.callbacks import EdersPageCallback, EdersSettingCallback
from manashelper.modules.eders.presentation.entrypoints import SNAPSHOT_KEY, SNAPSHOT_OPENED_AT_KEY, show_eders
from manashelper.modules.eders.presentation.formatter import format_activity_page
from manashelper.modules.eders.presentation.keyboards import build_eders_keyboard, build_eders_settings_keyboard
from manashelper.modules.obis.errors import UserNotFoundError
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback
from manashelper.platform.telegram.filters.translated_text import TranslatedText

router = Router(name="eders")


SNAPSHOT_TTL = timedelta(minutes=15)


@router.message(TranslatedText("menu.eders"))
@router.message(TranslatedText("menu.eders_materials"))
@router.message(Command("eders", "materials"))
@flags.private_chat_only
async def on_eders_command(
    message: Message,
    state: FSMContext,
    eders_service: FromDishka[EdersService],
    tracking: FromDishka[EdersTrackingService],
) -> None:
    if message.from_user is None:
        return
    source_text = getattr(message, "text", None) or ""
    command, separator, query = source_text.partition(" ")
    is_materials = command.split("@")[0] == "/materials" or source_text == _("menu.eders_materials")
    selected = DeadlineFilter.MATERIALS if is_materials else DeadlineFilter.ALL
    if not command.startswith("/"):
        query = ""
    await show_eders(message, message.from_user.id, state, eders_service, tracking, selected, query)


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
    callback: CallbackQuery, callback_data: EdersSettingCallback, tracking: FromDishka[EdersTrackingService]
) -> None:
    try:
        settings = await tracking.toggle(callback.from_user.id, callback_data.setting)
    except UserNotFoundError:
        await callback.answer(_("common.start_required"), show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _("eders.settings_header"), reply_markup=build_eders_settings_keyboard(settings)
        )
    await callback.answer()
