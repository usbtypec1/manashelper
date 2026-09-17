import uuid

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import (
    FoodMenuCallback,
    FoodMenuCleanupOpenCallback,
    FoodMenuDay,
    FoodMenuRatingCallback,
)

_RATING_LABELS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣"}


def _day_label(day: FoodMenuDay) -> str:
    match day:
        case FoodMenuDay.TODAY:
            return _("📅 Today")
        case FoodMenuDay.TOMORROW:
            return _("📆 Tomorrow")
        case _:
            return _("🗓 Day after tomorrow")


def build_day_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for day in FoodMenuDay:
        builder.button(text=_day_label(day), callback_data=FoodMenuCallback(day=day))
    builder.adjust(1)
    return builder.as_markup()


def build_rating_keyboard(daily_menu_id: uuid.UUID) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for score in range(1, 6):
        builder.button(
            text=_RATING_LABELS[score],
            callback_data=FoodMenuRatingCallback(daily_menu_id=daily_menu_id, rating=score),
        )
    builder.button(text=_("🧹 Auto-delete settings"), callback_data=FoodMenuCleanupOpenCallback())
    builder.adjust(5, 1)
    return builder.as_markup()
