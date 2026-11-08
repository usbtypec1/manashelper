from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.platform.telegram.navigation import build_navigation_keyboard


def build_achievements_keyboard(public_url: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("gamification.view_all"), web_app=WebAppInfo(url=f"{public_url}/app/"))]
        ]
    )
    builder = InlineKeyboardBuilder.from_markup(keyboard)
    builder.attach(build_navigation_keyboard())
    return builder.as_markup()
