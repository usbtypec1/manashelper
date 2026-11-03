import asyncio
import os
import sys
from textwrap import dedent


async def test_production_dispatcher_uses_the_unified_route_and_preserves_a_waiting_form(isolated_flow_pool):
    # Production routers attach once. A fresh process proves the actual composition without
    # mutating the module routers used by other isolated adapter tests.
    schema = isolated_flow_pool.kw["bind"].sync_engine.get_execution_options()["schema_translate_map"][None]
    script = dedent("""
        import asyncio
        from aiogram import Bot
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from manashelper.bootstrap import load_models
        from manashelper.core.config import get_settings
        from manashelper.core.database import create_engine
        from manashelper.platform.telegram.dispatcher import create_dispatcher
        from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
        from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession
        from tests.modules.ui_flows.telegram_factory import container_for, TelegramHarness
        import os

        async def check():
            load_models()
            settings = get_settings()
            engine = create_engine(settings).execution_options(
                schema_translate_map={None: os.environ['UI_INGRESS_TEST_SCHEMA']})
            pool = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with Bot(token='123456:synthetic-production-dispatcher') as bot, container_for(pool) as container:
                    await (await container.get(FlowTelegramCoordinator)).install_defaults(settings.admin_chat_id)
                    dispatcher = create_dispatcher(container)
                    harness = TelegramHarness(bot, dispatcher, settings.admin_chat_id)
                    bot.session.make_request = harness.respond
                    await harness.message('/start', 141000)
                    await harness.message('/start student_questions', 141001)
                    async with pool() as session:
                        before = await session.scalar(select(UiDialogSession).where(
                            UiDialogSession.status == 'waiting_button'))
                        assert before.flow_id == 'student_questions' and before.trigger_release == 1
                        identity, revision, answers = before.id, before.revision, dict(before.data)
                    await harness.message('/unknown_command', 141002)
                    async with pool() as session:
                        state = await session.get(UiDialogSession, identity)
                        assert state.revision == revision and state.data == answers
                    assert dispatcher.sub_routers[0].name == 'ui_ingress'
            finally:
                await engine.dispose()
        asyncio.run(check())
    """)
    environment = dict(os.environ, UI_INGRESS_TEST_SCHEMA=schema, MANASHELPER_ADMIN_CHAT_ID="991650")
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", script, env=environment, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, errors = await process.communicate()
    assert process.returncode == 0, errors.decode()
