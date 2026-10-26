from unittest.mock import AsyncMock, call

import pytest
from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.broadcast.provider import BroadcastProvider
from manashelper.modules.broadcast.service import BroadcastResult, BroadcastSender, SendBroadcast
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.queries import UsersQuery


async def test_broadcast_reaches_every_registered_user(session: AsyncSession) -> None:
    session.add_all(
        [
            User(id=950_001, full_name="Test User", username=None),
            User(id=950_002, full_name="Test User", username=None),
        ]
    )
    await session.flush()

    sender = AsyncMock(spec=BroadcastSender)
    sender.send.return_value = True
    result = await SendBroadcast(UsersQuery(UserRepository(session))).execute("All users", sender)
    recipient_ids = [delivery.args[0] for delivery in sender.send.await_args_list]

    assert {950_001, 950_002}.issubset(set(recipient_ids))
    assert result == BroadcastResult(sent=len(recipient_ids), total=len(recipient_ids))


@pytest.mark.parametrize("outcomes", [[], [True, True], [True, False, True]])
async def test_application_preserves_order_body_and_counts_failed_deliveries(outcomes):
    users = AsyncMock(spec=UsersQuery)
    users.get_all_ids.return_value = list(range(len(outcomes)))
    sender = AsyncMock(spec=BroadcastSender)
    sender.send.side_effect = outcomes
    body = "  <raw> & body\n "

    result = await SendBroadcast(users).execute(body, sender)

    assert result == BroadcastResult(sent=sum(outcomes), total=len(outcomes))
    assert sender.send.await_args_list == [call(user_id, body) for user_id in range(len(outcomes))]
    users.get_all_ids.assert_awaited_once()


async def test_application_propagates_unexpected_sender_failure_and_stops_delivery():
    users = AsyncMock(spec=UsersQuery)
    users.get_all_ids.return_value = [1, 2, 3]
    sender = AsyncMock(spec=BroadcastSender)
    sender.send.side_effect = [True, RuntimeError("unexpected delivery failure"), True]

    with pytest.raises(RuntimeError, match="unexpected delivery failure"):
        await SendBroadcast(users).execute("body", sender)

    assert sender.send.await_args_list == [call(1, "body"), call(2, "body")]


async def test_broadcast_use_case_retains_request_scope():
    class TestUsersProvider(Provider):
        @provide(scope=Scope.APP)
        def users(self) -> UsersQuery:
            return AsyncMock(spec=UsersQuery)

    async with make_async_container(BroadcastProvider(), TestUsersProvider()) as container:
        async with container() as request:
            first = await request.get(SendBroadcast)
            assert first is await request.get(SendBroadcast)
        async with container() as request:
            assert first is not await request.get(SendBroadcast)
