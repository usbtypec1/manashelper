import asyncio
import json
import os
from contextlib import asynccontextmanager

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import Message
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from dishka import FromDishka, make_async_container
from dishka.integrations.aiogram import inject_router, setup_dishka
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.core.config import get_settings
from manashelper.core.provider import CoreProvider
from manashelper.modules.gamification.application.use_cases.record_activity import RecordActivityUseCase
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.gamification.provider import GamificationProvider
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.telegram.dispatcher import on_error
from manashelper.platform.telegram.webhook_models import ProcessedTelegramUpdate
from manashelper.platform.web.auth import authenticate
from manashelper.platform.web.server import create_web_app
from tests.platform.web.factories import SECRET, TOKEN, USER_ID, authorization


@pytest.mark.parametrize("case", ["missing", "scheme", "expired", "future", "duplicate"])
def test_bad_init_data_rejected(case):
    # Construct timestamps at execution time, not test collection: a full suite
    # can take long enough for a future timestamp to enter the allowed window.
    headers = {
        "missing": "",
        "scheme": "Bearer x",
        "expired": authorization(age=3601),
        "future": authorization(age=-60),
        "duplicate": authorization() + "&auth_date=0",
    }
    with pytest.raises(web.HTTPUnauthorized):
        authenticate(headers[case], TOKEN)


@asynccontextmanager
async def application():
    settings = get_settings().model_copy(
        update={"public_url": "https://example.com", "webhook_secret": SecretStr(SECRET)}
    )
    container = make_async_container(CoreProvider(), UsersProvider(), GamificationProvider())
    dispatcher = Dispatcher()
    calls = []

    @dispatcher.message()
    async def received(message: Message, activity: FromDishka[RecordActivityUseCase]):
        calls.append(message.text)
        await activity.execute(USER_ID, "published")
        if message.text == "fail":
            raise RuntimeError("Synthetic handler failure")
        if message.text == "slow":
            await asyncio.sleep(0.2)

    dispatcher.errors.register(on_error)
    setup_dishka(container, dispatcher)
    inject_router(dispatcher)
    async with Bot(TOKEN) as bot:
        async with container() as scope:
            session = await scope.get(AsyncSession)
            session.add(User(id=USER_ID, full_name="<script>Fixture</script>", locale="ru"))
            await (await scope.get(AchievementRepository)).set_enabled(USER_ID, True)
        try:
            async with TestClient(TestServer(create_web_app(bot, dispatcher, container, settings))) as client:
                yield client, container, calls
        finally:
            async with container() as scope:
                session = await scope.get(AsyncSession)
                await session.execute(delete(User).where(User.id == USER_ID))
                await session.execute(
                    delete(ProcessedTelegramUpdate).where(ProcessedTelegramUpdate.update_id.between(992000, 992099))
                )
            await container.close()
            await dispatcher.storage.close()


def update(update_id, text="okay"):
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": 0,
            "text": text,
            "chat": {"id": USER_ID, "type": "private"},
            "from": {"id": USER_ID, "is_bot": False, "first_name": "Fixture"},
        },
    }


async def test_webhook_secret_failure_rollback_success_commit_and_replay():
    async with application() as (client, container, calls):
        assert (await client.post("/telegram/webhook", json=update(992010))).status == 401
        headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
        assert (await client.post("/telegram/webhook", headers=headers, json=update(992010, "fail"))).status == 500
        async with container() as scope:
            session = await scope.get(AsyncSession)
            assert await session.get(ProcessedTelegramUpdate, 992010) is None
            assert await session.scalar(select(User.id).where(User.id == USER_ID)) == USER_ID
            assert await (await scope.get(AchievementRepository)).get_awards(USER_ID) == {}
        assert (await client.post("/telegram/webhook", headers=headers, json=update(992010))).status == 200
        assert (await client.post("/telegram/webhook", headers=headers, json=update(992010))).status == 200
        assert calls == ["fail", "okay"]
        response = await client.get("/api/gamification/me", headers={"Authorization": authorization()})
        assert response.status == 200 and response.headers["Cache-Control"] == "no-store"
        data = await response.json()
        assert data["score"] == 1 and data["locale"] == "ru"
        assert next(card for card in data["achievements"] if card["key"] == "seller")["earned_at"]
        assert "student_number" not in json.dumps(data)


async def test_api_authorization_unknown_user_and_leaderboard_privacy():
    async with application() as (client, container, calls):
        assert (await client.get("/api/gamification/me")).status == 401
        assert (
            await client.get("/api/gamification/me", headers={"Authorization": authorization(992099)})
        ).status == 403
        headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
        await client.post("/telegram/webhook", headers=headers, json=update(992011))
        response = await client.get("/api/gamification/leaderboard", headers={"Authorization": authorization()})
        data = await response.json()
        mine = next(entry for entry in data["entries"] if entry["is_self"])
        assert mine["full_name"] == "<script>Fixture</script>"
        assert set(mine) == {"full_name", "score", "rank", "is_self"}


async def test_disabled_user_cannot_access_either_api_even_with_valid_init_data():
    async with application() as (client, container, calls):
        async with container() as scope:
            await (await scope.get(AchievementRepository)).set_enabled(USER_ID, False)
        for path in ("me", "leaderboard"):
            response = await client.get(f"/api/gamification/{path}", headers={"Authorization": authorization()})
            assert response.status == 403
            assert response.headers["Cache-Control"] == "no-store"


async def test_concurrent_replay_is_not_acknowledged_before_processing():
    async with application() as (client, container, calls):
        headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
        first = asyncio.create_task(client.post("/telegram/webhook", headers=headers, json=update(992012, "slow")))
        while not calls:
            await asyncio.sleep(0.01)
        second = await client.post("/telegram/webhook", headers=headers, json=update(992012, "slow"))
        assert second.status == 503
        assert (await first).status == 200
        assert (await client.post("/telegram/webhook", headers=headers, json=update(992012, "slow"))).status == 200
        assert calls == ["slow"]


@pytest.mark.skipif(not os.getenv("MANASHELPER_TELEGRAM_SIMULATION_URL"), reason="Optional local Telegram simulation")
async def test_real_aiogram_client_serializes_webhook_registration():
    import httpx

    url = os.environ["MANASHELPER_TELEGRAM_SIMULATION_URL"]
    async with httpx.AsyncClient() as http:
        await http.post(f"{url}/_reset")
        async with Bot(TOKEN, session=AiohttpSession(api=TelegramAPIServer.from_base(url))) as bot:
            assert await bot.set_webhook(
                "https://example.com/telegram/webhook",
                secret_token=SECRET,
                allowed_updates=["message", "callback_query"],
                max_connections=10,
                drop_pending_updates=False,
            )
        calls = (await http.get(f"{url}/_requests")).json()
        assert calls == [
            {
                "method": "setWebhook",
                "url": "https://example.com/telegram/webhook",
                "has_secret": True,
                "allowed_updates": '["message", "callback_query"]',
                "max_connections": 10,
            }
        ]
