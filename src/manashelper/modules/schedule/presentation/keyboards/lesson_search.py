from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.modules.schedule.presentation.callbacks import (
    LessonSearchPageCallback,
    TimetableMenuAction,
    TimetableMenuCallback,
)
from manashelper.platform.telegram.callbacks import NavigationAction, NavigationCallback
from manashelper.platform.telegram.navigation import build_navigation_keyboard


def build_lesson_search_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="⬅️", callback_data=LessonSearchPageCallback(page=page - 1))
    if page < total_pages - 1:
        builder.button(text="➡️", callback_data=LessonSearchPageCallback(page=page + 1))
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(
            text=_("schedule.search_subject"),
            callback_data=TimetableMenuCallback(action=TimetableMenuAction.OPEN_LESSON_SEARCH).pack(),
        )
    )
    builder.attach(build_navigation_keyboard(NavigationCallback(action=NavigationAction.STUDY)))
    return builder.as_markup()
