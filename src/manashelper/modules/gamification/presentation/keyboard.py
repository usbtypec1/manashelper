from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.i18n import gettext as _


def build_achievements_keyboard(public_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("gamification.view_all"), web_app=WebAppInfo(url=f"{public_url}/app/"))]
        ]
    )
