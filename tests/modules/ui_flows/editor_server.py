"""Loopback-only browser-test fixture with a disposable PostgreSQL schema and synthetic identity."""

import asyncio
import os
import ssl
import tempfile
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from pathlib import Path
from uuid import uuid4

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.responses import JSONResponse
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from common.database import Base
from manashelper.admin_main import create_app
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
from manashelper.modules.users.infrastructure.user import User
from manashelper.platform.web.auth import AdminAuthService
from manashelper.platform.web.orm import AdminLoginTicket, AdminWebSession
from tests.modules.ui_flows.admin_factory import admin_container

ADMIN_ID = 991_470


def certificate(directory: Path) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip_address("127.0.0.1"))]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / "cert.pem", directory / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    return cert_path, key_path


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
            session.add(User(id=ADMIN_ID, full_name="Editor test admin", locale="ru"))
        async with admin_container(pool) as container:
            app = create_app(settings, container)

            @app.get("/__test__/ticket", include_in_schema=False)
            async def ticket() -> JSONResponse:
                async with container() as request:
                    raw = await (await request.get(AdminAuthService)).issue(ADMIN_ID)
                return JSONResponse({"ticket": raw})

            @app.post("/__test__/reset", include_in_schema=False)
            async def reset() -> JSONResponse:
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
                    ):
                        await session.execute(delete(model))
                return JSONResponse({"ok": True})

            @app.post("/__test__/monitor/start", include_in_schema=False)
            async def start_monitor() -> JSONResponse:
                from manashelper.modules.ui_flows.demo import demo_document
                from ui_flows.application.dialogs import DialogService
                from ui_flows.application.flows import FlowService
                from ui_flows.domain.state import RuntimeUser

                async with container() as request:
                    flows = await request.get(FlowService)
                    document = demo_document().model_copy(update={"id": "monitor_form"})
                    await flows.create(document)
                    await flows.publish(document.id, 0, ADMIN_ID)
                    await (await request.get(DialogService)).start(document.id, RuntimeUser(ADMIN_ID, ADMIN_ID), 900000)
                return JSONResponse({"ok": True})

            @app.post("/__test__/monitor/advance", include_in_schema=False)
            async def advance_monitor() -> JSONResponse:
                from tests.modules.ui_flows.factories import button
                from ui_flows.application.dialogs import DialogService
                from ui_flows.domain.state import RuntimeUser

                async with container() as request:
                    dialogs = await request.get(DialogService)
                    user = RuntimeUser(ADMIN_ID, ADMIN_ID)
                    await dialogs.handle(button(await dialogs.active(user), 900001, "form"), user)
                return JSONResponse({"ok": True})

            @app.post("/__test__/monitor/legacy", include_in_schema=False)
            async def legacy_monitor() -> JSONResponse:
                from ui_flows.application.dialogs import DialogService
                from ui_flows.application.locations import LocationService
                from ui_flows.domain.state import RuntimeUser

                async with container() as request:
                    await (await request.get(DialogService)).cancel_active(RuntimeUser(ADMIN_ID, ADMIN_ID), 900002)
                    await (await request.get(LocationService)).observe(
                        ADMIN_ID, ADMIN_ID, 900003, "obis", "ObisCredentialsForm:password"
                    )
                return JSONResponse({"ok": True})

            @app.post("/__test__/monitor/restart", include_in_schema=False)
            async def restart_monitor() -> JSONResponse:
                from ui_flows.application.locations import LocationService

                async with container() as request:
                    await (await request.get(LocationService)).forget_legacy()
                return JSONResponse({"ok": True})

            @app.post("/__test__/cleanup", include_in_schema=False)
            async def cleanup() -> JSONResponse:
                async with engine.begin() as connection:
                    await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
                return JSONResponse({"ok": True})

            with tempfile.TemporaryDirectory(prefix="ui-editor-tls-") as directory:
                cert, key = certificate(Path(directory))
                server = uvicorn.Server(
                    uvicorn.Config(
                        app,
                        host="127.0.0.1",
                        port=port,
                        ssl_certfile=str(cert),
                        ssl_keyfile=str(key),
                        ssl_version=ssl.PROTOCOL_TLS_SERVER,
                        access_log=False,
                        log_level="warning",
                    )
                )
                await server.serve()
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
