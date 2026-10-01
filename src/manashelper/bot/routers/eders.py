from datetime import UTC, datetime, timedelta

from aiogram import Router, flags
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import EdersPageCallback, EdersSettingCallback
from manashelper.bot.keyboards.eders import build_eders_keyboard, build_eders_settings_keyboard
from manashelper.bot.keyboards.obis import build_no_credentials_keyboard
from manashelper.scraping.eders_client import EdersFetchError
from manashelper.scraping.eders_parser import EdersParseError
from manashelper.scraping.eders_urls import EdersUnsafeUrlError
from manashelper.scraping.obis_client import ObisLoginError
from manashelper.scraping.obis_parser import ObisParseError
from manashelper.services.eders import EdersService, filter_activities
from manashelper.services.eders_formatter import format_activity_page
from manashelper.services.eders_models import DeadlineFilter, EdersSnapshot
from manashelper.services.eders_tracking import EdersTrackingService
from manashelper.services.obis import UserHasNoCredentialsError, UserNotFoundError
from manashelper.services.study_week import StudyWeekService
from manashelper.services.study_week_formatter import format_study_week

router = Router(name="eders")
SNAPSHOT_KEY = "eders_snapshot"
SNAPSHOT_TTL = timedelta(minutes=15)


@router.message(Command("eders"))
@flags.private_chat_only
async def on_eders_command(
    message: Message,
    state: FSMContext,
    eders_service: FromDishka[EdersService],
    tracking: FromDishka[EdersTrackingService],
) -> None:
    if message.from_user is None:
        return
    await state.update_data({SNAPSHOT_KEY: None})
    await message.answer(_("eders.loading"))
    try:
        snapshot = await eders_service.get_snapshot(message.from_user.id)
    except UserNotFoundError:
        await message.answer(_("common.start_required"))
        return
    except UserHasNoCredentialsError:
        await message.answer(_("obis.credentials_missing"), reply_markup=build_no_credentials_keyboard())
        return
    except ObisLoginError:
        await message.answer(_("obis.credentials_invalid"), reply_markup=build_no_credentials_keyboard())
        return
    except (EdersFetchError, EdersParseError, EdersUnsafeUrlError, ObisParseError):
        await message.answer(_("eders.fetch_failed"))
        return
    await state.update_data({SNAPSHOT_KEY: snapshot})
    selected = DeadlineFilter.ALL
    settings = await tracking.get_settings(message.from_user.id)
    activities = filter_activities(snapshot.activities, selected, datetime.now(UTC), settings.hide_archived)
    await message.answer(
        format_activity_page(activities, 0),
        reply_markup=build_eders_keyboard(selected, 0, len(activities)),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


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
    if not isinstance(snapshot, EdersSnapshot) or now - snapshot.fetched_at > SNAPSHOT_TTL:
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


@router.message(Command("week"))
@flags.private_chat_only
async def on_week_command(message: Message, week_service: FromDishka[StudyWeekService]) -> None:
    if message.from_user is None:
        return
    await message.answer(_("eders.loading"))
    try:
        week = await week_service.get_week(message.from_user.id)
    except UserNotFoundError:
        await message.answer(_("common.start_required"))
        return
    except UserHasNoCredentialsError:
        await message.answer(_("obis.credentials_missing"), reply_markup=build_no_credentials_keyboard())
        return
    except ObisLoginError:
        await message.answer(_("obis.credentials_invalid"), reply_markup=build_no_credentials_keyboard())
        return
    except (EdersFetchError, EdersParseError, EdersUnsafeUrlError, ObisParseError):
        await message.answer(_("eders.fetch_failed"))
        return
    for text in format_study_week(week):
        await message.answer(text, link_preview_options=LinkPreviewOptions(is_disabled=True))
