import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent, Update
from aiohttp.test_utils import TestClient, TestServer
from pydantic import HttpUrl, SecretStr

from manashelper.core.config import Settings
from manashelper.platform.telegram.dispatcher import on_error
from manashelper.platform.web.application import create_admin_app
from manashelper.platform.web.webhook import install_webhook

SECRET = "synthetic-webhook-secret"
HEADERS = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
MESSAGE = {
    "update_id": 934001,
    "message": {
        "message_id": 1,
        "date": 0,
        "chat": {"id": 123, "type": "private"},
        "from": {"id": 123, "is_bot": False, "first_name": "Student"},
        "text": "/start",
    },
}
CALLBACK = {
    "update_id": 934002,
    "callback_query": {
        "id": "synthetic-callback",
        "from": {"id": 123, "is_bot": False, "first_name": "Student"},
        "chat_instance": "synthetic-chat",
        "data": "uf:opaque:0",
    },
}


@pytest_asyncio.fixture
async def webhook(tmp_path):
    settings = Settings.model_construct(
        telegram_bot_token="123456:development-placeholder",
        admin_chat_id=123,
        admin_web_origin=HttpUrl("https://admin.test"),
        admin_web_signing_key=SecretStr("synthetic-admin-signing-key-only-for-tests"),
        telegram_webhook_secret=SecretStr(SECRET),
    )
    bot = Bot(token=settings.telegram_bot_token)
    dispatch = SimpleNamespace(feed_update=AsyncMock())
    app = create_admin_app(settings, SimpleNamespace(), ui_directory=tmp_path / "unbuilt")
    install_webhook(app, bot, dispatch, settings)
    try:
        async with TestClient(TestServer(app)) as client:
            yield SimpleNamespace(client=client, dispatch=dispatch, bot=bot)
    finally:
        await bot.session.close()


@pytest.mark.parametrize("payload", [MESSAGE, CALLBACK])
async def test_authenticated_webhook_dispatches_supported_update_without_cookie_or_csrf(webhook, payload):
    response = await webhook.client.post("/telegram/webhook", json=payload, headers=HEADERS)
    assert response.status == 200
    webhook.dispatch.feed_update.assert_awaited_once()
    args, kwargs = webhook.dispatch.feed_update.await_args
    assert args[0] is webhook.bot
    assert isinstance(args[1], Update) and args[1].update_id == payload["update_id"]
    assert kwargs == {"webhook": True}
    assert "Set-Cookie" not in response.headers


@pytest.mark.parametrize("secret", [None, "", "wrong-secret"])
async def test_webhook_rejects_missing_or_incorrect_secret_before_dispatch(webhook, secret):
    headers = {} if secret is None else {"X-Telegram-Bot-Api-Secret-Token": secret}
    response = await webhook.client.post("/telegram/webhook", json=MESSAGE, headers=headers)
    assert response.status == 403
    webhook.dispatch.feed_update.assert_not_awaited()
    assert SECRET not in await response.text()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        {"update_id": 934003},
        {"update_id": 934004, "message": {"text": "malformed"}},
        {"update_id": 934005, "edited_message": MESSAGE["message"]},
        {
            "update_id": 934006,
            "inline_query": {
                "id": "unsupported-inline",
                "from": {"id": 123, "is_bot": False, "first_name": "Student"},
                "query": "private query",
                "offset": "",
            },
        },
    ],
)
async def test_malformed_or_unsupported_updates_are_rejected_without_dispatch(webhook, payload):
    response = await webhook.client.post("/telegram/webhook", json=payload, headers=HEADERS)
    assert response.status == 400
    webhook.dispatch.feed_update.assert_not_awaited()


async def test_invalid_json_and_oversized_body_are_rejected_without_dispatch(webhook):
    headers = {**HEADERS, "Content-Type": "application/json"}
    invalid = await webhook.client.post("/telegram/webhook", data=b"{", headers=headers)
    assert invalid.status == 400
    oversized = await webhook.client.post("/telegram/webhook", data=b"x" * (1024 * 1024 + 1), headers=headers)
    assert oversized.status == 413
    webhook.dispatch.feed_update.assert_not_awaited()


async def test_webhook_response_waits_for_processing_instead_of_acknowledging_background_work(webhook):
    started, finish = asyncio.Event(), asyncio.Event()

    async def process(*args, **kwargs):
        started.set()
        await finish.wait()

    webhook.dispatch.feed_update.side_effect = process
    pending = asyncio.create_task(webhook.client.post("/telegram/webhook", json=MESSAGE, headers=HEADERS))
    try:
        await asyncio.wait_for(started.wait(), 2)
        assert not pending.done()
        finish.set()
        response = await asyncio.wait_for(pending, 2)
        assert response.status == 200
    finally:
        finish.set()
        if not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)


async def test_dispatch_failure_returns_safe_500_instead_of_acknowledging_commit_failure(webhook):
    webhook.dispatch.feed_update.side_effect = RuntimeError("synthetic commit failure with private input")
    response = await webhook.client.post("/telegram/webhook", json=MESSAGE, headers=HEADERS)
    assert response.status == 500
    assert "private input" not in await response.text()
    assert "Set-Cookie" not in response.headers


async def test_aiogram_error_handler_propagates_webhook_failure_and_keeps_polling_behavior():
    event = ErrorEvent(update=Update.model_validate(MESSAGE), exception=RuntimeError("synthetic commit failure"))
    assert await on_error(event) is None
    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        await on_error(event, webhook=True)


async def test_real_dispatcher_error_boundary_does_not_turn_webhook_failure_into_success(webhook):
    dispatch = Dispatcher()

    async def fail(message):
        raise RuntimeError("synthetic handler commit failure")

    dispatch.message.register(fail)
    dispatch.errors.register(on_error)
    webhook.dispatch.feed_update.side_effect = dispatch.feed_update
    response = await webhook.client.post("/telegram/webhook", json=MESSAGE, headers=HEADERS)
    assert response.status == 500
    await dispatch.storage.close()
