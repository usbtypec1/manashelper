import logging
from datetime import UTC, datetime
from functools import partial

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.platform.telegram.deletions.service import MessageDeletionService
from manashelper.platform.telegram.delivery import delete_messages

logger = logging.getLogger(__name__)


async def cleanup_scheduled_message_deletions_job(container: AsyncContainer, bot: Bot) -> None:
    """The outbox sweep: deletes every due message, batched per chat (Bot API allows up to 100 message ids per
    `deleteMessages` call), then drops the processed rows regardless of whether the Telegram call succeeded —
    a message that's already gone (deleted by hand, too old, chat left) is not something to keep retrying."""
    try:
        async with container() as request_container:
            service = await request_container.get(MessageDeletionService)
            now = datetime.now(UTC).replace(tzinfo=None)
            await service.delete_due(now, partial(delete_messages, bot))
    except Exception:
        logger.exception("Failed to clean up scheduled message deletions")
