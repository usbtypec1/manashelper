from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from manashelper.bot.callback_data import NotificationSettingCallback, SettingsAction, SettingsCallback
from manashelper.bot.keyboards.settings import (
    build_food_menu_notifications_keyboard,
    build_notifications_keyboard,
    build_settings_keyboard,
)
from manashelper.services.notification_settings_service import (
    NotificationSetting,
    NotificationSettingsService,
    NotificationSettingsSummary,
    UserNotFoundError,
)

router = Router(name="settings")

NOTIFICATIONS_TEXT = "Настройки уведомлений бота"
FOOD_MENU_NOTIFICATIONS_TEXT = "Бот будет присылать актуальное меню в 11:00 и 17:00"
FOOD_MENU_SETTINGS = {NotificationSetting.BEFORE_LUNCH, NotificationSetting.BEFORE_DINNER}


async def _show_notifications_menu(callback_query: CallbackQuery, settings: NotificationSettingsSummary) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(NOTIFICATIONS_TEXT, reply_markup=build_notifications_keyboard(settings))


async def _show_food_menu_notifications(callback_query: CallbackQuery, settings: NotificationSettingsSummary) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            FOOD_MENU_NOTIFICATIONS_TEXT, reply_markup=build_food_menu_notifications_keyboard(settings)
        )


@router.message(F.text == "⚙️ Настройки")
async def on_settings_button(message: Message) -> None:
    await message.answer("Настройки", reply_markup=build_settings_keyboard())


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


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_FOOD_MENU_NOTIFICATIONS))
async def on_open_food_menu_notifications(
    callback_query: CallbackQuery,
    notification_settings_service: FromDishka[NotificationSettingsService],
) -> None:
    try:
        settings = await notification_settings_service.get_settings(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer("Пожалуйста, начните с команды /start", show_alert=True)
        return
    await _show_food_menu_notifications(callback_query, settings)
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

    if callback_data.setting in FOOD_MENU_SETTINGS:
        await _show_food_menu_notifications(callback_query, settings)
    else:
        await _show_notifications_menu(callback_query, settings)
    await callback_query.answer()
