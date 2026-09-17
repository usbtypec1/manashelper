import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import ScheduledMessageDeletion


class ScheduledMessageDeletionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add_many(self, chat_id: int, message_ids: Iterable[int], delete_at: datetime) -> None:
        for message_id in message_ids:
            self._session.add(
                ScheduledMessageDeletion(id=uuid.uuid4(), chat_id=chat_id, message_id=message_id, delete_at=delete_at)
            )

    async def get_due_grouped_by_chat(self, now: datetime) -> dict[int, list[tuple[uuid.UUID, int]]]:
        result = await self._session.execute(
            select(ScheduledMessageDeletion.id, ScheduledMessageDeletion.chat_id, ScheduledMessageDeletion.message_id)
            .where(ScheduledMessageDeletion.delete_at <= now)
            .order_by(ScheduledMessageDeletion.chat_id)
        )
        grouped: dict[int, list[tuple[uuid.UUID, int]]] = defaultdict(list)
        for task_id, chat_id, message_id in result.all():
            grouped[chat_id].append((task_id, message_id))
        return grouped

    async def delete_by_ids(self, ids: Sequence[uuid.UUID]) -> None:
        if not ids:
            return
        await self._session.execute(delete(ScheduledMessageDeletion).where(ScheduledMessageDeletion.id.in_(ids)))
