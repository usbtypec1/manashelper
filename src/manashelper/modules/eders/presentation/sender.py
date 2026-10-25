import logging
from collections.abc import AsyncIterator

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import LinkPreviewOptions

from manashelper.localization.locale import Locale
from manashelper.modules.eders.application.tracking import EdersEvent
from manashelper.modules.eders.presentation.formatter import format_eders_event, format_material_events
from manashelper.platform.i18n.catalog import i18n

logger = logging.getLogger(__name__)


class TelegramEdersNotificationSender:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send(self, user_id: int, locale: Locale, events: list[EdersEvent]) -> AsyncIterator[EdersEvent]:
        with i18n.context(), i18n.use_locale(locale.value):
            materials = [event for event in events if event.event_type.startswith("material_")]
            messages = format_material_events(materials)
            messages.extend(
                (format_eders_event(event), [event]) for event in events if not event.event_type.startswith("material_")
            )
        for text, batch in messages:
            try:
                await self._bot.send_message(user_id, text, link_preview_options=LinkPreviewOptions(is_disabled=True))
            except TelegramAPIError:
                logger.warning("Failed to send eders notification to user %s", user_id, exc_info=True)
                continue
            for event in batch:
                yield event
