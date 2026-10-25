import logging
from collections.abc import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)

TELEGRAM_DELETE_MESSAGES_BATCH_SIZE = 100


async def send_notification(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except TelegramAPIError:
        logger.warning("Failed to send notification to user %s", user_id, exc_info=True)


def chunk(items: list[int], size: int) -> Iterable[list[int]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def delete_message_batch(bot: Bot, chat_id: int, message_ids: list[int]) -> None:
    try:
        await bot.delete_messages(chat_id=chat_id, message_ids=message_ids)
    except TelegramAPIError:
        logger.warning("Failed to delete %s message(s) in chat %s", len(message_ids), chat_id, exc_info=True)
