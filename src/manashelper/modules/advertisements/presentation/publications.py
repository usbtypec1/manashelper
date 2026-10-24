from aiogram import Bot

from manashelper.config import Settings
from manashelper.jobs.common import TELEGRAM_DELETE_MESSAGES_BATCH_SIZE, chunk, delete_message_batch


class TelegramPublicationRemover:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self._bot = bot
        self._channel_id = settings.advertisement_channel_id

    async def delete_publications(self, message_ids: list[int]) -> None:
        for batch in chunk(message_ids, TELEGRAM_DELETE_MESSAGES_BATCH_SIZE):
            await delete_message_batch(self._bot, self._channel_id, batch)
