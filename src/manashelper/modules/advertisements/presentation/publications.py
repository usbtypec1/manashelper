from aiogram import Bot

from manashelper.core.config import Settings
from manashelper.platform.telegram.delivery import delete_messages


class TelegramPublicationRemover:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self._bot = bot
        self._channel_id = settings.advertisement_channel_id

    async def delete_publications(self, message_ids: list[int]) -> None:
        await delete_messages(self._bot, self._channel_id, message_ids)
