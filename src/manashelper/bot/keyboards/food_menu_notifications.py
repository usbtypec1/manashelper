from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import (
    FoodMenuNotificationBulkCallback,
    FoodMenuNotificationDayCallback,
    FoodMenuNotificationMealCallback,
    FoodMenuNotificationNoopCallback,
    FoodMenuNotificationWeekdayCallback,
    SettingsAction,
    SettingsCallback,
)
from manashelper.services.food_menu_notification_settings import (
    FoodMenuMeal,
    FoodMenuNotificationSettingsSummary,
)
from manashelper.services.timetable_formatter import weekday_abbr


def _mark(is_enabled: bool) -> str:
    return "✅" if is_enabled else "❌"


def build_food_menu_notifications_keyboard(summary: FoodMenuNotificationSettingsSummary) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text=".", callback_data=FoodMenuNotificationNoopCallback())
    builder.button(text=_("Lunch"), callback_data=FoodMenuNotificationMealCallback(meal=FoodMenuMeal.LUNCH))
    builder.button(text=_("Dinner"), callback_data=FoodMenuNotificationMealCallback(meal=FoodMenuMeal.DINNER))

    for day in summary.days:
        iso_weekday = day.weekday + 1
        builder.button(
            text=weekday_abbr(iso_weekday),
            callback_data=FoodMenuNotificationWeekdayCallback(weekday=day.weekday),
        )
        builder.button(
            text=_mark(day.lunch_enabled),
            callback_data=FoodMenuNotificationDayCallback(weekday=day.weekday, meal=FoodMenuMeal.LUNCH),
        )
        builder.button(
            text=_mark(day.dinner_enabled),
            callback_data=FoodMenuNotificationDayCallback(weekday=day.weekday, meal=FoodMenuMeal.DINNER),
        )

    builder.button(text=_("✅ All"), callback_data=FoodMenuNotificationBulkCallback(enable=True))
    builder.button(text=_("❌ All"), callback_data=FoodMenuNotificationBulkCallback(enable=False))
    builder.button(text=_("◀️ Back"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_NOTIFICATIONS))

    builder.adjust(3, 3, 3, 3, 3, 3, 3, 3, 2, 1)
    return builder.as_markup()


def build_open_food_menu_notifications_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("⚙️ Configure notifications"),
        callback_data=SettingsCallback(action=SettingsAction.OPEN_FOOD_MENU_NOTIFICATIONS),
    )
    builder.adjust(1)
    return builder.as_markup()
