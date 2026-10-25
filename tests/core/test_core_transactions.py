import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Chat, ErrorEvent, Message, Update
from aiogram.types import User as TelegramUser
from dishka import FromDishka, Provider, Scope, make_async_container, provide
from dishka.integrations.aiogram import inject_router, setup_dishka
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manashelper.core.provider import CoreProvider
from manashelper.modules.users.infrastructure.user import User


def container_with_pool(pool):
    class SessionPool(Provider):
        @provide(scope=Scope.APP, override=True)
        def session_pool(self) -> async_sessionmaker[AsyncSession]:
            return pool

    return make_async_container(CoreProvider(), SessionPool())


@pytest.fixture
def resource():
    session = AsyncMock(spec=AsyncSession)
    session.__aenter__.return_value = session
    events = []
    session.commit.side_effect = lambda: events.append("commit")
    session.rollback.side_effect = lambda: events.append("rollback")
    session.__aexit__.side_effect = lambda *args: events.append("close")
    return session, Mock(return_value=session), events


@pytest.mark.parametrize("error", [RuntimeError("body failed"), asyncio.CancelledError("body cancelled")])
async def test_body_failure_rolls_back_before_close_and_preserves_original_error(resource, error):
    session, pool, events = resource
    async with container_with_pool(pool) as container:
        with pytest.raises(type(error)) as caught:
            async with container() as request:
                assert await request.get(AsyncSession) is session
                raise error
        assert caught.value is error
    assert events == ["rollback", "close"]
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    session.__aexit__.assert_awaited_once()


async def test_handled_error_inside_request_still_commits(resource):
    session, pool, events = resource
    async with container_with_pool(pool) as container, container() as request:
        await request.get(AsyncSession)
        try:
            raise RuntimeError("handled by application")
        except RuntimeError:
            pass
    assert events == ["commit", "close"]
    session.rollback.assert_not_awaited()


async def test_actual_task_cancellation_rolls_back_and_closes_session(resource):
    session, pool, events = resource
    ready = asyncio.Event()
    async with container_with_pool(pool) as container:

        async def operation():
            async with container() as request:
                await request.get(AsyncSession)
                ready.set()
                await asyncio.Future()

        task = asyncio.create_task(operation())
        try:
            await asyncio.wait_for(ready.wait(), timeout=2)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    assert events == ["rollback", "close"]
    session.commit.assert_not_awaited()


@pytest.mark.parametrize("error", [RuntimeError("commit failed"), asyncio.CancelledError("commit cancelled")])
async def test_commit_failure_rolls_back_once_and_closes(resource, error):
    session, pool, events = resource

    async def commit():
        events.append("commit")
        raise error

    session.commit.side_effect = commit
    async with container_with_pool(pool) as container:
        with pytest.raises(ExceptionGroup if isinstance(error, Exception) else asyncio.CancelledError) as caught:
            async with container() as request:
                await request.get(AsyncSession)
        if isinstance(error, Exception):
            assert caught.value.exceptions == (error,)
        else:
            assert caught.value is error
    assert events == ["commit", "rollback", "close"]
    session.rollback.assert_awaited_once()


async def test_rollback_failure_is_reported_once_and_session_still_closes(resource):
    session, pool, events = resource
    body_error, rollback_error = RuntimeError("body failed"), RuntimeError("rollback failed")

    async def rollback():
        events.append("rollback")
        raise rollback_error

    session.rollback.side_effect = rollback
    async with container_with_pool(pool) as container:
        with pytest.raises(ExceptionGroup) as caught:
            async with container() as request:
                await request.get(AsyncSession)
                raise body_error
        assert caught.value.exceptions == (rollback_error,)
        assert caught.value.__context__ is body_error
    assert events == ["rollback", "close"]
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


async def test_aiogram_error_handler_runs_after_request_rollback(resource):
    session, pool, events = resource
    error = RuntimeError("handler failed")
    dispatcher, router = Dispatcher(), Router()

    @router.message()
    async def failing_handler(message: Message, database: FromDishka[AsyncSession]) -> None:
        assert database is session
        events.append("handler")
        raise error

    @dispatcher.errors()
    async def error_handler(event: ErrorEvent) -> bool:
        assert event.exception is error
        events.append("error_handler")
        return True

    dispatcher.include_router(router)
    async with container_with_pool(pool) as container:
        setup_dishka(container, dispatcher)
        inject_router(dispatcher)
        async with Bot(token="123456789:test-token") as bot:
            await dispatcher.feed_update(
                bot,
                Update(
                    update_id=1,
                    message=Message(
                        message_id=1,
                        date=datetime.now(UTC),
                        chat=Chat(id=42, type="private"),
                        from_user=TelegramUser(id=42, is_bot=False, first_name="Fixture"),
                        text="fail",
                    ),
                ),
            )
    assert events == ["handler", "rollback", "close", "error_handler"]
    session.commit.assert_not_awaited()


@pytest.mark.parametrize("error", [RuntimeError("body failed"), asyncio.CancelledError("body cancelled")])
async def test_database_flushed_writes_are_rolled_back_without_losing_other_requests(engine, error):
    async with engine.connect() as connection:
        outer = await connection.begin()
        try:
            pool = async_sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
            async with container_with_pool(pool) as container:
                async with container() as request:
                    session = await request.get(AsyncSession)
                    session.add(User(id=-978201, full_name="Successful request"))
                with pytest.raises(type(error)) as caught:
                    async with container() as request:
                        session = await request.get(AsyncSession)
                        session.add(User(id=-978202, full_name="Failed request"))
                        await session.flush()
                        raise error
                assert caught.value is error
                assert await connection.scalar(select(User.id).where(User.id == -978202)) is None
                async with container() as request:
                    session = await request.get(AsyncSession)
                    session.add(User(id=-978203, full_name="Next request"))
                result = await connection.scalars(select(User.id).where(User.id.in_([-978201, -978202, -978203])))
                assert set(result) == {-978201, -978203}
        finally:
            await outer.rollback()


async def test_database_commit_error_rolls_back_savepoint_and_next_request_succeeds(engine):
    async with engine.connect() as connection:
        outer = await connection.begin()
        try:
            pool = async_sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
            async with container_with_pool(pool) as container:
                async with container() as request:
                    session = await request.get(AsyncSession)
                    session.add(User(id=-978204, full_name="Original"))
                with pytest.raises(ExceptionGroup) as caught:
                    async with container() as request:
                        session = await request.get(AsyncSession)
                        session.add(User(id=-978204, full_name="Duplicate"))
                assert isinstance(caught.value.exceptions[0], IntegrityError)
                assert await connection.scalar(select(User.full_name).where(User.id == -978204)) == "Original"
                async with container() as request:
                    session = await request.get(AsyncSession)
                    session.add(User(id=-978205, full_name="After failed commit"))
                assert await connection.scalar(select(User.id).where(User.id == -978205)) == -978205
        finally:
            await outer.rollback()
