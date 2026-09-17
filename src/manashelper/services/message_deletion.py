from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from manashelper.repositories.scheduled_message_deletion_repository import ScheduledMessageDeletionRepository


class MessageDeletionService:
    def __init__(self, scheduled_message_deletion_repository: ScheduledMessageDeletionRepository) -> None:
        self._scheduled_message_deletion_repository = scheduled_message_deletion_repository

    async def schedule_deletion(self, chat_id: int, message_ids: Iterable[int], after: timedelta) -> None:
        delete_at = datetime.now(UTC).replace(tzinfo=None) + after
        self._scheduled_message_deletion_repository.add_many(chat_id, message_ids, delete_at)
