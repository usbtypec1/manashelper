"""Loopback-only browser-test fixture with a disposable PostgreSQL schema and synthetic identity."""

import asyncio
import os
import signal
import ssl
import tempfile
from pathlib import Path
from uuid import uuid4

from aiohttp import web
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from common.database import Base
from manashelper.bootstrap import load_models
from manashelper.core.config import get_settings
from manashelper.modules.student_questions.orm import StudentQuestionsResponse
from manashelper.modules.ui_flows.infrastructure.orm import (
    UiDialogSession,
    UiFlow,
    UiFlowEvent,
    UiFlowRollout,
    UiFlowVersion,
    UiScreenDelivery,
    UiUserLocation,
    UiUserTransition,
)
from manashelper.modules.ui_flows.infrastructure.trigger_orm import UiIngressReceipt, UiTriggerRelease, UiTriggerState
from manashelper.modules.users.infrastructure.user import User
from manashelper.platform.i18n.orm import TextCatalogRelease, TextCatalogState
from manashelper.platform.i18n.repository import initialize_catalog
from manashelper.platform.i18n.request import catalog_request
from manashelper.platform.web.application import create_admin_app
from manashelper.platform.web.auth import AdminAuthService
from manashelper.platform.web.orm import AdminLoginTicket, AdminWebSession
from tests.modules.ui_flows.admin_factory import admin_container, certificate
from tests.modules.ui_flows.webapp_factory import signed_init_data

ADMIN_ID = 991_470


