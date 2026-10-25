import logging
from itertools import batched

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)

TELEGRAM_DELETE_MESSAGES_BATCH_SIZE = 100


async def send_notification(bot: Bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text)
    except TelegramAPIError:
        logger.warning("Failed to send notification to user %s", user_id, exc_info=True)


async def delete_messages(bot: Bot, chat_id: int, message_ids: list[int]) -> None:
    for batch in batched(message_ids, TELEGRAM_DELETE_MESSAGES_BATCH_SIZE, strict=False):
        try:
            await bot.delete_messages(chat_id=chat_id, message_ids=list(batch))
        except TelegramAPIError:
            logger.warning("Failed to delete %s message(s) in chat %s", len(batch), chat_id, exc_info=True)
