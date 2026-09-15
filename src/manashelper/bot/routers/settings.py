from aiogram import F, Router, flags
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import NotificationSettingCallback, SettingsAction, SettingsCallback
from manashelper.bot.filters.translated_text import TranslatedText
from manashelper.bot.keyboards.obis import build_obis_settings_keyboard
from manashelper.bot.keyboards.settings import build_notifications_keyboard, build_settings_keyboard
from manashelper.bot.keyboards.timetable import build_faculty_keyboard
from manashelper.services.faculty import FacultyService
from manashelper.services.notification_settings import (
    NotificationSettingsService,
    NotificationSettingsSummary,
    UserNotFoundError,
)
from manashelper.services.obis import ObisService
from manashelper.services.obis import UserNotFoundError as ObisUserNotFoundError

router = Router(name="settings")


async def _show_notifications_menu(callback_query: CallbackQuery, settings: NotificationSettingsSummary) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("Bot notification settings"), reply_markup=build_notifications_keyboard(settings)
        )


@router.message(TranslatedText("⚙️ Settings"))
@flags.private_chat_only
async def on_settings_button(message: Message) -> None:
    await message.answer(_("Settings"), reply_markup=build_settings_keyboard())


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.BACK_TO_SETTINGS))
@flags.private_chat_only
async def on_back_to_settings(callback_query: CallbackQuery) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("Settings"), reply_markup=build_settings_keyboard())
    await callback_query.answer()


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_NOTIFICATIONS))
@flags.private_chat_only
async def on_open_notifications(
    callback_query: CallbackQuery,
    notification_settings_service: FromDishka[NotificationSettingsService],
) -> None:
    try:
        settings = await notification_settings_service.get_settings(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return
    await _show_notifications_menu(callback_query, settings)
    await callback_query.answer()


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.BACK_TO_NOTIFICATIONS))
@flags.private_chat_only
async def on_back_to_notifications(
    callback_query: CallbackQuery,
    notification_settings_service: FromDishka[NotificationSettingsService],
) -> None:
    await on_open_notifications(callback_query, notification_settings_service)


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_COURSE_TRACKING))
@flags.private_chat_only
async def on_open_course_tracking(
    callback_query: CallbackQuery,
    faculty_service: FromDishka[FacultyService],
) -> None:
    faculties = await faculty_service.get_all_faculties()
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("List of faculties"), reply_markup=build_faculty_keyboard(faculties))
    await callback_query.answer()


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_OBIS))
@flags.private_chat_only
async def on_open_obis(
    callback_query: CallbackQuery,
    obis_service: FromDishka[ObisService],
) -> None:
    try:
        has_credentials = await obis_service.has_credentials(callback_query.from_user.id)
    except ObisUserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("OBIS settings"), reply_markup=build_obis_settings_keyboard(has_credentials)
        )
    await callback_query.answer()


@router.callback_query(NotificationSettingCallback.filter())
@flags.private_chat_only
async def on_toggle_notification_setting(
    callback_query: CallbackQuery,
    callback_data: NotificationSettingCallback,
    notification_settings_service: FromDishka[NotificationSettingsService],
) -> None:
    try:
        settings = await notification_settings_service.toggle_setting(
            callback_query.from_user.id, callback_data.setting
        )
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return

    await _show_notifications_menu(callback_query, settings)
    await callback_query.answer()
