import uuid
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime, timedelta

from manashelper.platform.telegram.deletions.repository import ScheduledMessageDeletionRepository


class MessageDeletionService:
    def __init__(self, scheduled_message_deletion_repository: ScheduledMessageDeletionRepository) -> None:
        self._scheduled_message_deletion_repository = scheduled_message_deletion_repository

    async def schedule_deletion(self, chat_id: int, message_ids: Iterable[int], after: timedelta) -> None:
        delete_at = datetime.now(UTC).replace(tzinfo=None) + after
        self._scheduled_message_deletion_repository.add_many(chat_id, message_ids, delete_at)

    async def delete_due(self, now: datetime, delete_messages: Callable[[int, list[int]], Awaitable[None]]) -> None:
        due_by_chat = await self._scheduled_message_deletion_repository.get_due_grouped_by_chat(now)
        if not due_by_chat:
            return

        processed_ids: list[uuid.UUID] = []
        for chat_id, tasks in due_by_chat.items():
            await delete_messages(chat_id, [message_id for _, message_id in tasks])
            processed_ids.extend(task_id for task_id, _ in tasks)

        await self._scheduled_message_deletion_repository.delete_by_ids(processed_ids)
