from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


async def edit_view(callback_query: CallbackQuery, text: str, keyboard: InlineKeyboardMarkup) -> None:
    """Edit the callback's message; refreshing an unchanged view (e.g. "now" twice in a minute) is not an error."""
    if not isinstance(callback_query.message, Message):
        return
    try:
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as error:
        if "message is not modified" not in error.message:
            raise
