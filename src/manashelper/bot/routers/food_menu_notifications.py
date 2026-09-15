from aiogram import F, Router, flags
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import (
    FoodMenuNotificationBulkCallback,
    FoodMenuNotificationDayCallback,
    FoodMenuNotificationMealCallback,
    FoodMenuNotificationNoopCallback,
    FoodMenuNotificationWeekdayCallback,
    SettingsAction,
    SettingsCallback,
)
from manashelper.bot.keyboards.food_menu_notifications import build_food_menu_notifications_keyboard
from manashelper.services.food_menu_notification_settings import (
    FoodMenuNotificationSettingsService,
    FoodMenuNotificationSettingsSummary,
    UserNotFoundError,
)

router = Router(name="food_menu_notifications")


async def _show_food_menu_notifications(
    callback_query: CallbackQuery, summary: FoodMenuNotificationSettingsSummary
) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("🍽 Fine-tune menu notifications"), reply_markup=build_food_menu_notifications_keyboard(summary)
        )


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_FOOD_MENU_NOTIFICATIONS))
@flags.private_chat_only
async def on_open_food_menu_notifications(
    callback_query: CallbackQuery,
    food_menu_notification_settings_service: FromDishka[FoodMenuNotificationSettingsService],
) -> None:
    try:
        summary = await food_menu_notification_settings_service.get_settings(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return
    await _show_food_menu_notifications(callback_query, summary)
    await callback_query.answer()


@router.callback_query(FoodMenuNotificationDayCallback.filter())
@flags.private_chat_only
async def on_toggle_food_menu_notification_day(
    callback_query: CallbackQuery,
    callback_data: FoodMenuNotificationDayCallback,
    food_menu_notification_settings_service: FromDishka[FoodMenuNotificationSettingsService],
) -> None:
    try:
        summary = await food_menu_notification_settings_service.toggle(
            callback_query.from_user.id, callback_data.weekday, callback_data.meal
        )
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return
    await _show_food_menu_notifications(callback_query, summary)
    await callback_query.answer()


@router.callback_query(FoodMenuNotificationWeekdayCallback.filter())
@flags.private_chat_only
async def on_toggle_food_menu_notification_weekday(
    callback_query: CallbackQuery,
    callback_data: FoodMenuNotificationWeekdayCallback,
    food_menu_notification_settings_service: FromDishka[FoodMenuNotificationSettingsService],
) -> None:
    try:
        summary = await food_menu_notification_settings_service.toggle_weekday(
            callback_query.from_user.id, callback_data.weekday
        )
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return
    await _show_food_menu_notifications(callback_query, summary)
    await callback_query.answer()


@router.callback_query(FoodMenuNotificationMealCallback.filter())
@flags.private_chat_only
async def on_toggle_food_menu_notification_meal(
    callback_query: CallbackQuery,
    callback_data: FoodMenuNotificationMealCallback,
    food_menu_notification_settings_service: FromDishka[FoodMenuNotificationSettingsService],
) -> None:
    try:
        summary = await food_menu_notification_settings_service.toggle_meal(
            callback_query.from_user.id, callback_data.meal
        )
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return
    await _show_food_menu_notifications(callback_query, summary)
    await callback_query.answer()


@router.callback_query(FoodMenuNotificationBulkCallback.filter())
@flags.private_chat_only
async def on_bulk_toggle_food_menu_notifications(
    callback_query: CallbackQuery,
    callback_data: FoodMenuNotificationBulkCallback,
    food_menu_notification_settings_service: FromDishka[FoodMenuNotificationSettingsService],
) -> None:
    try:
        if callback_data.enable:
            summary = await food_menu_notification_settings_service.enable_all(callback_query.from_user.id)
        else:
            summary = await food_menu_notification_settings_service.disable_all(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return
    await _show_food_menu_notifications(callback_query, summary)
    await callback_query.answer()


@router.callback_query(FoodMenuNotificationNoopCallback.filter())
@flags.private_chat_only
async def on_food_menu_notification_noop(callback_query: CallbackQuery) -> None:
    await callback_query.answer(_("this isn't a button"))
