from aiogram import F, Router, flags
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.modules.food_menu.application.food_menu_notification_settings import (
    FoodMenuNotificationSettingsSummary,
    FoodMenuSettingsQuery,
    UserNotFoundError,
)
from manashelper.modules.food_menu.application.use_cases.disable_food_menu_notifications import (
    DisableFoodMenuNotificationsUseCase,
)
from manashelper.modules.food_menu.application.use_cases.enable_food_menu_notifications import (
    EnableFoodMenuNotificationsUseCase,
)
from manashelper.modules.food_menu.application.use_cases.toggle_food_menu_meal import ToggleFoodMenuMealUseCase
from manashelper.modules.food_menu.application.use_cases.toggle_food_menu_meal_for_week import (
    ToggleFoodMenuMealForWeekUseCase,
)
from manashelper.modules.food_menu.application.use_cases.toggle_food_menu_weekday import ToggleFoodMenuWeekdayUseCase
from manashelper.modules.food_menu.presentation.callbacks import (
    FoodMenuNotificationBulkCallback,
    FoodMenuNotificationDayCallback,
    FoodMenuNotificationMealCallback,
    FoodMenuNotificationNoopCallback,
    FoodMenuNotificationWeekdayCallback,
)
from manashelper.modules.food_menu.presentation.keyboards.food_menu_notifications import (
    build_food_menu_notifications_keyboard,
)
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback

router = Router(name="food_menu_notifications")


async def _show_food_menu_notifications(
    callback_query: CallbackQuery, summary: FoodMenuNotificationSettingsSummary
) -> None:
    if isinstance(callback_query.message, Message):
        send = (
            callback_query.message.answer if callback_query.message.rich_message else callback_query.message.edit_text
        )
        await send(_("food.notification_settings"), reply_markup=build_food_menu_notifications_keyboard(summary))


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_FOOD_MENU_NOTIFICATIONS))
@flags.private_chat_only
async def on_open_food_menu_notifications(
    callback_query: CallbackQuery,
    food_menu_settings_query: FromDishka[FoodMenuSettingsQuery],
) -> None:
    try:
        summary = await food_menu_settings_query.get_settings(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return
    await _show_food_menu_notifications(callback_query, summary)
    await callback_query.answer()


@router.callback_query(FoodMenuNotificationDayCallback.filter())
@flags.private_chat_only
async def on_toggle_food_menu_notification_day(
    callback_query: CallbackQuery,
    callback_data: FoodMenuNotificationDayCallback,
    toggle_food_menu_meal: FromDishka[ToggleFoodMenuMealUseCase],
) -> None:
    try:
        summary = await toggle_food_menu_meal.execute(
            callback_query.from_user.id, callback_data.weekday, callback_data.meal
        )
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return
    await _show_food_menu_notifications(callback_query, summary)
    await callback_query.answer()


@router.callback_query(FoodMenuNotificationWeekdayCallback.filter())
@flags.private_chat_only
async def on_toggle_food_menu_notification_weekday(
    callback_query: CallbackQuery,
    callback_data: FoodMenuNotificationWeekdayCallback,
    toggle_food_menu_weekday: FromDishka[ToggleFoodMenuWeekdayUseCase],
) -> None:
    try:
        summary = await toggle_food_menu_weekday.execute(callback_query.from_user.id, callback_data.weekday)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return
    await _show_food_menu_notifications(callback_query, summary)
    await callback_query.answer()


@router.callback_query(FoodMenuNotificationMealCallback.filter())
@flags.private_chat_only
async def on_toggle_food_menu_notification_meal(
    callback_query: CallbackQuery,
    callback_data: FoodMenuNotificationMealCallback,
    toggle_food_menu_meal_for_week: FromDishka[ToggleFoodMenuMealForWeekUseCase],
) -> None:
    try:
        summary = await toggle_food_menu_meal_for_week.execute(callback_query.from_user.id, callback_data.meal)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return
    await _show_food_menu_notifications(callback_query, summary)
    await callback_query.answer()


@router.callback_query(FoodMenuNotificationBulkCallback.filter())
@flags.private_chat_only
async def on_bulk_toggle_food_menu_notifications(
    callback_query: CallbackQuery,
    callback_data: FoodMenuNotificationBulkCallback,
    food_menu_settings_query: FromDishka[FoodMenuSettingsQuery],
    disable_food_menu_notifications: FromDishka[DisableFoodMenuNotificationsUseCase],
    enable_food_menu_notifications: FromDishka[EnableFoodMenuNotificationsUseCase],
) -> None:
    try:
        if callback_data.enable:
            summary = await enable_food_menu_notifications.execute(callback_query.from_user.id)
        else:
            summary = await disable_food_menu_notifications.execute(callback_query.from_user.id)
    except UserNotFoundError:
        await callback_query.answer(_("common.start_required"), show_alert=True)
        return
    await _show_food_menu_notifications(callback_query, summary)
    await callback_query.answer()


@router.callback_query(FoodMenuNotificationNoopCallback.filter())
@flags.private_chat_only
async def on_food_menu_notification_noop(callback_query: CallbackQuery) -> None:
    await callback_query.answer(_("common.not_a_button"))
