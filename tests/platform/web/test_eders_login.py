import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pydantic import SecretStr

from manashelper.core.config import Settings
from manashelper.modules.eders.application.browser_login import EdersLoginTokens, browser_login_marker
from manashelper.modules.eders.application.use_cases.redeem_eders_login_link import RedeemEdersLoginLinkUseCase
from manashelper.modules.eders.presentation.browser_login import register_browser_login_routes
from manashelper.modules.obis.application.models import StoredCredentials
from manashelper.modules.obis.errors import ObisManualLoginRequiredError, ObisRetryLaterError
from manashelper.platform.web.server import create_web_app

ORIGIN = "https://bot.example.com"
PATH = "/api/eders/browser-login?lang=ru"
DESTINATION = "https://eders.manas.edu.kg/auth/userkey/login.php?key=fake-key"


@asynccontextmanager
async def application(error=None, public_url=ORIGIN):
    credentials = StoredCredentials("student", "cipher")
    store = AsyncMock(get_by_user_id=AsyncMock(return_value=credentials))
    tokens = EdersLoginTokens()
    token = tokens.issue(42, browser_login_marker(credentials))
    upstream = AsyncMock(create_browser_login_url=AsyncMock(return_value=DESTINATION))
    exits = []

    async def with_session(user_id, operation):
        await asyncio.sleep(0)
        if error:
            raise error
        return await operation({"obis": "private-session"})

    redeem = RedeemEdersLoginLinkUseCase(store, tokens, upstream, AsyncMock(with_session=with_session))

    @asynccontextmanager
    async def scope():
        yield SimpleNamespace(get=AsyncMock(return_value=redeem))
        exits.append("committed")

    config = Settings.model_construct(public_url=public_url, eders_password=SecretStr("fake"))
    async with Bot("123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi") as bot:
        app = create_web_app(bot, Dispatcher(), scope, config)
        async with TestClient(TestServer(app)) as client:
            yield client, token, upstream, exits


async def test_get_and_head_previews_do_not_consume_then_post_redirects_without_shared_cookies():
    async with application() as (client, token, upstream, exits):
        for method in ("GET", "HEAD"):
            response = await client.request(method, PATH)
            assert response.status == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert response.headers["Referrer-Policy"] == "same-origin"
            assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        page = await (await client.get(PATH)).text()
        assert "location.hash" in page and "history.replaceState" in page
        assert token not in page
        upstream.create_browser_login_url.assert_not_awaited()
        response = await client.post(PATH, data={"token": token}, headers={"Origin": ORIGIN}, allow_redirects=False)
        assert response.status == 303 and response.headers["Location"] == DESTINATION
        assert "Set-Cookie" not in response.headers
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert exits == ["committed"]
        replay = await client.post(PATH, data={"token": token}, headers={"Origin": ORIGIN})
        assert replay.status == 410
        upstream.create_browser_login_url.assert_awaited_once_with({"obis": "private-session"})


async def test_concurrent_redemption_performs_only_one_upstream_login():
    async with application() as (client, token, upstream, _):
        responses = await asyncio.gather(
            *(
                client.post(PATH, data={"token": token}, headers={"Origin": ORIGIN}, allow_redirects=False)
                for _ in range(2)
            )
        )
        assert sorted(response.status for response in responses) == [303, 410]
        upstream.create_browser_login_url.assert_awaited_once()


async def test_browser_origin_accepts_canonical_host_and_default_https_port():
    async with application(public_url="https://BOT.example.com:443") as (client, token, _, _):
        response = await client.post(PATH, data={"token": token}, headers={"Origin": ORIGIN}, allow_redirects=False)
        assert response.status == 303


@pytest.mark.parametrize("origin", [None, "null", "https://evil.example"])
async def test_wrong_origin_does_not_spend_grant(origin):
    async with application() as (client, token, upstream, _):
        headers = {"Origin": origin} if origin else {}
        rejected = await client.post(PATH, data={"token": token}, headers=headers)
        assert rejected.status == 403
        upstream.create_browser_login_url.assert_not_awaited()
        accepted = await client.post(PATH, data={"token": token}, headers={"Origin": ORIGIN}, allow_redirects=False)
        assert accepted.status == 303


@pytest.mark.parametrize("error,status", [(ObisRetryLaterError, 503), (ObisManualLoginRequiredError, 409)])
async def test_expected_auth_failures_finish_scope_normally_and_spend_grant(error, status):
    async with application(error) as (client, token, upstream, exits):
        failed = await client.post(PATH, data={"token": token}, headers={"Origin": ORIGIN})
        assert failed.status == status and exits == ["committed"]
        assert failed.headers["Cache-Control"] == "no-store"
        assert "private-session" not in await failed.text()
        assert (await client.post(PATH, data={"token": token}, headers={"Origin": ORIGIN})).status == 410
        upstream.create_browser_login_url.assert_not_awaited()


@pytest.mark.parametrize("password,public_url", [(None, ORIGIN), (SecretStr(""), ORIGIN), (SecretStr("fake"), None)])
async def test_disabled_or_polling_has_no_login_endpoint(password, public_url):
    app = web.Application()
    config = Settings.model_construct(public_url=public_url, eders_password=password)
    register_browser_login_routes(app, AsyncMock(), config)
    async with TestClient(TestServer(app)) as client:
        assert (await client.get(PATH)).status == 404
