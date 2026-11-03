import ssl
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from pathlib import Path

import httpx
from aiohttp import web
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manashelper.core.provider import CoreProvider
from manashelper.modules.student_questions.provider import StudentQuestionsProvider
from manashelper.modules.ui_flows.presentation.admin_provider import AdminUiFlowsProvider
from manashelper.modules.ui_flows.provider import UiFlowsProvider
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.i18n.provider import TextCatalogProvider
from manashelper.platform.web.auth import AdminAuthService
from manashelper.platform.web.provider import WebPlatformProvider


def certificate(directory: Path) -> tuple[Path, Path]:
    """Generate a loopback-only, short-lived certificate for real HTTPS test clients."""
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


@asynccontextmanager
async def aiohttp_client(app: web.Application) -> AsyncIterator[httpx.AsyncClient]:
    """Exercise aiohttp over TLS so Secure cookie behavior matches the real API."""
    with tempfile.TemporaryDirectory(prefix="ui-api-tls-") as directory:
        cert, key = certificate(Path(directory))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        runner = web.AppRunner(app, access_log=None)
        try:
            await runner.setup()
            await web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context).start()
            port = runner.addresses[0][1]
            async with httpx.AsyncClient(
                base_url=f"https://127.0.0.1:{port}", verify=False, headers={"Origin": "https://admin.test"}
            ) as client:
                yield client
        finally:
            await runner.cleanup()


def admin_container(pool):
    class Pool(Provider):
        @provide(scope=Scope.APP, override=True)
        def session_pool(self) -> async_sessionmaker[AsyncSession]:
            return pool

    return make_async_container(
        CoreProvider(),
        TextCatalogProvider(),
        StudentQuestionsProvider(),
        UsersProvider(),
        UiFlowsProvider(),
        WebPlatformProvider(),
        AdminUiFlowsProvider(),
        Pool(),
    )


@dataclass
class AdminHarness:
    client: httpx.AsyncClient
    container: AsyncContainer
    pool: async_sessionmaker[AsyncSession]
    app: web.Application
    user_id: int

    async def ticket(self):
        async with self.container() as request:
            return await (await request.get(AdminAuthService)).issue(self.user_id)

    async def login(self):
        response = await self.client.post("/admin/api/v1/auth/exchange", json={"ticket": await self.ticket()})
        assert response.status_code == 200, response.text
        self.client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        return response
