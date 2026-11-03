import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manashelper.modules.ui_flows.demo import demo_document
from manashelper.platform.web.application import create_admin_app
from manashelper.platform.web.auth import COOKIE_NAME, AdminAuthService, token_digest
from manashelper.platform.web.keys import SETTINGS_KEY
from manashelper.platform.web.orm import AdminWebSession
from tests.modules.ui_flows.admin_factory import admin_container, aiohttp_client
from tests.modules.ui_flows.webapp_factory import signed_init_data

BASE = "/admin/api/v1"


def init_data(api, **kwargs):
    return signed_init_data(api.app[SETTINGS_KEY].telegram_bot_token, api.user_id, **kwargs)


async def bearer_login(api):
    response = await api.client.post(BASE + "/auth/telegram", json={"init_data": init_data(api)})
    assert response.status_code == 200, response.text
    api.client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    return response


async def test_miniapp_exchange_stores_only_namespaced_digest_and_expires_in_eight_hours(admin_api):
    api = admin_api
    before = datetime.now(UTC)
    response = await bearer_login(api)
    body = response.json()
    assert set(body) == {"user_id", "expires_at", "access_token"}
    assert body["user_id"] == api.user_id
    assert "set-cookie" not in response.headers
    expires_at = datetime.fromisoformat(body["expires_at"])
    assert timedelta(hours=8, seconds=-3) <= expires_at - before <= timedelta(hours=8, seconds=3)
    assert api.client.cookies.get(COOKIE_NAME) is None
    async with api.pool() as session:
        row = await session.scalar(select(AdminWebSession))
        assert row.digest == token_digest("miniapp:" + body["access_token"])
        assert row.digest != token_digest(body["access_token"])
        assert row.expires_at == expires_at
    current = await api.client.get(BASE + "/auth/session")
    assert current.status_code == 200
    assert current.json()["user_id"] == api.user_id and current.json()["csrf_token"] == ""


async def test_miniapp_bearer_mutations_require_origin_but_no_csrf(admin_api):
    api = admin_api
    await bearer_login(api)
    document = demo_document().model_dump(mode="json")
    response = await api.client.post(BASE + "/flows", json={"document": document})
    assert response.status_code == 201
    document["id"] = "wrong_origin"
    rejected = await api.client.post(
        BASE + "/flows", json={"document": document}, headers={"Origin": "https://wrong.test"}
    )
    assert rejected.status_code == 403
    api.client.headers.pop("Origin")
    rejected = await api.client.post(BASE + "/flows", json={"document": document})
    assert rejected.status_code == 403


@pytest.mark.parametrize("kind", ["malformed", "nonadmin", "stale", "future", "tampered", "duplicate", "invalid_user"])
async def test_untrusted_init_data_is_rejected_without_echo_or_session(admin_api, kind):
    api = admin_api
    token = api.app[SETTINGS_KEY].telegram_bot_token
    now = int(time.time())
    raw = init_data(api)
    if kind == "malformed":
        raw = "private-init-data-that-must-not-be-echoed"
    elif kind == "nonadmin":
        raw = signed_init_data(token, api.user_id + 1)
    elif kind == "stale":
        raw = init_data(api, auth_date=now - 301)
    elif kind == "future":
        raw = init_data(api, auth_date=now + 3600)
    elif kind == "tampered":
        values = dict(parse_qsl(raw))
        values["query_id"] = "tampered-without-resigning"
        raw = urlencode(values)
    elif kind == "duplicate":
        raw += "&auth_date=" + str(now)
    elif kind == "invalid_user":
        raw = init_data(api, fields={"user": "private-invalid-json-user"})
    response = await api.client.post(BASE + "/auth/telegram", json={"init_data": raw})
    assert response.status_code == 401
    assert raw not in response.text and token not in response.text
    assert "set-cookie" not in response.headers
    async with api.pool() as session:
        assert await session.scalar(select(func.count()).select_from(AdminWebSession)) == 0


async def test_init_data_schema_errors_do_not_echo_input(admin_api):
    raw = init_data(admin_api)
    response = await admin_api.client.post(BASE + "/auth/telegram", json={"init_data": raw, "extra": raw})
    assert response.status_code == 422
    assert raw not in response.text and "set-cookie" not in response.headers


async def test_sixth_valid_exchange_in_one_minute_is_rate_limited(admin_api):
    api = admin_api
    for index in range(5):
        raw = init_data(api, fields={"query_id": f"exchange-{index}"})
        response = await api.client.post(BASE + "/auth/telegram", json={"init_data": raw})
        assert response.status_code == 200
    response = await api.client.post(BASE + "/auth/telegram", json={"init_data": init_data(api)})
    assert response.status_code == 429
    assert "access_token" not in response.json()
    async with api.pool() as session:
        assert await session.scalar(select(func.count()).select_from(AdminWebSession)) == 5


async def test_cookie_and_bearer_credentials_are_not_interchangeable(admin_api):
    api = admin_api
    bearer = (await bearer_login(api)).json()["access_token"]
    api.client.headers.pop("Authorization")
    api.client.cookies.set(COOKIE_NAME, bearer, path="/admin")
    assert (await api.client.get(BASE + "/auth/session")).status_code == 401
    api.client.cookies.clear()
    api.client.cookies.set(COOKIE_NAME, "miniapp:" + bearer, path="/admin")
    assert (await api.client.get(BASE + "/auth/session")).status_code == 401
    api.client.cookies.clear()
    await api.login()
    cookie = api.client.cookies[COOKIE_NAME]
    api.client.headers["Authorization"] = "Bearer " + cookie
    assert (await api.client.get(BASE + "/auth/session")).status_code == 401
    api.client.headers["Authorization"] = "Bearer " + bearer
    assert (await api.client.get(BASE + "/auth/session")).status_code == 200


async def test_bearer_logout_and_expiry_revoke_access(admin_api):
    api = admin_api
    await bearer_login(api)
    response = await api.client.post(BASE + "/auth/logout")
    assert response.status_code == 204 and response.content == b""
    assert (await api.client.get(BASE + "/auth/session")).status_code == 401
    await bearer_login(api)
    async with api.pool.begin() as session:
        await session.execute(update(AdminWebSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    assert (await api.client.get(BASE + "/auth/session")).status_code == 401


async def test_miniapp_session_repr_hides_access_token(admin_api):
    raw = init_data(admin_api)
    async with admin_api.container() as request:
        login = await (await request.get(AdminAuthService)).exchange_telegram(raw)
        assert login.access_token not in repr(login)
        assert raw not in repr(login)


async def test_commit_failure_returns_no_bearer_and_rolls_back_session(admin_api):
    api = admin_api

    class FailSessionCommit(AsyncSession):
        async def commit(self):
            if await self.scalar(select(AdminWebSession)) is not None:
                raise RuntimeError("synthetic Mini App commit failure")
            await super().commit()

    pool = async_sessionmaker(api.pool.kw["bind"], class_=FailSessionCommit, expire_on_commit=False)
    async with admin_container(pool) as container:
        app = create_admin_app(api.app[SETTINGS_KEY], container)
        async with aiohttp_client(app) as client:
            response = await client.post(BASE + "/auth/telegram", json={"init_data": init_data(api)})
            assert response.status_code == 500 and "access_token" not in response.json()
            assert "set-cookie" not in response.headers
    async with api.pool() as session:
        assert await session.scalar(select(func.count()).select_from(AdminWebSession)) == 0
    assert (await api.client.post(BASE + "/auth/telegram", json={"init_data": init_data(api)})).status_code == 200
