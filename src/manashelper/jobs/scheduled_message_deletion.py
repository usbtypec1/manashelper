import logging
import uuid
from datetime import UTC, datetime

from aiogram import Bot
from dishka import AsyncContainer

from manashelper.jobs.common import TELEGRAM_DELETE_MESSAGES_BATCH_SIZE, chunk, delete_message_batch
from manashelper.repositories.scheduled_message_deletion_repository import ScheduledMessageDeletionRepository

logger = logging.getLogger(__name__)


async def cleanup_scheduled_message_deletions_job(container: AsyncContainer, bot: Bot) -> None:
    """The outbox sweep: deletes every due message, batched per chat (Bot API allows up to 100 message ids per
    `deleteMessages` call), then drops the processed rows regardless of whether the Telegram call succeeded —
    a message that's already gone (deleted by hand, too old, chat left) is not something to keep retrying."""
    try:
        async with container() as request_container:
            scheduled_message_deletion_repository = await request_container.get(ScheduledMessageDeletionRepository)
            now = datetime.now(UTC).replace(tzinfo=None)
            due_by_chat = await scheduled_message_deletion_repository.get_due_grouped_by_chat(now)
            if not due_by_chat:
                return

            processed_ids: list[uuid.UUID] = []
            for chat_id, tasks in due_by_chat.items():
                message_ids = [message_id for _, message_id in tasks]
                for batch in chunk(message_ids, TELEGRAM_DELETE_MESSAGES_BATCH_SIZE):
                    await delete_message_batch(bot, chat_id, batch)
                processed_ids.extend(task_id for task_id, _ in tasks)

            await scheduled_message_deletion_repository.delete_by_ids(processed_ids)
    except Exception:
        logger.exception("Failed to clean up scheduled message deletions")
