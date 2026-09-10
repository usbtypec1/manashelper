from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import (
    FoodMenuNotificationBulkCallback,
    FoodMenuNotificationDayCallback,
    FoodMenuNotificationNoopCallback,
    SettingsAction,
    SettingsCallback,
)
from manashelper.services.food_menu_notification_settings_service import (
    FoodMenuMeal,
    FoodMenuNotificationSettingsSummary,
)

_WEEKDAY_LABELS = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}


def _mark(is_enabled: bool) -> str:
    return "✅" if is_enabled else "❌"


def build_food_menu_notifications_keyboard(summary: FoodMenuNotificationSettingsSummary) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text=".", callback_data=FoodMenuNotificationNoopCallback())
    builder.button(text="Обед", callback_data=FoodMenuNotificationNoopCallback())
    builder.button(text="Ужин", callback_data=FoodMenuNotificationNoopCallback())

    for day in summary.days:
        builder.button(text=_WEEKDAY_LABELS[day.weekday], callback_data=FoodMenuNotificationNoopCallback())
        builder.button(
            text=_mark(day.lunch_enabled),
            callback_data=FoodMenuNotificationDayCallback(weekday=day.weekday, meal=FoodMenuMeal.LUNCH),
        )
        builder.button(
            text=_mark(day.dinner_enabled),
            callback_data=FoodMenuNotificationDayCallback(weekday=day.weekday, meal=FoodMenuMeal.DINNER),
        )

    builder.button(text="✅ Все", callback_data=FoodMenuNotificationBulkCallback(enable=True))
    builder.button(text="❌ Все", callback_data=FoodMenuNotificationBulkCallback(enable=False))
    builder.button(text="◀️ Назад", callback_data=SettingsCallback(action=SettingsAction.BACK_TO_NOTIFICATIONS))

    builder.adjust(3, 3, 3, 3, 3, 3, 3, 3, 2, 1)
    return builder.as_markup()


def build_open_food_menu_notifications_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⚙️ Настроить уведомления",
        callback_data=SettingsCallback(action=SettingsAction.OPEN_FOOD_MENU_NOTIFICATIONS),
    )
    builder.adjust(1)
    return builder.as_markup()
