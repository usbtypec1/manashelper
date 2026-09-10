import uuid

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import (
    FoodMenuCallback,
    FoodMenuDay,
    FoodMenuRatingCallback,
    NotificationSettingCallback,
)
from manashelper.services.notification_settings_service import NotificationSetting

_DAY_LABELS = {
    FoodMenuDay.TODAY: "📅 Сегодня",
    FoodMenuDay.TOMORROW: "📆 Завтра",
    FoodMenuDay.AFTER_TOMORROW: "🗓 Послезавтра",
}

_RATING_LABELS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣"}


def build_day_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for day, label in _DAY_LABELS.items():
        builder.button(text=label, callback_data=FoodMenuCallback(day=day))
    builder.adjust(1)
    return builder.as_markup()


def build_rating_keyboard(daily_menu_id: uuid.UUID) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for score in range(1, 6):
        builder.button(
            text=_RATING_LABELS[score],
            callback_data=FoodMenuRatingCallback(daily_menu_id=daily_menu_id, rating=score),
        )
    builder.adjust(5)
    return builder.as_markup()


def build_unsubscribe_keyboard(setting: NotificationSetting, label: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=label, callback_data=NotificationSettingCallback(setting=setting))
    builder.adjust(1)
    return builder.as_markup()
