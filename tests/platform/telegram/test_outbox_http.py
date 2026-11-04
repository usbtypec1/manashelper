import asyncio
import os
from collections import Counter
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.telegram import TelegramAPIServer
from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dishka import make_async_container
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manashelper.core.provider import CoreProvider
from manashelper.modules.broadcast.sender import TelegramBroadcastSender
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.users.application.bot_status import BotStatusQuery
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.telegram.outbox.jobs import deliver_outbox_job
from manashelper.platform.telegram.outbox.models import OutboxMessage, OutboxRateBucket
from manashelper.platform.telegram.outbox.provider import OutboxProvider
from manashelper.platform.telegram.outbox.service import OutboxService
from manashelper.platform.telegram.session import TelegramSession

SIMULATION_URL = os.getenv("MANASHELPER_TELEGRAM_SIMULATION_URL")
pytestmark = pytest.mark.skipif(not SIMULATION_URL, reason="Optional local Postman Telegram simulation")


@asynccontextmanager
async def delivery(engine, ids):
    container = make_async_container(CoreProvider(), UsersProvider(), NotificationsProvider(), OutboxProvider())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with container() as request:
            session = await request.get(AsyncSession)
            session.add_all(User(id=user_id, full_name="Synthetic recipient", locale="en") for user_id in ids)
        async with httpx.AsyncClient() as http:
            (await http.post(f"{SIMULATION_URL}/_reset")).raise_for_status()
            async with Bot(
                token="123456:development-placeholder",
                session=TelegramSession(api=TelegramAPIServer.from_base(SIMULATION_URL)),
                default=DefaultBotProperties(parse_mode="HTML"),
            ) as bot:
                yield container, bot, http
    finally:
        await container.close()
        async with sessions.begin() as session:
            await session.execute(delete(User).where(User.id.in_(ids)))
            await session.execute(delete(OutboxRateBucket).where(OutboxRateBucket.key.like("bot:123456%")))


async def drain(container, bot, ids, ready):
    async def run():
        while True:
            await deliver_outbox_job(container, bot)
            async with container() as request:
                session = await request.get(AsyncSession)
                rows = list((await session.scalars(select(OutboxMessage).where(OutboxMessage.user_id.in_(ids)))).all())
                if ready(rows):
                    return rows
            await asyncio.sleep(0.1)

    return await asyncio.wait_for(run(), timeout=15)


async def test_real_client_serialization_and_delivery_failure_flags(engine):
    ids = list(range(910001, 910008))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Site", url="https://example.com")],
            [InlineKeyboardButton(text="Menu", callback_data="food_menu:0")],
        ]
    )
    async with delivery(engine, ids) as (container, bot, http):
        async with container() as request:
            sender = TelegramBroadcastSender(
                await request.get(OutboxService),
                await request.get(LocaleQuery),
                photo_id="cached-photo-id",
                keyboard=keyboard,
            )
            for user_id in ids:
                assert await sender.send(user_id, "Hello <students>")
            # The producer only persists work; no Telegram call happens before commit.
            assert (await http.get(f"{SIMULATION_URL}/_requests")).json() == []
        rows = await drain(container, bot, ids, lambda rows: len(rows) == 7 and all(row.attempts for row in rows))
        by_id = {row.user_id: row for row in rows}
        assert by_id[ids[0]].status == "sent"
        assert all(by_id[user_id].status == "failed" for user_id in [*ids[1:4], ids[6]])
        assert all(by_id[user_id].status == "pending" for user_id in ids[4:6])
        async with container() as request:
            status = await request.get(BotStatusQuery)
            sender = TelegramBroadcastSender(await request.get(OutboxService), await request.get(LocaleQuery))
            for user_id in ids[1:4]:
                assert await status.is_stopped(user_id)
                assert not await sender.send(user_id, "Do not send again")
            for user_id in [ids[0], *ids[4:]]:
                assert not await status.is_stopped(user_id)
        calls = (await http.get(f"{SIMULATION_URL}/_requests")).json()
        first = next(call for call in calls if call["chat_id"] == ids[0])
        assert first["method"] == "sendPhoto" and first["photo"] == "cached-photo-id"
        assert "Hello &lt;students&gt;" in first["caption"]
        assert first["reply_markup"]["inline_keyboard"][0][0]["url"] == "https://example.com"
        assert first["reply_markup"]["inline_keyboard"][1][0]["callback_data"] == "food_menu:0"
        assert all(sum(call["chat_id"] == user_id for call in calls) == 1 for user_id in ids[1:4])


async def test_real_worker_recovers_429_json_503_html_502_and_checkpoints_photo(engine):
    ids = [920005, 920006, 920007, 920008, 920009]
    async with delivery(engine, ids) as (container, bot, http):
        async with container() as request:
            outbox = await request.get(OutboxService)
            for user_id in ids[:3]:
                assert await outbox.enqueue(user_id, [SendMessage(chat_id=user_id, text="Retry me")])
            sender = TelegramBroadcastSender(outbox, await request.get(LocaleQuery), photo_id="cached-photo-id")
            assert await sender.send(920008, "x" * 1024)
            assert await outbox.enqueue(
                920009,
                [SendMessage(chat_id=920009, text="Must expire")],
                expires_at=datetime.now(UTC) + timedelta(milliseconds=10),
            )
        await asyncio.sleep(0.02)
        rows = await drain(container, bot, ids, lambda rows: len(rows) == 5 and all(row.finished_at for row in rows))
        by_id = {row.user_id: row for row in rows}
        assert all(by_id[user_id].status == "sent" for user_id in ids[:4])
        assert by_id[920009].status == "expired" and by_id[920009].attempts == 0
        calls = (await http.get(f"{SIMULATION_URL}/_requests")).json()
        assert not any(call["chat_id"] == 920009 for call in calls)
        counts = Counter((call["chat_id"], call["method"]) for call in calls)
        for user_id in ids[:3]:
            assert counts[user_id, "sendMessage"] == 2
            attempts = [call for call in calls if call["chat_id"] == user_id]
            assert attempts[1]["at"] - attempts[0]["at"] >= 1000
        assert counts[920008, "sendPhoto"] == 1 and counts[920008, "sendMessage"] == 2
        assert by_id[920008].position == 2 and by_id[920008].attempts == 3
