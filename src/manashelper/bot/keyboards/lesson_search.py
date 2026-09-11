from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import LessonSearchPageCallback


def build_lesson_search_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup | None:
    if total_pages <= 1:
        return None

    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="⬅️", callback_data=LessonSearchPageCallback(page=page - 1))
    if page < total_pages - 1:
        builder.button(text="➡️", callback_data=LessonSearchPageCallback(page=page + 1))
    builder.adjust(2)
    return builder.as_markup()
