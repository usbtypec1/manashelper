from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import FoodMenuCleanupOpenCallback, FoodMenuCleanupSetCallback
from manashelper.services.food_menu_cleanup_settings import FoodMenuCleanupOption


def _option_label(option: FoodMenuCleanupOption) -> str:
    match option:
        case FoodMenuCleanupOption.MINUTES_15:
            return _("common.duration.minutes_15")
        case FoodMenuCleanupOption.MINUTES_45:
            return _("common.duration.minutes_45")
        case FoodMenuCleanupOption.HOURS_3:
            return _("common.duration.hours_3")
        case FoodMenuCleanupOption.DAY_1:
            return _("common.duration.days_1")
        case _:
            return _("common.off")


def _mark(is_selected: bool) -> str:
    return "✅ " if is_selected else ""


def build_food_menu_cleanup_keyboard(current_option: FoodMenuCleanupOption) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for option in FoodMenuCleanupOption:
        builder.button(
            text=f"{_mark(option == current_option)}{_option_label(option)}",
            callback_data=FoodMenuCleanupSetCallback(option=option),
        )
    builder.adjust(1)
    return builder.as_markup()


def build_open_food_menu_cleanup_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("food.auto_delete_settings"), callback_data=FoodMenuCleanupOpenCallback())
    builder.adjust(1)
    return builder.as_markup()
