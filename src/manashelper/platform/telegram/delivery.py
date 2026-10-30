import logging
from collections.abc import Awaitable, Callable
from itertools import batched

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError

from manashelper.modules.users.application.bot_status import BotStatusService

logger = logging.getLogger(__name__)

TELEGRAM_DELETE_MESSAGES_BATCH_SIZE = 100


def is_permanent_recipient_error(error: TelegramAPIError) -> bool:
    if not isinstance(error, (TelegramForbiddenError, TelegramBadRequest)):
        return False
    message = error.message.lower()
    return any(
        reason in message
        for reason in (
            "bot was blocked by the user",
            "bot was stopped by the user",
            "user is deactivated",
            "user was deleted",
            "chat not found",
            "user not found",
            "bot can't initiate conversation with a user",
            "bot can't send messages to bots",
            "input_user_deactivated",
            "peer_id_invalid",
        )
    )


class UserMessageDelivery:
    def __init__(self, status: BotStatusService) -> None:
        self._status = status

    async def send[T](self, user_id: int, action: Callable[[], Awaitable[T]]) -> T | None:
        if await self._status.is_stopped(user_id):
            return None
        try:
            return await action()
        except TelegramAPIError as error:
            if is_permanent_recipient_error(error):
                await self._status.stop(user_id)
            raise


async def send_notification(bot: Bot, user_id: int, text: str, status: BotStatusService) -> None:
    try:
        await UserMessageDelivery(status).send(user_id, lambda: bot.send_message(user_id, text))
    except TelegramAPIError:
        logger.warning("Failed to send notification to user %s", user_id, exc_info=True)


async def delete_messages(bot: Bot, chat_id: int, message_ids: list[int]) -> None:
    for batch in batched(message_ids, TELEGRAM_DELETE_MESSAGES_BATCH_SIZE, strict=False):
        try:
            await bot.delete_messages(chat_id=chat_id, message_ids=list(batch))
        except TelegramAPIError:
            logger.warning("Failed to delete %s message(s) in chat %s", len(batch), chat_id, exc_info=True)
