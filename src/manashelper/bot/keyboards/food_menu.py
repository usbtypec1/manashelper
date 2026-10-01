import uuid
from datetime import date

from aiogram.types import InlineKeyboardMarkup, InputRichBlockButtons, RichMessageButton
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import (
    FoodMenuCleanupOpenCallback,
    FoodMenuDateCallback,
    FoodMenuOpenCallback,
    FoodMenuRatingCallback,
    SettingsAction,
    SettingsCallback,
)
from manashelper.services.timetable_formatter import weekday_full

_RATING_LABELS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣"}


def _day_label(menu_date: date, today: date) -> str:
    match (menu_date - today).days:
        case 0:
            name = _("food.today")
        case 1:
            name = _("food.tomorrow")
        case 2:
            name = _("food.day_after_tomorrow")
        case _:
            name = weekday_full(menu_date.isoweekday())
    return f"{name} · {menu_date:%d.%m}"


def build_menu_day_buttons(menu_dates: list[date], today: date) -> list[InputRichBlockButtons]:
    return [
        InputRichBlockButtons(
            buttons=[
                RichMessageButton(
                    text=_day_label(menu_date, today),
                    callback_data=FoodMenuDateCallback(menu_date=menu_date.isoformat()).pack(),
                )
            ]
        )
        for menu_date in menu_dates
    ]


def build_menu_open_button() -> InputRichBlockButtons:
    return InputRichBlockButtons(
        buttons=[RichMessageButton(text=_("food.open_menu"), callback_data=FoodMenuOpenCallback().pack())]
    )


def build_food_menu_settings_buttons(*, include_notifications: bool = False) -> list[RichMessageButton]:
    buttons = [
        RichMessageButton(text=_("food.auto_delete_settings"), callback_data=FoodMenuCleanupOpenCallback().pack()),
    ]
    if include_notifications:
        buttons.append(
            RichMessageButton(
                text=_("notifications.configure"),
                callback_data=SettingsCallback(action=SettingsAction.OPEN_FOOD_MENU_NOTIFICATIONS).pack(),
            )
        )
    return buttons


def build_menu_rating_buttons(daily_menu_id: uuid.UUID, user_rating: int | None = None) -> InputRichBlockButtons:
    return InputRichBlockButtons(
        buttons=[
            RichMessageButton(
                text=_RATING_LABELS[score],
                style="success" if score == user_rating else None,
                callback_data=FoodMenuRatingCallback(daily_menu_id=daily_menu_id, rating=score).pack(),
            )
            for score in range(1, 6)
        ]
    )


def build_rating_keyboard(daily_menu_id: uuid.UUID) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for score in range(1, 6):
        builder.button(
            text=_RATING_LABELS[score],
            callback_data=FoodMenuRatingCallback(daily_menu_id=daily_menu_id, rating=score),
        )
    builder.button(text=_("food.auto_delete_settings"), callback_data=FoodMenuCleanupOpenCallback())
    builder.adjust(5, 1)
    return builder.as_markup()
