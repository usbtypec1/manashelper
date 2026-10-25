import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteMessages
from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.core.provider import CoreProvider
from manashelper.db.models import Advertisement, AdvertisementChannelMessage, User
from manashelper.di import AppProvider, RequestProvider
from manashelper.modules.advertisements import jobs as job
from manashelper.modules.advertisements.application.advertisement import AdvertisementService
from manashelper.modules.advertisements.application.expiry import ExpireAdvertisements, PublicationRemover
from manashelper.modules.advertisements.infrastructure.advertisement_repository import AdvertisementRepository
from manashelper.modules.advertisements.provider import AdvertisementsProvider
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.users.provider import UsersProvider

CHANNEL_ID = -100943001


@pytest.mark.parametrize("fail_first_batch", [False, True])
async def test_expiry_deletes_publications_in_batches_before_removing_rows(session, monkeypatch, fail_first_batch):
    session.add(User(id=943_001, full_name="Expiry owner", username=None))
    await session.flush()
    repository = AdvertisementRepository(session)
    service = AdvertisementService(repository)
    now = datetime.now(UTC).replace(tzinfo=None)
    expired = await service.create_advertisement(
        943_001, "Expired", "Published item", None, now - timedelta(minutes=1), []
    )
    expired_row = await repository.get_by_id(expired.id)
    expired_row.status = "published"
    expired_row.channel_messages = [
        AdvertisementChannelMessage(id=uuid.uuid4(), message_id=index) for index in range(205)
    ]
    pending = await service.create_advertisement(
        943_001, "Pending expired", "Also removed", None, now - timedelta(minutes=1), []
    )
    active = await service.create_advertisement(943_001, "Still active", "Keep this", None, now + timedelta(days=1), [])
    await session.flush()

    class TestSessionProvider(Provider):
        @provide(scope=Scope.REQUEST, override=True)
        def get_session(self) -> AsyncSession:
            return session

    bot = AsyncMock(spec=Bot)
    existing_during_send = []

    async def delete_messages(*, chat_id, message_ids):
        existing_during_send.append(
            await session.scalar(select(Advertisement.id).where(Advertisement.id == expired.id))
        )
        if fail_first_batch and len(existing_during_send) == 1:
            raise TelegramBadRequest(
                method=DeleteMessages(chat_id=chat_id, message_ids=message_ids), message="test: message unavailable"
            )
        return True

    bot.delete_messages.side_effect = delete_messages
    monkeypatch.setattr(job, "get_settings", lambda: SimpleNamespace(advertisement_channel_id=CHANNEL_ID))
    async with make_async_container(
        CoreProvider(),
        AppProvider(),
        RequestProvider(),
        ScheduleProvider(),
        NotificationsProvider(),
        AdvertisementsProvider(),
        UsersProvider(),
        TestSessionProvider(),
    ) as container:
        await job.cleanup_expired_advertisements_job(container, bot)

    assert existing_during_send == [expired.id] * 3
    calls = bot.delete_messages.await_args_list
    assert [call.kwargs["chat_id"] for call in calls] == [CHANNEL_ID] * 3
    assert [call.kwargs["message_ids"] for call in calls] == [
        list(range(100)),
        list(range(100, 200)),
        list(range(200, 205)),
    ]
    assert await session.scalar(select(Advertisement.id).where(Advertisement.id == expired.id)) is None
    assert await session.scalar(select(Advertisement.id).where(Advertisement.id == pending.id)) is None
    assert await session.scalar(select(Advertisement.id).where(Advertisement.id == active.id)) == active.id


@pytest.mark.parametrize("fail_publications", [False, True])
async def test_expiry_use_case_preserves_order_and_propagates_unexpected_adapter_failure(fail_publications):
    rows = [SimpleNamespace(channel_messages=[SimpleNamespace(message_id=10)]), SimpleNamespace(channel_messages=[])]
    repository = AsyncMock(spec=AdvertisementRepository)
    repository.get_expired.return_value = rows
    publications = AsyncMock(spec=PublicationRemover)
    events = []

    async def remove(message_ids):
        events.append(("publications", message_ids))
        if fail_publications:
            raise RuntimeError("adapter failed")

    async def delete(row):
        events.append(("row", row))

    publications.delete_publications.side_effect = remove
    repository.delete.side_effect = delete
    use_case = ExpireAdvertisements(repository, publications)
    if fail_publications:
        with pytest.raises(RuntimeError, match="adapter failed"):
            await use_case.execute()
        assert events == [("publications", [10])]
        repository.delete.assert_not_awaited()
    else:
        await use_case.execute()
        assert events == [("publications", [10]), ("row", rows[0]), ("publications", []), ("row", rows[1])]
    checked_at = repository.get_expired.await_args.args[0]
    assert checked_at.tzinfo is None
    assert abs(datetime.now(UTC).replace(tzinfo=None) - checked_at) < timedelta(seconds=10)
