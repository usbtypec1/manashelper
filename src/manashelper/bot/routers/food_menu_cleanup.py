from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import FoodMenuCleanupOpenCallback, FoodMenuCleanupSetCallback
from manashelper.bot.keyboards.food_menu_cleanup import build_food_menu_cleanup_keyboard
from manashelper.services.food_menu_cleanup_settings import FoodMenuCleanupSettingsService

router = Router(name="food_menu_cleanup")


async def _show_food_menu_cleanup_settings(
    callback_query: CallbackQuery, food_menu_cleanup_settings_service: FoodMenuCleanupSettingsService
) -> None:
    if not isinstance(callback_query.message, Message):
        return
    option = await food_menu_cleanup_settings_service.get_option(callback_query.message.chat.id)
    await callback_query.message.edit_text(
        _("🧹 Auto-delete food menu messages in this chat after:"),
        reply_markup=build_food_menu_cleanup_keyboard(option),
    )


@router.callback_query(FoodMenuCleanupOpenCallback.filter())
async def on_open_food_menu_cleanup(
    callback_query: CallbackQuery,
    food_menu_cleanup_settings_service: FromDishka[FoodMenuCleanupSettingsService],
) -> None:
    await _show_food_menu_cleanup_settings(callback_query, food_menu_cleanup_settings_service)
    await callback_query.answer()


@router.callback_query(FoodMenuCleanupSetCallback.filter())
async def on_set_food_menu_cleanup(
    callback_query: CallbackQuery,
    callback_data: FoodMenuCleanupSetCallback,
    food_menu_cleanup_settings_service: FromDishka[FoodMenuCleanupSettingsService],
) -> None:
    if isinstance(callback_query.message, Message):
        await food_menu_cleanup_settings_service.set_option(callback_query.message.chat.id, callback_data.option)
    await _show_food_menu_cleanup_settings(callback_query, food_menu_cleanup_settings_service)
    await callback_query.answer(_("Saved"))
