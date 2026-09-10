from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from manashelper.bot.callback_data import NotificationSettingCallback, SettingsAction, SettingsCallback
from manashelper.bot.keyboards.obis import build_obis_settings_keyboard
from manashelper.bot.keyboards.settings import build_notifications_keyboard, build_settings_keyboard
from manashelper.bot.keyboards.timetable import build_faculty_keyboard
from manashelper.services.faculty_service import FacultyService
from manashelper.services.notification_settings_service import (
    NotificationSettingsService,
    NotificationSettingsSummary,
    UserNotFoundError,
)
from manashelper.services.obis_service import ObisService
from manashelper.services.obis_service import UserNotFoundError as ObisUserNotFoundError

router = Router(name="settings")

SETTINGS_TEXT = "Настройки"
NOTIFICATIONS_TEXT = "Настройки уведомлений бота"
OBIS_SETTINGS_TEXT = "Настройки OBIS"


async def _show_notifications_menu(callback_query: CallbackQuery, settings: NotificationSettingsSummary) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(NOTIFICATIONS_TEXT, reply_markup=build_notifications_keyboard(settings))


@router.message(F.text == "⚙️ Настройки")
async def on_settings_button(message: Message) -> None:
    await message.answer(SETTINGS_TEXT, reply_markup=build_settings_keyboard())


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.BACK_TO_SETTINGS))
async def on_back_to_settings(callback_query: CallbackQuery) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(SETTINGS_TEXT, reply_markup=build_settings_keyboard())
    await callback_query.answer()


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_NOTIFICATIONS))
async def on_open_notifications(
    callback_query: CallbackQuery,
    notification_settings_service: FromDishka[NotificationSettingsService],
) -> None:
    try:
        settings = await notification_settings_service.get_settings(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer("Пожалуйста, начните с команды /start", show_alert=True)
        return
    await _show_notifications_menu(callback_query, settings)
    await callback_query.answer()


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.BACK_TO_NOTIFICATIONS))
async def on_back_to_notifications(
    callback_query: CallbackQuery,
    notification_settings_service: FromDishka[NotificationSettingsService],
) -> None:
    await on_open_notifications(callback_query, notification_settings_service)


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_COURSE_TRACKING))
async def on_open_course_tracking(
    callback_query: CallbackQuery,
    faculty_service: FromDishka[FacultyService],
) -> None:
    faculties = await faculty_service.get_all_faculties()
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text("Список факультетов", reply_markup=build_faculty_keyboard(faculties))
    await callback_query.answer()


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_OBIS))
async def on_open_obis(
    callback_query: CallbackQuery,
    obis_service: FromDishka[ObisService],
) -> None:
    try:
        has_credentials = await obis_service.has_credentials(callback_query.from_user.id)
    except ObisUserNotFoundError:
        await callback_query.answer("Пожалуйста, начните с команды /start", show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            OBIS_SETTINGS_TEXT, reply_markup=build_obis_settings_keyboard(has_credentials)
        )
    await callback_query.answer()


@router.callback_query(NotificationSettingCallback.filter())
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
        await callback_query.answer("Пожалуйста, начните с команды /start", show_alert=True)
        return

    await _show_notifications_menu(callback_query, settings)
    await callback_query.answer()
