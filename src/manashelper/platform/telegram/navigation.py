from aiogram.enums import ChatType
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.core.config import get_settings
from manashelper.platform.telegram.callbacks import NavigationAction, NavigationCallback


def build_mini_app_button(*, courses: bool = False) -> InlineKeyboardButton | None:
    public_url = get_settings().public_url
    if not public_url:
        return None
    return InlineKeyboardButton(
        text=_("schedule.mini_app") if courses else _("settings.mini_app"),
        web_app=WebAppInfo(url=f"{public_url.rstrip('/')}/app/{'courses' if courses else 'settings'}"),
    )


def build_free_time_button() -> InlineKeyboardButton | None:
    public_url = get_settings().public_url
    if not public_url:
        return None
    return InlineKeyboardButton(
        text=_("schedule.free_time.mini_app"),
        web_app=WebAppInfo(url=f"{public_url.rstrip('/')}/app/free-time"),
    )


def build_navigation_keyboard(back: CallbackData | None = None) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    if back is not None:
        builder.button(text=_("common.back"), callback_data=back)
    builder.button(text=_("common.back_to_menu"), callback_data=NavigationCallback(action=NavigationAction.MAIN))
    builder.adjust(1)
    return builder


def build_main_keyboard(*, achievements_enabled: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("menu.food")), KeyboardButton(text=_("menu.study"))],
            [
                KeyboardButton(text=_("menu.marketplace")),
                *(
                    [KeyboardButton(text=_("menu.achievements_button"))]
                    if achievements_enabled and get_settings().public_url
                    else []
                ),
            ],
            [KeyboardButton(text=_("menu.settings"))],
        ],
        resize_keyboard=True,
    )


def build_study_keyboard() -> ReplyKeyboardMarkup:
    schedule_row = [KeyboardButton(text=_("menu.schedule"))]
    services_row = [KeyboardButton(text=_("menu.obis"))]
    if get_settings().eders_enabled:
        schedule_row.append(KeyboardButton(text=_("menu.study_week")))
        services_row.append(KeyboardButton(text=_("menu.eders")))
    return ReplyKeyboardMarkup(
        keyboard=[
            schedule_row,
            services_row,
            [KeyboardButton(text=_("menu.rooms")), KeyboardButton(text=_("menu.teachers"))],
            [KeyboardButton(text=_("schedule.search_subject"))],
            [KeyboardButton(text=_("common.back_to_menu"))],
        ],
        resize_keyboard=True,
    )


async def send_welcome(message: Message, *, achievements_enabled: bool = False) -> None:
    reply_markup = (
        build_main_keyboard(achievements_enabled=achievements_enabled)
        if message.chat.type == ChatType.PRIVATE
        else ReplyKeyboardRemove()
    )
    await message.answer(_("common.welcome"), reply_markup=reply_markup)