async def main() -> None:
    # Never use a remote DB or the operator's real admin identity in browser checks.
    port = int(os.environ.get("UI_EDITOR_TEST_PORT", "8091"))
    os.environ.update(
        {
            "MANASHELPER_DATASOURCE_HOST": "localhost",
            "MANASHELPER_ADMIN_CHAT_ID": str(ADMIN_ID),
            "MANASHELPER_ADMIN_WEB_ORIGIN": f"https://127.0.0.1:{port}",
            "MANASHELPER_ADMIN_WEB_SIGNING_KEY": "synthetic-editor-e2e-key-never-for-production",
            "MANASHELPER_ADVERTISEMENT_CHANNEL_ID": "-1000000000000",
            "MANASHELPER_ADVERTISEMENT_CHANNEL_LINK": "https://t.me/example",
            "MANASHELPER_MODERATION_CHAT_ID": "-1000000000001",
        }
    )
    get_settings.cache_clear()
    settings = get_settings()
    load_models()
    engine = create_async_engine(settings.database_url)
    schema = "ui_editor_e2e_" + uuid4().hex
    async with engine.begin() as connection:
        await connection.execute(CreateSchema(schema))
    scoped_engine = engine.execution_options(schema_translate_map={None: schema})
    pool = async_sessionmaker(scoped_engine, expire_on_commit=False)
    try:
        async with scoped_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with pool.begin() as session:
            await initialize_catalog(session)
            session.add(User(id=ADMIN_ID, full_name="Editor test admin", locale="ru"))
        async with admin_container(pool) as container:
            app = create_admin_app(settings, container)
            routes = web.RouteTableDef()
            stopped = asyncio.Event()

            @routes.get("/__test__/ticket")
            async def ticket(_request: web.Request) -> web.Response:
                async with catalog_request(container) as request:
                    raw = await (await request.get(AdminAuthService)).issue(ADMIN_ID)
                return web.json_response({"ticket": raw})

            @routes.get("/__test__/init-data")
            async def init_data(_request: web.Request) -> web.Response:
                return web.json_response({"init_data": signed_init_data(settings.telegram_bot_token, ADMIN_ID)})

            @routes.post("/__test__/reset")
            async def reset(_request: web.Request) -> web.Response:
                async with pool.begin() as session:
                    await session.execute(update(UiFlow).values(published_version=None))
                    for model in (
                        UiFlowRollout,
                        UiUserLocation,
                        UiUserTransition,
                        UiScreenDelivery,
                        UiFlowEvent,
                        UiDialogSession,
                        UiFlowVersion,
                        UiFlow,
                        StudentQuestionsResponse,
                        AdminLoginTicket,
                        AdminWebSession,
                        UiIngressReceipt,
                        UiTriggerState,
                        UiTriggerRelease,
                        TextCatalogState,
                        TextCatalogRelease,
                    ):
                        await session.execute(delete(model))
                    await initialize_catalog(session)
                return web.json_response({"ok": True})

            @routes.post("/__test__/triggers/start")
            async def start_triggers(_request: web.Request) -> web.Response:
                from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator

                await (await container.get(FlowTelegramCoordinator)).install_defaults(ADMIN_ID)
                return web.json_response({"ok": True})

            @routes.post("/__test__/monitor/start")
            async def start_monitor(_request: web.Request) -> web.Response:
                from manashelper.modules.ui_flows.demo import demo_document
                from ui_flows.application.dialogs import DialogService
                from ui_flows.application.flows import FlowService
                from ui_flows.domain.state import RuntimeUser

                async with catalog_request(container) as request:
                    flows = await request.get(FlowService)
                    document = demo_document().model_copy(update={"id": "monitor_form"})
                    await flows.create(document)
                    await flows.publish(document.id, 0, ADMIN_ID)
                    await (await request.get(DialogService)).start(document.id, RuntimeUser(ADMIN_ID, ADMIN_ID), 900000)
                return web.json_response({"ok": True})

            @routes.post("/__test__/monitor/advance")
            async def advance_monitor(_request: web.Request) -> web.Response:
                from tests.modules.ui_flows.factories import button
                from ui_flows.application.dialogs import DialogService
                from ui_flows.domain.state import RuntimeUser

                async with catalog_request(container) as request:
                    dialogs = await request.get(DialogService)
                    user = RuntimeUser(ADMIN_ID, ADMIN_ID)
                    await dialogs.handle(button(await dialogs.active(user), 900001, "form"), user)
                return web.json_response({"ok": True})

            @routes.post("/__test__/monitor/legacy")
            async def legacy_monitor(_request: web.Request) -> web.Response:
                from ui_flows.application.dialogs import DialogService
                from ui_flows.application.locations import LocationService
                from ui_flows.domain.state import RuntimeUser

                async with catalog_request(container) as request:
                    await (await request.get(DialogService)).cancel_active(RuntimeUser(ADMIN_ID, ADMIN_ID), 900002)
                    await (await request.get(LocationService)).observe(
                        ADMIN_ID, ADMIN_ID, 900003, "obis", "ObisCredentialsForm:password"
                    )
                return web.json_response({"ok": True})

            @routes.post("/__test__/monitor/restart")
            async def restart_monitor(_request: web.Request) -> web.Response:
                from ui_flows.application.locations import LocationService

                async with catalog_request(container) as request:
                    await (await request.get(LocationService)).forget_legacy()
                return web.json_response({"ok": True})

            @routes.post("/__test__/cleanup")
            async def cleanup(_request: web.Request) -> web.Response:
                stopped.set()
                return web.json_response({"ok": True})

            app.add_routes(routes)
            with tempfile.TemporaryDirectory(prefix="ui-editor-tls-") as directory:
                cert, key = certificate(Path(directory))
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(cert, key)
                runner = web.AppRunner(app, access_log=None)
                loop = asyncio.get_running_loop()

                def request_stop(_signal, _frame):
                    loop.call_soon_threadsafe(stopped.set)

                previous_signals = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGINT, signal.SIGTERM)}
                try:
                    await runner.setup()
                    await web.TCPSite(runner, "127.0.0.1", port, ssl_context=context).start()
                    await stopped.wait()
                finally:
                    await runner.cleanup()
                    for sig, handler in previous_signals.items():
                        signal.signal(sig, handler)
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
