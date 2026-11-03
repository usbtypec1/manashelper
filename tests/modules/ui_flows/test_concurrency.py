import asyncio

import pytest
from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manashelper.core.provider import CoreProvider
from manashelper.modules.student_questions.orm import StudentQuestionsResponse
from manashelper.modules.student_questions.provider import StudentQuestionsProvider
from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiFlowEvent
from manashelper.modules.ui_flows.provider import UiFlowsProvider
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.i18n.provider import TextCatalogProvider
from tests.modules.ui_flows.factories import button, policy, publish_examples, runtime
from ui_flows.application.dialogs import DialogService
from ui_flows.application.policy import FlowPolicy
from ui_flows.domain.state import RuntimeUser
from ui_flows.errors import ActiveDialogError, StaleEventError

USER = RuntimeUser(991_402, 991_402)


async def setup_examples(pool):
    async with pool.begin() as session:
        session.add(User(id=USER.id, full_name="Concurrent flow", username=None))
        await session.flush()
        await publish_examples(runtime(session))


async def test_concurrent_first_start_creates_only_one_active_dialog(isolated_flow_pool):
    await setup_examples(isolated_flow_pool)

    async def start(update_id):
        try:
            async with isolated_flow_pool.begin() as session:
                return await runtime(session).dialogs.start("main_menu", USER, update_id)
        except ActiveDialogError as error:
            return error

    results = await asyncio.wait_for(asyncio.gather(start(1), start(2)), timeout=10)
    assert sum(isinstance(result, ActiveDialogError) for result in results) == 1
    async with isolated_flow_pool() as session:
        assert await session.scalar(select(func.count()).select_from(UiDialogSession)) == 1
        assert await session.scalar(select(func.count()).select_from(UiFlowEvent)) == 1


@pytest.mark.parametrize("same_update", [True, False])
async def test_concurrent_confirmation_writes_once(isolated_flow_pool, same_update):
    await setup_examples(isolated_flow_pool)
    async with isolated_flow_pool.begin() as session:
        dialogs = runtime(session).dialogs
        result = await dialogs.start("student_questions", USER, 10)
        result = await dialogs.handle(button(result.state, 11, "year_1"), USER)
        result = await dialogs.handle(button(result.state, 12, "no"), USER)
        state = result.state

    async def confirm(update_id):
        try:
            async with isolated_flow_pool.begin() as session:
                return await runtime(session).dialogs.handle(button(state, update_id, "yes"), USER)
        except StaleEventError as error:
            return error

    results = await asyncio.wait_for(asyncio.gather(confirm(13), confirm(13 if same_update else 14)), timeout=10)
    if same_update:
        assert {result.outcome for result in results} == {"advanced", "duplicate"}
    else:
        assert sum(isinstance(result, StaleEventError) for result in results) == 1
    async with isolated_flow_pool() as session:
        assert await session.scalar(select(func.count()).select_from(StudentQuestionsResponse)) == 1
        saved = await session.get(UiDialogSession, state.id)
        assert saved.status == "completed" and saved.revision == state.revision + 1
        assert await session.scalar(select(func.count()).select_from(UiFlowEvent)) == 4


async def test_new_container_restores_the_persisted_step_and_core_rolls_back_failure(isolated_flow_pool):
    await setup_examples(isolated_flow_pool)

    class PoolProvider(Provider):
        @provide(scope=Scope.APP, override=True)
        def pool(self) -> async_sessionmaker[AsyncSession]:
            return isolated_flow_pool

        @provide(scope=Scope.REQUEST, override=True)
        def flow_policy(self) -> FlowPolicy:
            return policy()

    def container():
        return make_async_container(
            CoreProvider(),
            TextCatalogProvider(),
            UsersProvider(),
            StudentQuestionsProvider(),
            UiFlowsProvider(),
            PoolProvider(),
        )

    async with container() as first, first() as request:
        dialogs = await request.get(DialogService)
        result = await dialogs.start("student_questions", USER, 20)
        result = await dialogs.handle(button(result.state, 21, "year_2"), USER)
        state = result.state
    async with container() as second:
        async with second() as request:
            dialogs = await request.get(DialogService)
            assert await dialogs.get(state.id, USER) == state
        with pytest.raises(RuntimeError, match="request failed"):
            async with second() as request:
                dialogs = await request.get(DialogService)
                await dialogs.handle(button(state, 22, "no"), USER)
                raise RuntimeError("request failed")
        async with second() as request:
            dialogs = await request.get(DialogService)
            assert await dialogs.get(state.id, USER) == state
            assert (await dialogs.handle(button(state, 22, "no"), USER)).state.node_id == "beta"
