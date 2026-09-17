from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.repositories.scheduled_message_deletion_repository import ScheduledMessageDeletionRepository
from manashelper.services.message_deletion import MessageDeletionService


async def test_schedule_deletion_creates_one_row_per_message(session: AsyncSession) -> None:
    repository = ScheduledMessageDeletionRepository(session)
    service = MessageDeletionService(repository)

    await service.schedule_deletion(chat_id=555, message_ids=[1, 2, 3], after=timedelta(minutes=15))
    await session.flush()

    now = datetime.now(UTC).replace(tzinfo=None)
    due = await repository.get_due_grouped_by_chat(now + timedelta(minutes=16))
    assert sorted(message_id for _, message_id in due[555]) == [1, 2, 3]


async def test_get_due_grouped_by_chat_excludes_not_yet_due(session: AsyncSession) -> None:
    repository = ScheduledMessageDeletionRepository(session)
    service = MessageDeletionService(repository)

    await service.schedule_deletion(chat_id=1, message_ids=[10], after=timedelta(minutes=15))
    await service.schedule_deletion(chat_id=2, message_ids=[20], after=timedelta(hours=3))
    await session.flush()

    now = datetime.now(UTC).replace(tzinfo=None)
    due = await repository.get_due_grouped_by_chat(now + timedelta(minutes=16))

    assert list(due.keys()) == [1]
    assert [message_id for _, message_id in due[1]] == [10]


async def test_delete_by_ids_removes_rows_even_though_deletion_was_never_attempted(session: AsyncSession) -> None:
    repository = ScheduledMessageDeletionRepository(session)
    service = MessageDeletionService(repository)

    await service.schedule_deletion(chat_id=3, message_ids=[30, 31], after=timedelta(minutes=1))
    await session.flush()

    now = datetime.now(UTC).replace(tzinfo=None)
    due = await repository.get_due_grouped_by_chat(now + timedelta(minutes=2))
    task_ids = [task_id for task_id, _ in due[3]]

    await repository.delete_by_ids(task_ids)
    await session.flush()

    due_after = await repository.get_due_grouped_by_chat(now + timedelta(minutes=2))
    assert 3 not in due_after
