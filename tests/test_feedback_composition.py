import subprocess
import sys
from textwrap import dedent
from unittest.mock import AsyncMock, Mock

import pytest
from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manashelper.db.base import Base
from manashelper.db.models import FeedbackMessage as RegisteredFeedbackMessage
from manashelper.di import AppProvider, RequestProvider
from manashelper.modules.feedback.orm import FeedbackMessage
from manashelper.modules.feedback.provider import FeedbackProvider
from manashelper.modules.feedback.service import FeedbackService


async def test_feedback_request_scope_preserves_existing_transaction_finalization():
    sessions = [AsyncMock(spec=AsyncSession) for _ in range(3)]
    for session in sessions:
        session.__aenter__.return_value = session
    pool = Mock(side_effect=sessions)

    class TestSessionProvider(Provider):
        @provide(scope=Scope.APP, override=True)
        def session_pool(self) -> async_sessionmaker[AsyncSession]:
            return pool

    async with make_async_container(
        AppProvider(), RequestProvider(), FeedbackProvider(), TestSessionProvider()
    ) as container:
        async with container() as request:
            service = await request.get(FeedbackService)
            assert service is await request.get(FeedbackService)
            summary = await service.submit(941_002, "Persist through the request session")
            row = sessions[0].add.call_args.args[0]
            assert isinstance(row, FeedbackMessage)
            assert (row.id, row.user_id, row.body) == (summary.id, summary.user_id, summary.body)

        sessions[0].commit.assert_awaited_once()
        sessions[0].rollback.assert_not_awaited()
        sessions[0].__aexit__.assert_awaited_once()

        with pytest.raises(RuntimeError, match="rollback requested"):
            async with container() as request:
                other_service = await request.get(FeedbackService)
                assert other_service is not service
                await other_service.submit(941_003, "Roll back this request")
                raise RuntimeError("rollback requested")

        # Existing behavior: Dishka sends the body exception as the yield value.
        # RequestProvider ignores that value and commits. Fix separately from relocation.
        sessions[1].commit.assert_awaited_once()
        sessions[1].rollback.assert_not_awaited()
        sessions[1].__aexit__.assert_awaited_once()

        sessions[2].commit.side_effect = RuntimeError("commit failed")
        with pytest.raises(ExceptionGroup) as errors:
            async with container() as request:
                await request.get(FeedbackService)
        assert "commit failed" in str(errors.value.exceptions[0])
        sessions[2].commit.assert_awaited_once()
        sessions[2].rollback.assert_awaited_once()
        sessions[2].__aexit__.assert_awaited_once()


def test_root_composition_keeps_feedback_in_dispatcher_and_orm_registry():
    # Production routers are singletons: attach/inject them in an isolated process.
    script = dedent("""\
        import asyncio
        from dishka import make_async_container
        from manashelper.bot.dispatcher import create_dispatcher
        from manashelper.di import AppProvider, RequestProvider
        from manashelper.modules.advertisements.provider import AdvertisementsProvider
        from manashelper.modules.feedback.provider import FeedbackProvider

        async def check():
            async with make_async_container(
                AppProvider(), RequestProvider(), FeedbackProvider(), AdvertisementsProvider()
            ) as container:
                dispatcher = create_dispatcher(container)
                names = [router.name for router in dispatcher.sub_routers]
                assert names.count("feedback") == 1
                assert names.index("student_questions") < names.index("advertisement_contact")
                assert names.index("advertisement_contact") < names.index("start")

        asyncio.run(check())
    """)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    assert RegisteredFeedbackMessage is FeedbackMessage
    assert Base.metadata.tables["feedback_messages"] is FeedbackMessage.__table__
