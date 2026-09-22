import logging
from datetime import UTC, datetime

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.config import get_settings
from manashelper.jobs.common import TELEGRAM_DELETE_MESSAGES_BATCH_SIZE, chunk, delete_message_batch
from manashelper.repositories.advertisement_repository import AdvertisementRepository

logger = logging.getLogger(__name__)


async def cleanup_expired_advertisements_job(container: AsyncContainer, bot: Bot) -> None:
    """Deletes every advertisement past its `expires_at`, removing its channel post(s) first (best
    effort - an already-gone message, e.g. deleted by hand, doesn't block the DB row from being
    dropped) — same outbox-sweep shape as `scheduled_message_deletion.cleanup_scheduled_message_deletions_job`."""
    try:
        async with container() as request_container:
            advertisement_repository = await request_container.get(AdvertisementRepository)
            now = datetime.now(UTC).replace(tzinfo=None)
            expired = await advertisement_repository.get_expired(now)
            if not expired:
                return

            channel_id = get_settings().advertisement_channel_id
            for advertisement in expired:
                message_ids = [cm.message_id for cm in advertisement.channel_messages]
                for batch in chunk(message_ids, TELEGRAM_DELETE_MESSAGES_BATCH_SIZE):
                    await delete_message_batch(bot, channel_id, batch)
                await advertisement_repository.delete(advertisement)
    except Exception:
        logger.exception("Failed to clean up expired advertisements")
